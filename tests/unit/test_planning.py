from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from rightjob.contracts.authorization import ExecutionAuthorizationReference
from rightjob.contracts.capabilities import EffectClassification
from rightjob.contracts.departments import WorkCategory
from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.planning import (
    ExecutionPlan,
    PlanningConstraints,
    PlanningContext,
    PlanningRequest,
    ProposedPlan,
    StructuredInput,
    SyntheticPlanningGoal,
)
from rightjob.orchestration.application.plan_compiler import (
    ExecutionPlanCompilationError,
    ExecutionPlanCompiler,
)
from rightjob.orchestration.application.registry import BUILT_IN_WORKFLOWS
from rightjob.planner import PlanValidationError, PlanValidator, SyntheticPlanner
from rightjob.registry import (
    BUILT_IN_CAPABILITIES,
    BUILT_IN_DEPARTMENTS,
    BuiltInCapabilityRegistry,
    BuiltInDepartmentRegistry,
)

NOW = datetime(2026, 8, 12, 12, tzinfo=timezone.utc)
WORKSPACE = UUID("03000000-0000-4000-8000-000000000001")
REQUEST_ID = UUID("03000000-0000-4000-8000-000000000002")
CORRELATION_ID = UUID("03000000-0000-4000-8000-000000000003")
CAUSATION_ID = UUID("03000000-0000-4000-8000-000000000004")


def authorization(plan_id: UUID, workspace_id: UUID = WORKSPACE) -> ExecutionAuthorizationReference:
    return ExecutionAuthorizationReference(UUID(int=88), workspace_id, plan_id, "0" * 64)


class DeterministicIds:
    def __init__(self) -> None:
        self._next = 100

    def __call__(self) -> UUID:
        value = UUID(f"03000000-0000-4000-8000-{self._next:012d}")
        self._next += 1
        return value


def request(
    goal: SyntheticPlanningGoal = SyntheticPlanningGoal.PREPARE_TRANSFORM_VERIFY,
) -> PlanningRequest:
    return PlanningRequest(
        planning_request_id=REQUEST_ID,
        workspace_id=WORKSPACE,
        correlation_id=CORRELATION_ID,
        causation_id=CAUSATION_ID,
        actor=Actor(ActorType.USER, "user-1"),
        goal=goal,
        constraints=PlanningConstraints(),
        input=StructuredInput((("value", "synthetic content"),)),
        created_at=NOW,
    )


def context(item: PlanningRequest | None = None) -> PlanningContext:
    planning_request = item or request()
    return PlanningContext(
        workspace_id=planning_request.workspace_id,
        actor=planning_request.actor,
        correlation_id=planning_request.correlation_id,
        causation_id=planning_request.causation_id,
        available_departments=tuple(item.reference for item in BUILT_IN_DEPARTMENTS),
        available_capabilities=tuple(item.reference for item in BUILT_IN_CAPABILITIES),
        constraints=planning_request.constraints,
    )


def proposal(
    goal: SyntheticPlanningGoal = SyntheticPlanningGoal.PREPARE_TRANSFORM_VERIFY,
) -> tuple[PlanningRequest, PlanningContext, ProposedPlan]:
    planning_request = request(goal)
    planning_context = context(planning_request)
    proposed = SyntheticPlanner(DeterministicIds()).plan(planning_request, planning_context)
    return planning_request, planning_context, proposed


def validator() -> PlanValidator:
    capabilities = BuiltInCapabilityRegistry()
    return PlanValidator(capabilities, BuiltInDepartmentRegistry(capabilities))


def test_planning_contracts_are_immutable_bounded_and_secret_safe() -> None:
    planning_request = request()
    assert planning_request.input.as_dict() == {"value": "synthetic content"}
    with pytest.raises(FrozenInstanceError):
        planning_request.goal = SyntheticPlanningGoal.PREPARE  # type: ignore[misc]
    with pytest.raises(ValueError, match="secret-bearing"):
        StructuredInput((("token", "no"),))
    with pytest.raises(ValueError, match="unique"):
        StructuredInput((("value", "a"), ("value", "b")))
    with pytest.raises(ValueError, match="configured bound"):
        replace(
            planning_request,
            constraints=PlanningConstraints(maximum_input_bytes=1),
        )
    with pytest.raises(ValueError, match="user or system"):
        replace(planning_request, actor=Actor(ActorType.AI, "planner"))


@pytest.mark.parametrize(
    ("goal", "keys"),
    (
        (SyntheticPlanningGoal.PREPARE, ("fake.prepare",)),
        (SyntheticPlanningGoal.TRANSFORM, ("fake.transform",)),
        (SyntheticPlanningGoal.VERIFY, ("fake.verify",)),
        (
            SyntheticPlanningGoal.PREPARE_TRANSFORM_VERIFY,
            ("fake.prepare", "fake.transform", "fake.verify"),
        ),
    ),
)
def test_synthetic_planner_is_deterministic_for_all_goals(
    goal: SyntheticPlanningGoal, keys: tuple[str, ...]
) -> None:
    first_request, first_context, first = proposal(goal)
    second = SyntheticPlanner(DeterministicIds()).plan(first_request, first_context)
    assert first == second
    assert tuple(step.capability.capability_key for step in first.steps) == keys
    assert tuple(step.sequence for step in first.steps) == tuple(range(len(keys)))
    assert tuple(step.dependency_step_ids for step in first.steps) == tuple(
        () if index == 0 else (first.steps[index - 1].step_id,) for index in range(len(keys))
    )


def test_validator_returns_distinct_validated_plan_with_exact_metadata() -> None:
    planning_request, planning_context, proposed = proposal()
    validated = validator().validate(planning_request, planning_context, proposed)
    assert isinstance(validated, ExecutionPlan)
    assert validated.steps == proposed.steps
    assert validated.workspace_id == WORKSPACE
    assert validated.correlation_id == CORRELATION_ID
    assert validated.causation_id == CAUSATION_ID
    for step, capability in zip(validated.steps, BUILT_IN_CAPABILITIES, strict=True):
        assert step.expected_output == capability.output_contract
        assert step.effect_classification is capability.effect_classification


def test_validator_rejects_duplicate_missing_cyclic_and_unordered_dependencies() -> None:
    planning_request, planning_context, proposed = proposal()
    first, second, third = proposed.steps
    cases = (
        replace(
            proposed,
            steps=(
                first,
                replace(second, step_id=first.step_id, dependency_step_ids=()),
                third,
            ),
        ),
        replace(
            proposed,
            steps=(first, replace(second, dependency_step_ids=(UUID(int=99),)), third),
        ),
        replace(
            proposed,
            steps=(
                replace(first, dependency_step_ids=(third.step_id,)),
                second,
                replace(third, dependency_step_ids=(first.step_id,)),
            ),
        ),
        replace(proposed, steps=(first, replace(second, sequence=2), third)),
        replace(
            proposed, steps=(replace(first, dependency_step_ids=(second.step_id,)), second, third)
        ),
    )
    for invalid in cases:
        with pytest.raises(PlanValidationError):
            validator().validate(planning_request, planning_context, invalid)


def test_validator_rejects_unknown_disabled_and_mismatched_references() -> None:
    planning_request, planning_context, proposed = proposal()
    first = proposed.steps[0]
    wrong_department = replace(first, department=BUILT_IN_DEPARTMENTS[1].reference)
    wrong_category = replace(first, work_category=WorkCategory.TRANSFORM)
    wrong_output = replace(first, expected_output=BUILT_IN_CAPABILITIES[1].output_contract)
    wrong_effect = replace(first, effect_classification=EffectClassification.REVERSIBLE)
    unknown_capability = replace(
        first.capability,
        capability_definition_id=UUID("03000000-0000-4000-8000-000000000099"),
    )
    unknown = replace(first, capability=unknown_capability)
    for invalid_step in (
        wrong_department,
        wrong_category,
        wrong_output,
        wrong_effect,
        unknown,
    ):
        invalid = replace(proposed, steps=(invalid_step, *proposed.steps[1:]))
        with pytest.raises(PlanValidationError):
            validator().validate(planning_request, planning_context, invalid)

    disabled_capability = replace(BUILT_IN_CAPABILITIES[0], enabled=False)
    capabilities = BuiltInCapabilityRegistry((disabled_capability, *BUILT_IN_CAPABILITIES[1:]))
    departments = BuiltInDepartmentRegistry(BuiltInCapabilityRegistry(), BUILT_IN_DEPARTMENTS)
    with pytest.raises(PlanValidationError):
        PlanValidator(capabilities, departments).validate(
            planning_request, planning_context, proposed
        )
    enabled_capabilities = BuiltInCapabilityRegistry()
    disabled_departments = BuiltInDepartmentRegistry(
        enabled_capabilities,
        (replace(BUILT_IN_DEPARTMENTS[0], enabled=False), BUILT_IN_DEPARTMENTS[1]),
    )
    with pytest.raises(PlanValidationError):
        PlanValidator(enabled_capabilities, disabled_departments).validate(
            planning_request, planning_context, proposed
        )


def test_validator_rejects_context_and_provenance_drift() -> None:
    planning_request, planning_context, proposed = proposal()
    with pytest.raises(PlanValidationError, match="context"):
        validator().validate(
            planning_request,
            replace(planning_context, workspace_id=UUID(int=99)),
            proposed,
        )
    with pytest.raises(PlanValidationError, match="provenance"):
        validator().validate(
            planning_request,
            planning_context,
            replace(proposed, correlation_id=UUID(int=99)),
        )
    with pytest.raises(PlanValidationError, match="synthetic goal"):
        validator().validate(
            replace(planning_request, goal=SyntheticPlanningGoal.PREPARE),
            replace(planning_context, constraints=planning_request.constraints),
            proposed,
        )


def test_execution_plan_compiler_stops_at_execution_request() -> None:
    planning_request, planning_context, proposed = proposal()
    plan = validator().validate(planning_request, planning_context, proposed)
    execution = ExecutionPlanCompiler().compile(
        plan,
        planning_request,
        BUILT_IN_WORKFLOWS[0],
        authorization(plan.plan_id),
        UUID("03000000-0000-4000-8000-000000000200"),
        NOW,
    )
    assert execution.workspace_id == plan.workspace_id
    assert execution.correlation_id == plan.correlation_id
    assert execution.causation_id == plan.causation_id
    assert execution.actor == planning_request.actor
    assert tuple(step.id for step in execution.steps) == tuple(step.step_id for step in plan.steps)
    assert execution.input == {"value": "synthetic content"}


def test_execution_plan_compiler_rejects_incompatible_workflow_and_provenance() -> None:
    planning_request, planning_context, proposed = proposal()
    plan = validator().validate(planning_request, planning_context, proposed)
    compiler = ExecutionPlanCompiler()
    with pytest.raises(ExecutionPlanCompilationError):
        compiler.compile(
            plan,
            planning_request,
            BUILT_IN_WORKFLOWS[1],
            authorization(plan.plan_id),
            UUID(int=200),
            NOW,
        )
    with pytest.raises(ExecutionPlanCompilationError, match="provenance"):
        compiler.compile(
            replace(plan, workspace_id=UUID(int=99)),
            planning_request,
            BUILT_IN_WORKFLOWS[0],
            authorization(plan.plan_id),
            UUID(int=200),
            NOW,
        )


def test_planning_source_has_no_provider_temporal_policy_or_dynamic_execution() -> None:
    root = Path(__file__).resolve().parents[2]
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            root / "packages/core/src/rightjob/contracts/planning.py",
            root / "packages/core/src/rightjob/planner/synthetic.py",
            root / "packages/core/src/rightjob/planner/validation.py",
            root / "packages/core/src/rightjob/orchestration/application/plan_compiler.py",
        )
    ).lower()
    for forbidden in (
        "importlib",
        "eval(",
        "exec(",
        "temporalio",
        "openai",
        "anthropic",
        "gemini",
        "prompt",
        "requires_policy_review",
        "orchestrationapplicationservice",
        "durableworkflowengine",
    ):
        assert forbidden not in source
