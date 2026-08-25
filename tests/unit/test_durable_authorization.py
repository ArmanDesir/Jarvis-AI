from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from rightjob.contracts.approval import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRequest,
    ApprovalStatus,
    decide_request,
)
from rightjob.contracts.authorization import (
    AuthorizationError,
    AuthorizationEvidence,
    AuthorizedWorkflow,
    AuthorizedWorkflowStep,
    ExecutionAuthorization,
    action_digest,
    canonical_json,
)
from rightjob.contracts.capabilities import EffectClassification
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
    PolicyOperation,
    PolicySubject,
)
from rightjob.orchestration.application.registry import BUILT_IN_WORKFLOWS
from rightjob.planner import PlanValidator, SyntheticPlanner
from rightjob.policy import (
    SYNTHETIC_POLICY_SET,
    DurableAuthorizationService,
    SyntheticPolicyEvaluator,
)
from rightjob.policy.application import GovernanceRecorder
from rightjob.policy.infrastructure.models import (
    ApprovalDecisionRecord,
    ApprovalRequestRecord,
    AuthorizationEvidenceRecord,
    ExecutionAuthorizationRecord,
    ExecutionAuthorizationStepRecord,
)
from rightjob.policy.repositories import IdempotencyConflictError
from rightjob.registry import (
    BUILT_IN_CAPABILITIES,
    BUILT_IN_DEPARTMENTS,
    BuiltInCapabilityRegistry,
    BuiltInDepartmentRegistry,
)
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.exc import IntegrityError

NOW = datetime(2026, 8, 13, 10, tzinfo=timezone.utc)
WORKSPACE = UUID("03200000-0000-4000-8000-000000000001")
USER = UUID("03200000-0000-4000-8000-000000000002")
MEMBERSHIP = UUID("03200000-0000-4000-8000-000000000003")


class Ids:
    def __init__(self, value: int = 100) -> None:
        self.value = value

    def __call__(self) -> UUID:
        result = UUID(f"03200000-0000-4000-8000-{self.value:012d}")
        self.value += 1
        return result


def facts(
    role: str = "owner", *, active: bool = True, workspace: UUID = WORKSPACE, version: int = 1
) -> MembershipFacts:
    return MembershipFacts(MEMBERSHIP, USER, workspace, active, (role,), (), version)


def plan_and_catalogs(
    effect: EffectClassification = EffectClassification.READ_ONLY,
) -> tuple[ExecutionPlan, BuiltInCapabilityRegistry, BuiltInDepartmentRegistry]:
    capabilities_data = (
        replace(BUILT_IN_CAPABILITIES[0], effect_classification=effect),
        *BUILT_IN_CAPABILITIES[1:],
    )
    capabilities = BuiltInCapabilityRegistry(capabilities_data)
    departments = BuiltInDepartmentRegistry(capabilities, BUILT_IN_DEPARTMENTS)
    request = PlanningRequest(
        UUID(int=10),
        WORKSPACE,
        UUID(int=11),
        UUID(int=12),
        Actor(ActorType.USER, str(USER)),
        SyntheticPlanningGoal.PREPARE,
        PlanningConstraints(),
        StructuredInput((("value", "safe"),)),
        NOW,
    )
    context = PlanningContext(
        WORKSPACE,
        request.actor,
        request.correlation_id,
        request.causation_id,
        tuple(item.reference for item in BUILT_IN_DEPARTMENTS),
        tuple(item.reference for item in capabilities_data),
        request.constraints,
    )
    proposed = SyntheticPlanner(Ids()).plan(request, context)
    if effect is not EffectClassification.READ_ONLY:
        proposed = replace(
            proposed, steps=(replace(proposed.steps[0], effect_classification=effect),)
        )
    return (
        PlanValidator(capabilities, departments).validate(request, context, proposed),
        capabilities,
        departments,
    )


def evaluation(
    plan: ExecutionPlan,
    capabilities: BuiltInCapabilityRegistry,
    departments: BuiltInDepartmentRegistry,
    *,
    role: str = "owner",
    active: bool = True,
):
    step = plan.steps[0]
    subject = PolicySubject(Actor(ActorType.USER, str(USER)), WORKSPACE, facts(role, active=active))
    action = PolicyAction(
        PolicyOperation.EXECUTE_CAPABILITY,
        plan.plan_id,
        step.step_id,
        step.department,
        step.capability,
        step.work_category,
        step.effect_classification,
    )
    context = PolicyContext(
        WORKSPACE, plan.correlation_id, plan.causation_id, plan.planning_request_id, plan.plan_id
    )
    return SyntheticPolicyEvaluator(capabilities, departments, Ids(300), lambda: NOW).evaluate(
        subject, action, context
    )


def service(
    capabilities: BuiltInCapabilityRegistry, departments: BuiltInDepartmentRegistry
) -> DurableAuthorizationService:
    return DurableAuthorizationService(capabilities, departments, SYNTHETIC_POLICY_SET, Ids(500))


def workflow() -> AuthorizedWorkflow:
    definition = BUILT_IN_WORKFLOWS[0]
    return AuthorizedWorkflow(
        definition.id,
        definition.workflow_type,
        definition.version,
        True,
        tuple(
            AuthorizedWorkflowStep(item.department, item.capability)
            for item in definition.steps
            if item.department and item.capability
        ),
    )


def decision(
    request: ApprovalRequest,
    role: str = "owner",
    *,
    active: bool = True,
    workspace: UUID = WORKSPACE,
    outcome: ApprovalOutcome = ApprovalOutcome.APPROVED,
) -> ApprovalDecision:
    return ApprovalDecision(
        UUID(int=700),
        request.approval_request_id,
        workspace,
        request.action_digest,
        outcome,
        Actor(ActorType.USER, str(USER)),
        facts(role, active=active, workspace=workspace),
        NOW + timedelta(seconds=2),
        request.correlation_id,
        request.causation_id,
    )


class _EvidenceRepository:
    def __init__(self) -> None:
        self.values: dict[tuple[UUID, UUID], AuthorizationEvidence] = {}

    def add(self, workspace_id: UUID, evidence: AuthorizationEvidence) -> None:
        self.values[(workspace_id, evidence.policy_evaluation.decision_id)] = evidence

    def get_by_policy_evaluation(
        self, workspace_id: UUID, policy_evaluation_id: UUID
    ) -> AuthorizationEvidence | None:
        return self.values.get((workspace_id, policy_evaluation_id))


class _RequestRepository:
    def __init__(self) -> None:
        self.by_evidence: dict[tuple[UUID, UUID], ApprovalRequest] = {}
        self.by_key: dict[tuple[UUID, str], ApprovalRequest] = {}

    def add(self, workspace_id: UUID, request: ApprovalRequest, idempotency_key: str) -> None:
        self.by_evidence[(workspace_id, request.authorization_evidence_id)] = request
        self.by_key[(workspace_id, idempotency_key)] = request

    def get(self, workspace_id: UUID, request_id: UUID) -> ApprovalRequest | None:
        return next(
            (
                value
                for (scope, _), value in self.by_evidence.items()
                if scope == workspace_id and value.approval_request_id == request_id
            ),
            None,
        )

    def get_by_evidence(self, workspace_id: UUID, evidence_id: UUID) -> ApprovalRequest | None:
        return self.by_evidence.get((workspace_id, evidence_id))

    def get_by_idempotency_key(
        self, workspace_id: UUID, idempotency_key: str
    ) -> ApprovalRequest | None:
        return self.by_key.get((workspace_id, idempotency_key))

    def save(self, workspace_id: UUID, request: ApprovalRequest, expected_version: int) -> None:
        assert request.version == expected_version + 1
        for key, value in tuple(self.by_evidence.items()):
            if key[0] == workspace_id and value.approval_request_id == request.approval_request_id:
                self.by_evidence[key] = request
        for key, value in tuple(self.by_key.items()):
            if key[0] == workspace_id and value.approval_request_id == request.approval_request_id:
                self.by_key[key] = request


class _DecisionRepository:
    def __init__(self) -> None:
        self.by_request: dict[tuple[UUID, UUID], ApprovalDecision] = {}
        self.by_key: dict[tuple[UUID, str], ApprovalDecision] = {}

    def add(self, workspace_id: UUID, value: ApprovalDecision, idempotency_key: str) -> None:
        self.by_request[(workspace_id, value.approval_request_id)] = value
        self.by_key[(workspace_id, idempotency_key)] = value

    def get_by_request(self, workspace_id: UUID, request_id: UUID) -> ApprovalDecision | None:
        return self.by_request.get((workspace_id, request_id))

    def get_by_idempotency_key(
        self, workspace_id: UUID, idempotency_key: str
    ) -> ApprovalDecision | None:
        return self.by_key.get((workspace_id, idempotency_key))


class _AuthorizationRepository:
    def __init__(self) -> None:
        self.by_key: dict[tuple[UUID, str], ExecutionAuthorization] = {}

    def add(self, workspace_id: UUID, value: ExecutionAuthorization, idempotency_key: str) -> None:
        self.by_key[(workspace_id, idempotency_key)] = value

    def get_by_idempotency_key(
        self, workspace_id: UUID, idempotency_key: str
    ) -> ExecutionAuthorization | None:
        return self.by_key.get((workspace_id, idempotency_key))


class _Appender:
    def __init__(self) -> None:
        self.values: list[object] = []

    def append(self, workspace_id: UUID, value: object) -> None:
        self.values.append((workspace_id, value))

    def add(self, workspace_id: UUID, value: object) -> None:
        self.values.append((workspace_id, value))


class _UnitOfWork:
    def __init__(self) -> None:
        self.authorization_evidence = _EvidenceRepository()
        self.approval_requests = _RequestRepository()
        self.approval_decisions = _DecisionRepository()
        self.execution_authorizations = _AuthorizationRepository()
        self.audit_evidence = _Appender()
        self.outbox = _Appender()
        self.commits = 0

    def __enter__(self) -> _UnitOfWork:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None


class _Diagnostic:
    def __init__(self, constraint_name: str) -> None:
        self.constraint_name = constraint_name


class _UniqueViolation(Exception):
    def __init__(self, constraint_name: str) -> None:
        self.diag = _Diagnostic(constraint_name)


class _FailingUnitOfWork(_UnitOfWork):
    def __init__(self, constraint_name: str) -> None:
        super().__init__()
        self.constraint_name = constraint_name

    def commit(self) -> None:
        raise IntegrityError("INSERT", {}, _UniqueViolation(self.constraint_name))


def test_digest_is_canonical_immutable_and_binds_every_material_change() -> None:
    left = {"b": 2, "a": {"value": "x"}}
    right = {"a": {"value": "x"}, "b": 2}
    assert canonical_json(left) == canonical_json(right)
    assert action_digest(left) == action_digest(right)
    assert action_digest(left) != action_digest({"b": 2, "a": {"value": "y"}})
    plan, capabilities, departments = plan_and_catalogs()
    evidence = service(capabilities, departments).record_evidence(
        plan, evaluation(plan, capabilities, departments)
    )
    with pytest.raises(FrozenInstanceError):
        evidence.action_digest = "0" * 64  # type: ignore[misc]


def test_evidence_rejects_workspace_policy_registry_and_expiry_drift() -> None:
    plan, capabilities, departments = plan_and_catalogs()
    value = evaluation(plan, capabilities, departments)
    durable = service(capabilities, departments)
    with pytest.raises(AuthorizationError, match="does not belong"):
        durable.record_evidence(replace(plan, workspace_id=UUID(int=99)), value)
    with pytest.raises(AuthorizationError, match="Policy reference"):
        durable.record_evidence(
            plan,
            replace(value, policy_set=replace(SYNTHETIC_POLICY_SET, policy_set_id=UUID(int=99))),
        )
    stale_capabilities = BuiltInCapabilityRegistry(
        (replace(BUILT_IN_CAPABILITIES[0], enabled=False), *BUILT_IN_CAPABILITIES[1:])
    )
    with pytest.raises(AuthorizationError, match="stale"):
        service(stale_capabilities, departments).record_evidence(plan, value)
    evidence = durable.record_evidence(plan, value)
    with pytest.raises(AuthorizationError, match="expired"):
        from rightjob.contracts.authorization import require_evidence_current

        require_evidence_current(evidence, value.expires_at)


@pytest.mark.parametrize(
    ("role", "active", "allowed"),
    (
        ("owner", True, True),
        ("admin", True, True),
        ("member", True, False),
        ("owner", False, False),
        ("admin", False, False),
    ),
)
def test_synthetic_approver_authority(role: str, active: bool, allowed: bool) -> None:
    plan, capabilities, departments = plan_and_catalogs(EffectClassification.CONSEQUENTIAL)
    evidence = service(capabilities, departments).record_evidence(
        plan, evaluation(plan, capabilities, departments)
    )
    request = ApprovalRequest.create(UUID(int=600), evidence, NOW + timedelta(seconds=1))
    if allowed:
        assert decision(request, role, active=active).membership.roles == (role,)
    else:
        with pytest.raises(AuthorizationError):
            decision(request, role, active=active)
    cross_workspace = decision(request, "owner", workspace=UUID(int=99))
    with pytest.raises(AuthorizationError, match="request"):
        decide_request(request, cross_workspace)


def test_deny_and_exact_approval_invariants() -> None:
    plan, capabilities, departments = plan_and_catalogs()
    value = replace(
        evaluation(plan, capabilities, departments, active=False), decision=PolicyDecision.DENY
    )
    evidence = service(capabilities, departments).record_evidence(plan, value)
    with pytest.raises(AuthorizationError, match="DENY"):
        ApprovalRequest.create(UUID(int=600), evidence, NOW)
    consequential, capabilities, departments = plan_and_catalogs(EffectClassification.CONSEQUENTIAL)
    durable = service(capabilities, departments)
    evidence = durable.record_evidence(
        consequential, evaluation(consequential, capabilities, departments)
    )
    request = ApprovalRequest.create(UUID(int=600), evidence, NOW + timedelta(seconds=1))
    approved = decision(request)
    resolved = decide_request(request, approved)
    assert resolved.status is ApprovalStatus.APPROVED and resolved.version == 2
    assert decide_request(request, approved, approved) == resolved
    with pytest.raises(AuthorizationError):
        decide_request(
            request,
            replace(approved, outcome=ApprovalOutcome.REJECTED),
            approved,
        )


def test_allow_and_require_approval_plan_authorization_are_atomic_and_bounded() -> None:
    plan, capabilities, departments = plan_and_catalogs()
    durable = service(capabilities, departments)
    evidence = durable.record_evidence(plan, evaluation(plan, capabilities, departments))
    one_step = AuthorizedWorkflow(
        BUILT_IN_WORKFLOWS[0].id,
        "synthetic.one",
        "1.0.0",
        True,
        (AuthorizedWorkflowStep(plan.steps[0].department, plan.steps[0].capability),),
    )
    authorization = durable.issue(
        plan,
        one_step,
        {plan.steps[0].step_id: evidence},
        {},
        {plan.steps[0].step_id: facts()},
        {},
        NOW + timedelta(seconds=1),
    )
    assert authorization.expires_at == evidence.expires_at
    assert authorization.steps[0].approval_decision_id is None
    consequential, capabilities, departments = plan_and_catalogs(EffectClassification.CONSEQUENTIAL)
    durable = service(capabilities, departments)
    evidence = durable.record_evidence(
        consequential, evaluation(consequential, capabilities, departments)
    )
    exact_workflow = AuthorizedWorkflow(
        UUID(int=800),
        "synthetic.one",
        "1.0.0",
        True,
        (
            AuthorizedWorkflowStep(
                consequential.steps[0].department, consequential.steps[0].capability
            ),
        ),
    )
    with pytest.raises(AuthorizationError, match="unresolved"):
        durable.issue(
            consequential,
            exact_workflow,
            {consequential.steps[0].step_id: evidence},
            {},
            {consequential.steps[0].step_id: facts()},
            {},
            NOW + timedelta(seconds=1),
        )
    request = ApprovalRequest.create(UUID(int=600), evidence, NOW + timedelta(seconds=1))
    approved = decision(request)
    resolved = decide_request(request, approved)
    result = durable.issue(
        consequential,
        exact_workflow,
        {consequential.steps[0].step_id: evidence},
        {consequential.steps[0].step_id: (resolved, approved)},
        {consequential.steps[0].step_id: facts()},
        {consequential.steps[0].step_id: facts()},
        NOW + timedelta(seconds=3),
    )
    assert result.steps[0].approval_decision_id == approved.approval_decision_id
    with pytest.raises(AuthorizationError, match="action changed"):
        durable.issue(
            replace(
                consequential,
                steps=(
                    replace(consequential.steps[0], input=StructuredInput((("value", "changed"),))),
                ),
            ),
            exact_workflow,
            {consequential.steps[0].step_id: evidence},
            {consequential.steps[0].step_id: (resolved, approved)},
            {consequential.steps[0].step_id: facts()},
            {consequential.steps[0].step_id: facts()},
            NOW + timedelta(seconds=3),
        )
    with pytest.raises(AuthorizationError, match="stale"):
        durable.issue(
            consequential,
            exact_workflow,
            {consequential.steps[0].step_id: evidence},
            {consequential.steps[0].step_id: (resolved, approved)},
            {consequential.steps[0].step_id: facts(version=2)},
            {consequential.steps[0].step_id: facts()},
            NOW + timedelta(seconds=3),
        )


def test_governance_recorder_reuses_evidence_without_duplicate_events() -> None:
    plan, capabilities, departments = plan_and_catalogs()
    evidence = service(capabilities, departments).record_evidence(
        plan, evaluation(plan, capabilities, departments)
    )
    uow = _UnitOfWork()
    recorder = GovernanceRecorder(lambda: uow, Ids(900))  # type: ignore[arg-type]

    assert recorder.record_evidence(evidence) is evidence
    replay = replace(evidence, authorization_evidence_id=UUID(int=901))
    assert recorder.record_evidence(replay) is evidence
    assert uow.commits == 1
    assert len(uow.audit_evidence.values) == len(uow.outbox.values) == 1

    conflicting = replace(
        replay,
        policy_evaluation=replace(
            replay.policy_evaluation,
            expires_at=replay.expires_at - timedelta(seconds=1),
        ),
    )
    with pytest.raises(IdempotencyConflictError, match="AuthorizationEvidence"):
        recorder.record_evidence(conflicting)


def test_governance_recorder_recovers_only_the_exact_idempotency_race() -> None:
    plan, capabilities, departments = plan_and_catalogs()
    evidence = service(capabilities, departments).record_evidence(
        plan, evaluation(plan, capabilities, departments)
    )
    loser = _FailingUnitOfWork("uq_authorization_evidence_workspace_evaluation")
    winner = _UnitOfWork()
    winner.authorization_evidence.add(WORKSPACE, evidence)
    units = iter((loser, winner))
    recorder = GovernanceRecorder(lambda: next(units), Ids(905))  # type: ignore[arg-type]
    assert (
        recorder.record_evidence(replace(evidence, authorization_evidence_id=UUID(int=906)))
        is evidence
    )

    unrelated = _FailingUnitOfWork("fk_authorization_evidence_workspace")
    recorder = GovernanceRecorder(lambda: unrelated, Ids(907))  # type: ignore[arg-type]
    with pytest.raises(IntegrityError):
        recorder.record_evidence(replace(evidence, authorization_evidence_id=UUID(int=908)))


def test_governance_recorder_reuses_current_request_and_terminal_decision() -> None:
    plan, capabilities, departments = plan_and_catalogs(EffectClassification.CONSEQUENTIAL)
    evidence = service(capabilities, departments).record_evidence(
        plan, evaluation(plan, capabilities, departments)
    )
    request = ApprovalRequest.create(UUID(int=600), evidence, NOW + timedelta(seconds=1))
    approved = decision(request)
    resolved = decide_request(request, approved)
    uow = _UnitOfWork()
    recorder = GovernanceRecorder(lambda: uow, Ids(910))  # type: ignore[arg-type]

    assert recorder.create_approval_request(request, "request-key") is request
    uow.approval_requests.save(WORKSPACE, resolved, 1)
    replay = replace(request, approval_request_id=UUID(int=601))
    assert recorder.create_approval_request(replay, "request-key") is resolved
    with pytest.raises(IdempotencyConflictError, match="identities"):
        recorder.create_approval_request(replay, "different-key")

    assert recorder.record_decision(resolved, approved, "decision-key") is approved
    duplicate = replace(approved, approval_decision_id=UUID(int=701))
    assert recorder.record_decision(resolved, duplicate, "decision-key") is approved
    with pytest.raises(IdempotencyConflictError, match="ApprovalDecision"):
        recorder.record_decision(
            resolved,
            replace(duplicate, outcome=ApprovalOutcome.REJECTED),
            "decision-key",
        )
    assert uow.commits == 2
    assert len(uow.audit_evidence.values) == len(uow.outbox.values) == 2


def test_governance_recorder_reuses_exact_authorization_step_manifest() -> None:
    plan, capabilities, departments = plan_and_catalogs()
    durable = service(capabilities, departments)
    evidence = durable.record_evidence(plan, evaluation(plan, capabilities, departments))
    one_step = AuthorizedWorkflow(
        UUID(int=800),
        "synthetic.one",
        "1.0.0",
        True,
        (AuthorizedWorkflowStep(plan.steps[0].department, plan.steps[0].capability),),
    )
    authorization = durable.issue(
        plan,
        one_step,
        {plan.steps[0].step_id: evidence},
        {},
        {plan.steps[0].step_id: facts()},
        {},
        NOW + timedelta(seconds=1),
    )
    uow = _UnitOfWork()
    recorder = GovernanceRecorder(lambda: uow, Ids(920))  # type: ignore[arg-type]
    actor = Actor(ActorType.SYSTEM, "policy")

    assert recorder.issue_authorization(authorization, actor, "authorization-key") is authorization
    replay = replace(
        authorization,
        execution_authorization_id=UUID(int=921),
        steps=(
            replace(
                authorization.steps[0],
                execution_authorization_step_id=UUID(int=922),
            ),
        ),
    )
    assert recorder.issue_authorization(replay, actor, "authorization-key") is authorization
    with pytest.raises(IdempotencyConflictError, match="ExecutionAuthorization"):
        recorder.issue_authorization(
            replace(replay, steps=(replace(replay.steps[0], action_digest="f" * 64),)),
            actor,
            "authorization-key",
        )
    assert uow.commits == 1
    assert len(uow.audit_evidence.values) == len(uow.outbox.values) == 1


def _unique_columns(record: type[object]) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in record.__table__.constraints  # type: ignore[attr-defined]
        if isinstance(constraint, UniqueConstraint)
    }


def _foreign_key(record: type[object], name: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    constraint = next(
        item
        for item in record.__table__.constraints  # type: ignore[attr-defined]
        if isinstance(item, ForeignKeyConstraint) and item.name == name
    )
    return (
        tuple(element.parent.name for element in constraint.elements),
        tuple(element.target_fullname.rsplit(".", 1)[-1] for element in constraint.elements),
    )


def test_persistence_metadata_binds_exact_evidence_request_and_decision_chain() -> None:
    assert (
        "workspace_id",
        "id",
        "planning_request_id",
        "plan_id",
        "step_id",
        "action_digest",
    ) in _unique_columns(AuthorizationEvidenceRecord)
    assert _foreign_key(ApprovalRequestRecord, "fk_approval_requests_workspace_evidence") == (
        (
            "workspace_id",
            "authorization_evidence_id",
            "planning_request_id",
            "plan_id",
            "step_id",
            "action_digest",
        ),
        (
            "workspace_id",
            "id",
            "planning_request_id",
            "plan_id",
            "step_id",
            "action_digest",
        ),
    )
    assert _foreign_key(
        ExecutionAuthorizationStepRecord,
        "fk_execution_authorization_steps_approval_request",
    ) == (
        ("workspace_id", "approval_request_id", "authorization_evidence_id", "action_digest"),
        ("workspace_id", "id", "authorization_evidence_id", "action_digest"),
    )
    assert _foreign_key(
        ExecutionAuthorizationStepRecord,
        "fk_execution_authorization_steps_approval_decision",
    ) == (
        ("workspace_id", "approval_decision_id", "approval_request_id", "action_digest"),
        ("workspace_id", "id", "approval_request_id", "action_digest"),
    )
    assert all(
        columns[0] == "workspace_id"
        for record in (
            ApprovalRequestRecord,
            ApprovalDecisionRecord,
            ExecutionAuthorizationStepRecord,
        )
        for columns, _ in (
            _foreign_key(record, constraint.name or "")
            for constraint in record.__table__.constraints
            if isinstance(constraint, ForeignKeyConstraint)
        )
    )


def test_persistence_metadata_is_bounded_nonredundant_and_mutability_is_narrow() -> None:
    assert "reason_codes_json" not in ApprovalRequestRecord.__table__.columns
    assert ExecutionAuthorizationStepRecord.__table__.indexes == set()
    assert {
        constraint.name
        for record in (
            AuthorizationEvidenceRecord,
            ApprovalRequestRecord,
            ApprovalDecisionRecord,
            ExecutionAuthorizationRecord,
            ExecutionAuthorizationStepRecord,
        )
        for constraint in record.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    } >= {
        "ck_authorization_evidence_membership_snapshot",
        "ck_approval_requests_resolution",
        "ck_approval_decisions_authority_arrays",
        "ck_execution_authorizations_digest",
        "ck_execution_authorization_steps_approval_pair",
    }
    source = (
        Path(__file__).resolve().parents[2]
        / "packages/core/src/rightjob/policy/infrastructure/repositories.py"
    ).read_text(encoding="utf-8")
    update_fragment = source[source.index("class SqlAlchemyApprovalRequestRepository") :]
    update_fragment = update_fragment[
        : update_fragment.index("class SqlAlchemyApprovalDecisionRepository")
    ]
    assert "status=request.status.value" in update_fragment
    assert "resolved_at=request.resolved_at" in update_fragment
    assert "version=request.version" in update_fragment
