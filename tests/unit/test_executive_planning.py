import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from rightjob.contracts.ai import AIModelReference, AIProviderFailure
from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.executive import (
    ExecutivePlanningFailure,
    ExecutivePlanningOutcome,
    ExecutivePlanningRequest,
)
from rightjob.contracts.planning import (
    ExecutionPlan,
    PlanningApplication,
    PlanningConstraints,
    PlanningContext,
    PlanningRequest,
    StructuredInput,
    SyntheticPlanningGoal,
)
from rightjob.executive import ExecutivePlanningService
from rightjob.planner import (
    PlanningApplicationService,
    PlanValidator,
    ProviderBackedPlanner,
    SyntheticPlanner,
)
from rightjob.provider_adapters import FakeAIProvider
from rightjob.registry import BuiltInCapabilityRegistry, BuiltInDepartmentRegistry

NOW = datetime(2026, 8, 14, 8, 0, tzinfo=UTC)


class Ids:
    def __init__(self, prefix: int) -> None:
        self.prefix = prefix
        self.value = 0

    def __call__(self) -> UUID:
        self.value += 1
        return UUID(f"{self.prefix:08d}-0000-4000-8000-{self.value:012d}")


class CapturingPlanning:
    def __init__(self, delegate: PlanningApplication) -> None:
        self.delegate = delegate
        self.calls: list[tuple[PlanningRequest, PlanningContext]] = []

    def plan(self, request: PlanningRequest, context: PlanningContext) -> ExecutionPlan:
        self.calls.append((request, context))
        return self.delegate.plan(request, context)


class WrongWorkspacePlanning:
    def __init__(self, delegate: PlanningApplication) -> None:
        self.delegate = delegate

    def plan(self, request: PlanningRequest, context: PlanningContext) -> ExecutionPlan:
        plan = self.delegate.plan(request, context)
        return replace(plan, workspace_id=UUID("21400000-0000-4000-8000-000000009999"))


def executive_request() -> ExecutivePlanningRequest:
    return ExecutivePlanningRequest(
        workspace_id=UUID("21400000-0000-4000-8000-000000000001"),
        actor=Actor(ActorType.USER, "trusted-user"),
        correlation_id=UUID("21400000-0000-4000-8000-000000000002"),
        causation_id=UUID("21400000-0000-4000-8000-000000000003"),
        goal=SyntheticPlanningGoal.PREPARE_TRANSFORM_VERIFY,
        constraints=PlanningConstraints(),
        input=StructuredInput((("topic", "bounded planning data"),)),
    )


def catalogs() -> tuple[BuiltInCapabilityRegistry, BuiltInDepartmentRegistry]:
    capabilities = BuiltInCapabilityRegistry()
    return capabilities, BuiltInDepartmentRegistry(capabilities)


def service(
    planning: PlanningApplication,
    *,
    executive_ids: Ids | None = None,
) -> ExecutivePlanningService:
    capabilities, departments = catalogs()
    return ExecutivePlanningService(
        planning,
        capabilities,
        departments,
        executive_ids or Ids(21410000),
        lambda: NOW,
    )


def synthetic_application() -> PlanningApplicationService:
    capabilities, departments = catalogs()
    return PlanningApplicationService(
        SyntheticPlanner(Ids(21420000)), PlanValidator(capabilities, departments)
    )


def ai_proposal() -> str:
    def step(
        sequence: int,
        objective: str,
        category: str,
        department: str,
        capability: str,
        dependencies: list[int],
    ) -> dict[str, object]:
        return {
            "sequence": sequence,
            "objective": objective,
            "work_category": category,
            "department_key": department,
            "department_semantic_version": "1.0.0",
            "capability_key": capability,
            "capability_semantic_version": "1.0.0",
            "structured_input": [{"key": "topic", "value": "bounded planning data"}],
            "dependency_sequences": dependencies,
        }

    return json.dumps(
        {
            "schema_version": 1,
            "steps": [
                step(0, "prepare", "prepare", "foundation.operations", "fake.prepare", []),
                step(
                    1,
                    "transform",
                    "transform",
                    "foundation.content",
                    "fake.transform",
                    [0],
                ),
                step(2, "verify", "verify", "foundation.operations", "fake.verify", [1]),
            ],
        }
    )


def provider_application(
    provider: FakeAIProvider | None = None,
) -> PlanningApplicationService:
    capabilities, departments = catalogs()
    planner = ProviderBackedPlanner(
        provider or FakeAIProvider(ai_proposal()),
        capabilities,
        departments,
        AIModelReference("fake", "planning-model"),
        Ids(21430000),
        lambda: NOW,
    )
    return PlanningApplicationService(planner, PlanValidator(capabilities, departments))


def test_synthetic_planner_composes_through_published_planning_boundary() -> None:
    captured = CapturingPlanning(synthetic_application())
    request = executive_request()
    result = service(captured).plan(request)

    assert result.outcome is ExecutivePlanningOutcome.PLANNED
    assert result.plan is not None
    assert result.plan.workspace_id == request.workspace_id
    assert result.plan.actor == request.actor
    assert result.plan.correlation_id == request.correlation_id
    assert result.plan.causation_id == request.causation_id
    assert [step.objective.value for step in result.plan.steps] == [
        "prepare",
        "transform",
        "verify",
    ]
    planning_request, context = captured.calls[0]
    assert planning_request.actor == request.actor
    assert context.workspace_id == request.workspace_id
    assert tuple(item.department_key for item in context.available_departments) == (
        "foundation.content",
        "foundation.operations",
    )
    assert tuple(item.capability_key for item in context.available_capabilities) == (
        "fake.prepare",
        "fake.transform",
        "fake.verify",
    )


def test_provider_backed_planner_and_fake_provider_reach_safe_presentation() -> None:
    captured = CapturingPlanning(provider_application())
    request = executive_request()
    result = service(captured).plan(request)

    assert result.outcome is ExecutivePlanningOutcome.PLANNED
    assert result.plan is not None
    assert result.plan.planner.planner_key == "provider.backed.planner"
    assert result.plan.planning_request_id == captured.calls[0][0].planning_request_id
    assert result.plan.steps[1].dependency_step_ids == (result.plan.steps[0].step_id,)
    assert result.plan.steps[1].effect_classification.value == "reversible"
    assert not hasattr(result.plan.steps[0], "handler_key")


def test_identical_trusted_inputs_and_injections_are_deterministic() -> None:
    first = service(provider_application(), executive_ids=Ids(21410000)).plan(executive_request())
    second = service(provider_application(), executive_ids=Ids(21410000)).plan(executive_request())
    assert first == second


def test_mismatched_validated_plan_provenance_fails_closed() -> None:
    result = service(WrongWorkspacePlanning(synthetic_application())).plan(executive_request())
    assert result.outcome is ExecutivePlanningOutcome.NOT_PLANNABLE
    assert result.failure is ExecutivePlanningFailure.PLANNING_REJECTED
    assert result.plan is None


@pytest.mark.parametrize(
    ("provider_failure", "outcome", "executive_failure"),
    [
        (
            AIProviderFailure.TIMEOUT,
            ExecutivePlanningOutcome.FAILED,
            ExecutivePlanningFailure.PROVIDER_UNAVAILABLE,
        ),
        (
            AIProviderFailure.CONFIGURATION,
            ExecutivePlanningOutcome.FAILED,
            ExecutivePlanningFailure.PROVIDER_CONFIGURATION,
        ),
        (
            AIProviderFailure.REFUSAL,
            ExecutivePlanningOutcome.NOT_PLANNABLE,
            ExecutivePlanningFailure.INVALID_PROVIDER_OUTPUT,
        ),
        (
            AIProviderFailure.SCHEMA_VIOLATION,
            ExecutivePlanningOutcome.NOT_PLANNABLE,
            ExecutivePlanningFailure.INVALID_PROVIDER_OUTPUT,
        ),
    ],
)
def test_provider_failures_are_presentation_safe(
    provider_failure: AIProviderFailure,
    outcome: ExecutivePlanningOutcome,
    executive_failure: ExecutivePlanningFailure,
) -> None:
    result = service(provider_application(FakeAIProvider(failure=provider_failure))).plan(
        executive_request()
    )
    assert result == result.__class__(outcome, failure=executive_failure)


def test_invalid_actor_and_nil_workspace_fail_before_planning() -> None:
    value = executive_request()
    with pytest.raises(ValueError, match="actor"):
        replace(value, actor=Actor(ActorType.PROVIDER, "untrusted"))
    with pytest.raises(ValueError, match="must not be nil"):
        replace(value, workspace_id=UUID(int=0))
