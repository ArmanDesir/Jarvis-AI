from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from rightjob.contracts.capabilities import EffectClassification, SemanticVersion
from rightjob.contracts.departments import WorkCategory
from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.planning import (
    ExecutionPlan,
    PlanningConstraints,
    PlanningContext,
    PlanningRequest,
    StructuredInput,
    SyntheticPlanningGoal,
)
from rightjob.contracts.policy import (
    MembershipFacts,
    PolicyAction,
    PolicyContext,
    PolicyDecision,
    PolicyEvaluationError,
    PolicyOperation,
    PolicyReasonCode,
    PolicySubject,
)
from rightjob.planner import PlanValidator, SyntheticPlanner
from rightjob.policy import (
    SYNTHETIC_POLICY_SET,
    PlanPolicyEvaluator,
    SyntheticPolicyEvaluator,
)
from rightjob.registry import (
    BUILT_IN_CAPABILITIES,
    BUILT_IN_DEPARTMENTS,
    BuiltInCapabilityRegistry,
    BuiltInDepartmentRegistry,
)

NOW = datetime(2026, 8, 13, 8, tzinfo=timezone.utc)
WORKSPACE = UUID("03100000-0000-4000-8000-000000000010")
USER = UUID("03100000-0000-4000-8000-000000000011")
MEMBERSHIP = UUID("03100000-0000-4000-8000-000000000012")
REQUEST = UUID("03100000-0000-4000-8000-000000000013")
CORRELATION = UUID("03100000-0000-4000-8000-000000000014")
CAUSATION = UUID("03100000-0000-4000-8000-000000000015")


class DeterministicIds:
    def __init__(self, start: int = 100) -> None:
        self._next = start

    def __call__(self) -> UUID:
        value = UUID(f"03100000-0000-4000-8000-{self._next:012d}")
        self._next += 1
        return value


def planning_request() -> PlanningRequest:
    return PlanningRequest(
        REQUEST,
        WORKSPACE,
        CORRELATION,
        CAUSATION,
        Actor(ActorType.USER, str(USER)),
        SyntheticPlanningGoal.PREPARE_TRANSFORM_VERIFY,
        PlanningConstraints(),
        StructuredInput((("value", "synthetic"),)),
        NOW,
    )


def validated_plan() -> tuple[PlanningRequest, ExecutionPlan]:
    request = planning_request()
    capabilities = BuiltInCapabilityRegistry()
    departments = BuiltInDepartmentRegistry(capabilities)
    context = PlanningContext(
        request.workspace_id,
        request.actor,
        request.correlation_id,
        request.causation_id,
        tuple(item.reference for item in BUILT_IN_DEPARTMENTS),
        tuple(item.reference for item in BUILT_IN_CAPABILITIES),
        request.constraints,
    )
    proposal = SyntheticPlanner(DeterministicIds()).plan(request, context)
    return request, PlanValidator(capabilities, departments).validate(request, context, proposal)


def subject(*, active: bool = True) -> PolicySubject:
    return PolicySubject(
        Actor(ActorType.USER, str(USER)),
        WORKSPACE,
        MembershipFacts(
            MEMBERSHIP,
            USER,
            WORKSPACE,
            active,
            ("member",),
            ("synthetic.execute",),
        ),
    )


def policy_context(plan: ExecutionPlan) -> PolicyContext:
    return PolicyContext(WORKSPACE, CORRELATION, CAUSATION, REQUEST, plan.plan_id)


def action(plan: ExecutionPlan, index: int = 0) -> PolicyAction:
    step = plan.steps[index]
    return PolicyAction(
        PolicyOperation.EXECUTE_CAPABILITY,
        plan.plan_id,
        step.step_id,
        step.department,
        step.capability,
        step.work_category,
        step.effect_classification,
    )


def evaluator(
    capabilities: BuiltInCapabilityRegistry | None = None,
    departments: BuiltInDepartmentRegistry | None = None,
    *,
    ids: DeterministicIds | None = None,
) -> SyntheticPolicyEvaluator:
    capability_catalog = capabilities or BuiltInCapabilityRegistry()
    department_catalog = departments or BuiltInDepartmentRegistry(capability_catalog)
    return SyntheticPolicyEvaluator(
        capability_catalog, department_catalog, ids or DeterministicIds(500), lambda: NOW
    )


def test_policy_contracts_are_immutable_versioned_and_bounded() -> None:
    policy_subject = subject()
    assert SYNTHETIC_POLICY_SET.policy_set_key == "synthetic.foundation.policy"
    assert SYNTHETIC_POLICY_SET.semantic_version == SemanticVersion.parse("1.0.0")
    with pytest.raises(FrozenInstanceError):
        policy_subject.workspace_id = UUID(int=1)  # type: ignore[misc]
    with pytest.raises(ValueError, match="unique"):
        replace(policy_subject.membership, roles=("member", "member"))
    with pytest.raises(ValueError, match="bounded canonical"):
        replace(policy_subject.membership, permissions=("not valid",))
    with pytest.raises(PolicyEvaluationError, match="Workspaces"):
        replace(policy_subject, workspace_id=UUID(int=99))


def test_allow_is_deterministic_with_exact_rules_id_and_clock() -> None:
    _, plan = validated_plan()
    ids = DeterministicIds(700)
    policy = evaluator(ids=ids)
    first = policy.evaluate(subject(), action(plan), policy_context(plan))
    second = policy.evaluate(subject(), action(plan), policy_context(plan))
    assert first.decision is PolicyDecision.ALLOW
    assert first.reason_codes == (PolicyReasonCode.SYNTHETIC_NONCONSEQUENTIAL_ALLOWED,)
    assert tuple(rule.rule_key for rule in first.matched_rules) == (
        "synthetic.validate_action",
        "synthetic.authorize_subject",
        "synthetic.classify_effect",
    )
    assert first.decision_id == UUID("03100000-0000-4000-8000-000000000700")
    assert second.decision_id == UUID("03100000-0000-4000-8000-000000000701")
    assert first.evaluated_at == NOW
    assert (first.expires_at - first.evaluated_at).total_seconds() == 300
    assert replace(first, decision_id=second.decision_id) == second


@pytest.mark.parametrize(
    "policy_subject",
    (
        subject(active=False),
        PolicySubject(Actor(ActorType.USER, str(USER)), WORKSPACE, None),
        PolicySubject(Actor(ActorType.SYSTEM, "system"), WORKSPACE, None),
        PolicySubject(
            Actor(ActorType.USER, str(UUID(int=99))),
            WORKSPACE,
            subject().membership,
        ),
    ),
)
def test_missing_inactive_or_unsupported_subject_is_denied(
    policy_subject: PolicySubject,
) -> None:
    _, plan = validated_plan()
    result = evaluator().evaluate(policy_subject, action(plan), policy_context(plan))
    assert result.decision is PolicyDecision.DENY
    assert result.reason_codes == (PolicyReasonCode.SUBJECT_NOT_AUTHORIZED,)


def test_consequential_and_external_effect_require_future_approval() -> None:
    request, plan = validated_plan()
    for effect in (
        EffectClassification.CONSEQUENTIAL,
        EffectClassification.EXTERNAL_EFFECT,
    ):
        changed_capability = replace(BUILT_IN_CAPABILITIES[0], effect_classification=effect)
        capabilities = BuiltInCapabilityRegistry((changed_capability, *BUILT_IN_CAPABILITIES[1:]))
        departments = BuiltInDepartmentRegistry(capabilities)
        changed_step = replace(plan.steps[0], effect_classification=effect)
        changed_plan = replace(plan, steps=(changed_step, *plan.steps[1:]))
        result = evaluator(capabilities, departments).evaluate(
            subject(), action(changed_plan), policy_context(changed_plan)
        )
        assert request.workspace_id == result.context.workspace_id
        assert result.decision is PolicyDecision.REQUIRE_APPROVAL
        assert result.reason_codes == (PolicyReasonCode.APPROVAL_REQUIRED_FOR_EFFECT,)


def test_workspace_plan_and_registry_metadata_fail_closed() -> None:
    _, plan = validated_plan()
    policy = evaluator()
    valid_action = action(plan)
    cases = (
        (
            replace(subject(), workspace_id=UUID(int=99), membership=None),
            valid_action,
            policy_context(plan),
        ),
        (subject(), replace(valid_action, plan_id=UUID(int=99)), policy_context(plan)),
        (
            subject(),
            replace(
                valid_action,
                department=replace(
                    valid_action.department,
                    department_definition_id=UUID(int=99),
                ),
            ),
            policy_context(plan),
        ),
        (
            subject(),
            replace(
                valid_action,
                department=replace(
                    valid_action.department,
                    semantic_version=SemanticVersion.parse("9.0.0"),
                ),
            ),
            policy_context(plan),
        ),
        (
            subject(),
            replace(
                valid_action,
                capability=replace(
                    valid_action.capability,
                    capability_definition_id=UUID(int=99),
                ),
            ),
            policy_context(plan),
        ),
        (
            subject(),
            replace(
                valid_action,
                capability=replace(
                    valid_action.capability,
                    semantic_version=SemanticVersion.parse("9.0.0"),
                ),
            ),
            policy_context(plan),
        ),
        (
            subject(),
            replace(valid_action, work_category=WorkCategory.TRANSFORM),
            policy_context(plan),
        ),
        (
            subject(),
            replace(valid_action, effect_classification=EffectClassification.REVERSIBLE),
            policy_context(plan),
        ),
    )
    for policy_subject, policy_action, context in cases:
        with pytest.raises(PolicyEvaluationError):
            policy.evaluate(policy_subject, policy_action, context)


def test_disabled_and_department_capability_mismatch_fail_closed() -> None:
    _, plan = validated_plan()
    disabled_capability = replace(BUILT_IN_CAPABILITIES[0], enabled=False)
    disabled_capabilities = BuiltInCapabilityRegistry(
        (disabled_capability, *BUILT_IN_CAPABILITIES[1:])
    )
    with pytest.raises(PolicyEvaluationError):
        evaluator(
            disabled_capabilities,
            BuiltInDepartmentRegistry(BuiltInCapabilityRegistry()),
        ).evaluate(subject(), action(plan), policy_context(plan))

    capabilities = BuiltInCapabilityRegistry()
    disabled_departments = BuiltInDepartmentRegistry(
        capabilities,
        (replace(BUILT_IN_DEPARTMENTS[0], enabled=False), BUILT_IN_DEPARTMENTS[1]),
    )
    with pytest.raises(PolicyEvaluationError):
        evaluator(capabilities, disabled_departments).evaluate(
            subject(), action(plan), policy_context(plan)
        )
    with pytest.raises(PolicyEvaluationError, match="does not belong"):
        evaluator().evaluate(
            subject(),
            replace(action(plan), department=BUILT_IN_DEPARTMENTS[1].reference),
            policy_context(plan),
        )


def test_plan_evaluation_preserves_steps_provenance_and_aggregate_allow() -> None:
    request, plan = validated_plan()
    aggregate = PlanPolicyEvaluator(evaluator()).evaluate(
        request, plan, subject(), policy_context(plan)
    )
    assert aggregate.decision is PolicyDecision.ALLOW
    assert len(aggregate.step_evaluations) == 3
    assert tuple(item.action.step_id for item in aggregate.step_evaluations) == tuple(
        step.step_id for step in plan.steps
    )
    assert all(item.context.correlation_id == CORRELATION for item in aggregate.step_evaluations)
    assert all(item.context.causation_id == CAUSATION for item in aggregate.step_evaluations)


def test_plan_aggregate_require_approval_deny_and_precedence() -> None:
    request, plan = validated_plan()
    changed_capability = replace(
        BUILT_IN_CAPABILITIES[1], effect_classification=EffectClassification.CONSEQUENTIAL
    )
    capabilities = BuiltInCapabilityRegistry(
        (BUILT_IN_CAPABILITIES[0], changed_capability, BUILT_IN_CAPABILITIES[2])
    )
    departments = BuiltInDepartmentRegistry(capabilities)
    changed_plan = replace(
        plan,
        steps=(
            plan.steps[0],
            replace(plan.steps[1], effect_classification=EffectClassification.CONSEQUENTIAL),
            plan.steps[2],
        ),
    )
    aggregate = PlanPolicyEvaluator(evaluator(capabilities, departments)).evaluate(
        request, changed_plan, subject(), policy_context(changed_plan)
    )
    assert aggregate.decision is PolicyDecision.REQUIRE_APPROVAL
    assert tuple(item.decision for item in aggregate.step_evaluations) == (
        PolicyDecision.ALLOW,
        PolicyDecision.REQUIRE_APPROVAL,
        PolicyDecision.ALLOW,
    )
    denied = PlanPolicyEvaluator(evaluator(capabilities, departments)).evaluate(
        request, changed_plan, subject(active=False), policy_context(changed_plan)
    )
    assert denied.decision is PolicyDecision.DENY
    assert all(item.decision is PolicyDecision.DENY for item in denied.step_evaluations)

    class MixedEvaluator:
        def evaluate(
            self,
            policy_subject: PolicySubject,
            policy_action: PolicyAction,
            context: PolicyContext,
        ):
            result = evaluator(capabilities, departments).evaluate(
                policy_subject, policy_action, context
            )
            if policy_action.capability.capability_key == "fake.verify":
                return replace(
                    result,
                    decision=PolicyDecision.DENY,
                    reason_codes=(PolicyReasonCode.SUBJECT_NOT_AUTHORIZED,),
                )
            return result

    mixed = PlanPolicyEvaluator(MixedEvaluator()).evaluate(
        request, changed_plan, subject(), policy_context(changed_plan)
    )
    assert tuple(item.decision for item in mixed.step_evaluations) == (
        PolicyDecision.ALLOW,
        PolicyDecision.REQUIRE_APPROVAL,
        PolicyDecision.DENY,
    )
    assert mixed.decision is PolicyDecision.DENY


def test_plan_provenance_mismatch_fails_closed() -> None:
    request, plan = validated_plan()
    with pytest.raises(PolicyEvaluationError, match="provenance"):
        PlanPolicyEvaluator(evaluator()).evaluate(
            request,
            replace(plan, correlation_id=UUID(int=99)),
            subject(),
            policy_context(plan),
        )


def test_policy_source_has_no_authority_leakage_or_dynamic_execution() -> None:
    root = Path(__file__).resolve().parents[2]
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            root / "packages/core/src/rightjob/contracts/policy.py",
            root / "packages/core/src/rightjob/policy/evaluator.py",
            root / "packages/core/src/rightjob/policy/plan_evaluation.py",
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
        "sqlalchemy",
        "rightjob.identity",
        "rightjob.orchestration",
        "rightjob.registry",
        "rightjob.executive",
        "rightjob.planner",
        "durableworkflowengine",
        "orchestrationapplicationservice",
        "executionrequest",
    ):
        assert forbidden not in source
