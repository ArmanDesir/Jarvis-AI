from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from rightjob.contracts.approval import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRequest,
    decide_request,
)
from rightjob.contracts.authorization import AuthorizationEvidence, action_digest
from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.policy import (
    MembershipFacts,
    PolicyAction,
    PolicyContext,
    PolicyDecision,
    PolicyEvaluation,
    PolicyOperation,
    PolicyReasonCode,
    PolicyRuleReference,
    PolicySetReference,
    PolicySubject,
)
from rightjob.contracts.review import (
    ArtifactReference,
    CapabilityResult,
    EvidenceReference,
    ResultProvenance,
    ResultValidationEvidence,
    ResultValidationOutcome,
    ResultValidationReason,
    ValidationCriteriaReference,
    canonical_result_payload,
    result_digest,
)
from rightjob.contracts.revision import (
    QualityGateCommand,
    QualityGateDecision,
    QualityGateDecisionEvidence,
    QualityGateOutcome,
    QualityGateReason,
    QualityGateState,
    QualityGateStatus,
)
from rightjob.contracts.revision_execution import (
    RevisionActionType,
    RevisionArtifactSubmission,
    RevisionCompletionCommand,
    RevisionExecutionAuthorizationReference,
    RevisionExecutionCommand,
    RevisionExecutionContractError,
    RevisionExecutionOutcome,
    RevisionExecutionStatus,
    RevisionLifecycleCommand,
    RevisionLifecycleReason,
    SafeRevisionAction,
    revision_workflow_id,
    safe_revision_action_snapshot,
)
from rightjob.orchestration.application.repositories import RevisionExecutionRequestBinding
from rightjob.orchestration.application.revision_execution import (
    DurableRevisionExecutionClaimService,
    DurableRevisionLifecycleService,
    RevisionExecutionClaimService,
)
from rightjob.orchestration.domain import RunStatus, StepStatus
from rightjob.registry.catalog import VERSION_1, BuiltInCapabilityRegistry
from rightjob.registry.departments import BuiltInDepartmentRegistry

NOW = datetime(2026, 8, 28, 10, tzinfo=UTC)


def U(value: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{value:012d}")


WORKSPACE, GATE, DECISION_ID, PLAN_REQUEST, PLAN = (U(i) for i in range(1, 6))
RUN, STEP, CORRELATION, SOURCE_AUTH, COMMAND = (U(i) for i in range(6, 11))
ARTIFACT = U(11)
CAPABILITIES = BuiltInCapabilityRegistry()
DEPARTMENTS = BuiltInDepartmentRegistry(CAPABILITIES)
CAPABILITY = CAPABILITIES.get_enabled("fake.verify", VERSION_1)
DEPARTMENT = DEPARTMENTS.get_enabled("foundation.operations", VERSION_1)
SOURCE = ArtifactReference(ARTIFACT, 1, "a" * 64)


def action(*, cycle: int = 1) -> SafeRevisionAction:
    policy = CAPABILITY.quality_gate_policy
    assert policy is not None
    return SafeRevisionAction(
        WORKSPACE,
        GATE,
        DECISION_ID,
        cycle,
        PLAN_REQUEST,
        PLAN,
        RUN,
        STEP,
        CORRELATION,
        None,
        DEPARTMENT.reference,
        CAPABILITY.reference,
        SOURCE,
        ARTIFACT,
        2,
        policy.policy_key,
        policy.semantic_version,
        RevisionActionType.REGENERATE_ARTIFACT,
        U(12),
        "revision.artifact",
        VERSION_1,
        SOURCE_AUTH,
    )


def policy_evaluation(
    item: SafeRevisionAction, decision: PolicyDecision = PolicyDecision.ALLOW
) -> PolicyEvaluation:
    membership = MembershipFacts(U(20), U(21), WORKSPACE, True, ("owner",), (), 1)
    policy_set = PolicySetReference(U(22), "synthetic.policy", VERSION_1)
    return PolicyEvaluation(
        U(23),
        PolicySubject(Actor(ActorType.USER, str(U(21))), WORKSPACE, membership),
        PolicyAction(
            operation=PolicyOperation.EXECUTE_CAPABILITY,
            plan_id=PLAN,
            step_id=STEP,
            department=item.department,
            capability=item.capability,
            work_category=DEPARTMENT.work_categories[1],
            effect_classification=CAPABILITY.effect_classification,
        ),
        PolicyContext(WORKSPACE, CORRELATION, None, PLAN_REQUEST, PLAN),
        decision,
        (PolicyReasonCode.SYNTHETIC_NONCONSEQUENTIAL_ALLOWED,),
        policy_set,
        (PolicyRuleReference(policy_set, "synthetic.rule", VERSION_1),),
        NOW,
        NOW + timedelta(minutes=10),
    )


def authorized_command(
    item: SafeRevisionAction | None = None,
    *,
    decision: PolicyDecision = PolicyDecision.ALLOW,
    command_id: UUID = COMMAND,
) -> tuple[RevisionExecutionCommand, AuthorizationEvidence]:
    item = item or action()
    snapshot = safe_revision_action_snapshot(item)
    evaluation = policy_evaluation(item, decision)
    evidence = AuthorizationEvidence(U(24), evaluation, snapshot, action_digest(snapshot))
    reference = RevisionExecutionAuthorizationReference(
        evidence.authorization_evidence_id,
        item.workspace_id,
        evidence.action_digest,
        evaluation.decision_id,
        evaluation.evaluated_at,
        evaluation.expires_at,
    )
    return RevisionExecutionCommand(
        command_id, item, reference, 1, NOW + timedelta(minutes=1)
    ), evidence


def gate(item: SafeRevisionAction | None = None) -> tuple[QualityGateDecision, QualityGateState]:
    item = item or action()
    qcommand = QualityGateCommand(
        DECISION_ID,
        GATE,
        WORKSPACE,
        RUN,
        STEP,
        CORRELATION,
        None,
        SOURCE,
        Actor(ActorType.SYSTEM, "quality-gate"),
        None,
        NOW,
    )
    evidence = QualityGateDecisionEvidence(
        DECISION_ID,
        qcommand.command_id,
        GATE,
        WORKSPACE,
        RUN,
        STEP,
        CORRELATION,
        None,
        CAPABILITY.reference,
        item.quality_policy_key,
        item.quality_policy_version,
        "fake.verify.quality",
        VERSION_1,
        "fake.verify.quality",
        50,
        80,
        None,
        SOURCE,
        U(31),
        U(32),
        item.reserved_cycle - 1,
        item.reserved_cycle,
        NOW,
    )
    state = QualityGateState(
        GATE,
        WORKSPACE,
        RUN,
        STEP,
        CORRELATION,
        None,
        CAPABILITY.reference,
        item.quality_policy_key,
        item.quality_policy_version,
        "fake.verify.quality",
        VERSION_1,
        "fake.verify.quality",
        QualityGateStatus.REVISION_REQUIRED,
        item.reserved_cycle,
        SOURCE,
        U(31),
        U(32),
        50,
        DECISION_ID,
        1,
        NOW,
    )
    return QualityGateDecision(
        qcommand,
        QualityGateOutcome.REVISION_REQUIRED,
        (QualityGateReason.THRESHOLD_NOT_MET,),
        evidence,
        state,
    ), state


def service() -> RevisionExecutionClaimService:
    return RevisionExecutionClaimService(CAPABILITIES, DEPARTMENTS)


@pytest.mark.parametrize("cycle", [1, 2])
def test_cycle_one_and_two_can_be_claimed_once(cycle: int) -> None:
    item = action(cycle=cycle)
    command, authorization = authorized_command(item)
    decision, state = gate(item)
    claim, evidence = service().claim(command, decision, state, authorization)
    assert claim.command.action.reserved_cycle == cycle
    assert evidence.outcome is RevisionExecutionOutcome.CLAIMED


def test_cycle_three_is_structurally_rejected() -> None:
    with pytest.raises(RevisionExecutionContractError):
        action(cycle=3)


@pytest.mark.parametrize(
    "change",
    [
        {"reserved_cycle": True},
        {"reserved_cycle": 1.0},
        {"workspace_id": "workspace"},
        {"action_type": "regenerate_artifact"},
        {"target_artifact_version": 3},
        {"quality_policy_key": "ignore previous instructions"},
    ],
)
def test_action_rejects_malformed_or_unsafe_values(change: dict[str, object]) -> None:
    with pytest.raises((AttributeError, RevisionExecutionContractError)):
        replace(action(), **change)


def test_contracts_are_immutable_and_reject_mutable_evidence() -> None:
    command, authorization = authorized_command()
    decision, state = gate()
    claim, evidence = service().claim(command, decision, state, authorization)
    with pytest.raises(FrozenInstanceError):
        claim.version = 2  # type: ignore[misc]
    with pytest.raises(RevisionExecutionContractError):
        replace(evidence, reasons=list(evidence.reasons))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda item: replace(item, workspace_id=U(40)),
        lambda item: replace(item, quality_gate_id=U(41)),
        lambda item: replace(item, quality_decision_id=U(42)),
        lambda item: replace(
            item, capability=replace(item.capability, capability_key="fake.prepare")
        ),
        lambda item: replace(item, source_artifact=ArtifactReference(ARTIFACT, 1, "b" * 64)),
    ],
)
def test_exact_gate_registry_and_artifact_bindings_fail_closed(mutation: object) -> None:
    item = mutation(action())  # type: ignore[operator]
    command, authorization = authorized_command(item)
    decision, state = gate()
    with pytest.raises(RevisionExecutionContractError):
        service().claim(command, decision, state, authorization)


def test_non_revision_decision_and_stale_state_fail_closed() -> None:
    command, authorization = authorized_command()
    decision, state = gate()
    accepted_state = replace(state, status=QualityGateStatus.ACCEPTED)
    with pytest.raises(RevisionExecutionContractError):
        service().claim(
            command,
            replace(
                decision,
                outcome=QualityGateOutcome.ACCEPTED,
                next_state=accepted_state,
            ),
            accepted_state,
            authorization,
        )
    with pytest.raises(RevisionExecutionContractError, match="stale"):
        service().claim(
            replace(command, expected_quality_gate_state_version=2), decision, state, authorization
        )


def test_prior_or_changed_authorization_cannot_authorize_revision() -> None:
    command, authorization = authorized_command()
    decision, state = gate()
    with pytest.raises(RevisionExecutionContractError, match="exact revision action"):
        service().claim(
            command,
            decision,
            state,
            replace(authorization, authorization_evidence_id=SOURCE_AUTH),
        )
    changed = dict(authorization.action_snapshot)
    changed["reserved_cycle"] = 2
    changed_authorization = AuthorizationEvidence(
        U(24), authorization.policy_evaluation, changed, action_digest(changed)
    )
    with pytest.raises(RevisionExecutionContractError, match="exact revision action"):
        service().claim(command, decision, state, changed_authorization)


def test_policy_deny_and_required_approval_without_approval_fail_closed() -> None:
    decision, state = gate()
    for policy_decision in (PolicyDecision.DENY, PolicyDecision.REQUIRE_APPROVAL):
        command, authorization = authorized_command(decision=policy_decision)
        with pytest.raises(RevisionExecutionContractError):
            service().claim(command, decision, state, authorization)


def test_require_approval_succeeds_only_with_exact_fresh_human_approval() -> None:
    command, authorization = authorized_command(decision=PolicyDecision.REQUIRE_APPROVAL)
    request = ApprovalRequest.create(U(60), authorization, NOW + timedelta(seconds=10))
    evaluation = authorization.policy_evaluation
    membership = evaluation.subject.membership
    assert membership is not None
    approval = ApprovalDecision(
        U(61),
        request.approval_request_id,
        WORKSPACE,
        authorization.action_digest,
        ApprovalOutcome.APPROVED,
        evaluation.subject.actor,
        membership,
        NOW + timedelta(seconds=20),
        CORRELATION,
        None,
    )
    request = decide_request(request, approval)
    command = replace(
        command,
        authorization=replace(
            command.authorization,
            approval_request_id=request.approval_request_id,
            approval_decision_id=approval.approval_decision_id,
        ),
    )
    decision, state = gate()
    claim, _ = service().claim(command, decision, state, authorization, request, approval)
    assert claim.command.authorization.approval_decision_id == approval.approval_decision_id


def test_exact_replay_is_idempotent_and_conflicting_replay_fails() -> None:
    command, authorization = authorized_command()
    decision, state = gate()
    claim, _ = service().claim(command, decision, state, authorization)
    replay, evidence = service().claim(
        command, decision, state, authorization, existing_claim=claim
    )
    assert replay is claim
    assert evidence.outcome is RevisionExecutionOutcome.REPLAYED
    conflicting, other_authorization = authorized_command(command_id=COMMAND)
    conflicting = replace(conflicting, issued_at=conflicting.issued_at + timedelta(seconds=1))
    with pytest.raises(RevisionExecutionContractError, match="conflicting duplicate"):
        service().claim(conflicting, decision, state, other_authorization, existing_claim=claim)


def test_safe_snapshot_and_evidence_exclude_untrusted_text_and_authority_claims() -> None:
    command, authorization = authorized_command()
    decision, state = gate()
    _, evidence = service().claim(command, decision, state, authorization)
    rendered = repr((safe_revision_action_snapshot(command.action), evidence))
    for unsafe in (
        "reviewer prose",
        "ignore previous",
        "raw model output",
        "api_key=",
        "curl http",
        "human approved",
    ):
        assert unsafe not in rendered.lower()


def test_revision_artifact_must_advance_and_change_hash() -> None:
    valid = RevisionArtifactSubmission(
        COMMAND,
        WORKSPACE,
        GATE,
        RUN,
        STEP,
        CAPABILITY.reference,
        SOURCE,
        ArtifactReference(ARTIFACT, 2, "b" * 64),
        U(50),
        NOW,
    )
    assert valid.result_artifact.version == 2
    with pytest.raises(RevisionExecutionContractError):
        replace(valid, result_artifact=ArtifactReference(ARTIFACT, 2, SOURCE.sha256))


def test_claim_does_not_refund_phase_219_reservation() -> None:
    command, authorization = authorized_command()
    decision, state = gate()
    claim, _ = service().claim(command, decision, state, authorization)
    assert claim.command.action.reserved_cycle == state.automated_revision_count == 1


class _Repo:
    def __init__(self, value: object | None = None) -> None:
        self.value = value
        self.items: list[object] = []

    def get(self, *args: object) -> object | None:
        return self.value

    def get_current(self, *args: object) -> object | None:
        return self.value

    def get_by_command(self, workspace_id: UUID, command: object) -> object | None:
        return self.value

    def assert_version(self, *args: object) -> None:
        return None

    def add(self, *args: object) -> None:
        self.items.append(args[-1])

    def add_all(self, workspace_id: UUID, values: tuple[object, ...]) -> None:
        self.items.extend(values)

    def get_revision_binding(
        self, workspace_id: UUID, request_id: UUID
    ) -> RevisionExecutionRequestBinding | None:
        if not self.items:
            return None
        request = self.items[0]
        assert hasattr(request, "authorization") and hasattr(request, "input")
        return RevisionExecutionRequestBinding(
            request.execution_id,
            request.workspace_id,
            request.authorization.authorization_evidence_id,
            request.workflow_definition_id,
            request.workflow_type,
            request.workflow_version,
            request.input,
        )

    def append(self, *args: object) -> None:
        self.items.append(args[-1])

    def save(self, *args: object) -> None:
        self.value = args[1]
        self.items.append(args[1])


class _Uow:
    def __init__(self, decision: QualityGateDecision, state: QualityGateState) -> None:
        self.quality_gate_states = _Repo(state)
        self.quality_gate_decisions = _Repo(decision)
        self.revision_execution_claims = _Repo()
        self.requests = _Repo()
        self.runs = _Repo()
        self.steps = _Repo()
        self.audit_evidence = _Repo()
        self.outbox = _Repo()
        self.committed = False

    def __enter__(self) -> _Uow:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def commit(self) -> None:
        self.committed = True


def test_durable_claim_atomically_prepares_execution_audit_and_outbox_without_launch() -> None:
    command, authorization = authorized_command()
    decision, state = gate()
    uow = _Uow(decision, state)
    durable = DurableRevisionExecutionClaimService(service(), lambda: uow, id_factory=lambda: U(90))
    claim = durable.claim(command, authorization)
    assert uow.committed
    assert uow.revision_execution_claims.items == [claim]
    assert len(uow.requests.items) == len(uow.runs.items) == len(uow.steps.items) == 1
    assert len(uow.audit_evidence.items) == len(uow.outbox.items) == 1
    assert uow.runs.items[0].status.value == "queued"  # type: ignore[union-attr]
    assert uow.steps.items[0].status.value == "pending"  # type: ignore[union-attr]


def test_durable_exact_replay_creates_no_duplicate_side_effects() -> None:
    command, authorization = authorized_command()
    decision, state = gate()
    first = _Uow(decision, state)
    claim = DurableRevisionExecutionClaimService(service(), lambda: first).claim(
        command, authorization
    )
    replay = _Uow(decision, state)
    replay.revision_execution_claims.value = claim
    returned = DurableRevisionExecutionClaimService(service(), lambda: replay).claim(
        command, authorization
    )
    assert returned == claim
    assert not replay.committed
    assert replay.requests.items == replay.audit_evidence.items == replay.outbox.items == []


def _claimed_runtime() -> tuple[
    RevisionExecutionCommand, QualityGateDecision, QualityGateState, _Uow, object
]:
    command, authorization = authorized_command()
    decision, state = gate()
    claimed_uow = _Uow(decision, state)
    claim = DurableRevisionExecutionClaimService(service(), lambda: claimed_uow).claim(
        command, authorization
    )
    return command, decision, state, claimed_uow, claim


def _lifecycle_uow(
    decision: QualityGateDecision, state: QualityGateState, claimed: _Uow, claim: object
) -> _Uow:
    uow = _Uow(decision, state)
    uow.revision_execution_claims.value = claim
    uow.requests.items = list(claimed.requests.items)
    uow.runs.value = claimed.runs.items[0]
    uow.steps.value = claimed.steps.items[0]
    return uow


def _valid_result(claim: object) -> tuple[RevisionArtifactSubmission, ResultValidationEvidence]:
    assert hasattr(claim, "command")
    payload = canonical_result_payload({"verified": True})
    artifact = ArtifactReference(ARTIFACT, 2, result_digest(payload))
    provenance = ResultProvenance(
        WORKSPACE,
        claim.execution_run_id,
        claim.execution_step_id,
        CORRELATION,
        None,
        CAPABILITY.reference,
        CAPABILITY.output_contract,
        artifact,
        NOW + timedelta(minutes=4),
    )
    validation = ResultValidationEvidence(
        U(101),
        CapabilityResult(provenance, payload),
        ValidationCriteriaReference("result.contract", VERSION_1),
        ResultValidationOutcome.PASSED,
        (ResultValidationReason.ACCEPTED,),
        (EvidenceReference("result.contract", "validation:passed"),),
        NOW + timedelta(minutes=5),
    )
    submission = RevisionArtifactSubmission(
        claim.claim_id,
        WORKSPACE,
        GATE,
        claim.execution_run_id,
        claim.execution_step_id,
        CAPABILITY.reference,
        SOURCE,
        artifact,
        validation.validation_id,
        NOW + timedelta(minutes=4),
    )
    return submission, validation


def test_durable_lifecycle_transitions_and_exact_replay_are_safe() -> None:
    command, decision, state, claimed_uow, claim = _claimed_runtime()
    workflow_id = revision_workflow_id(command.action)
    uow = _lifecycle_uow(decision, state, claimed_uow, claim)
    service = DurableRevisionLifecycleService(lambda: uow, id_factory=lambda: U(102))
    launch = RevisionLifecycleCommand(
        U(103),
        WORKSPACE,
        claim.claim_id,
        1,
        RevisionExecutionStatus.LAUNCH_PENDING,
        workflow_id,
        NOW + timedelta(minutes=2),
    )
    launched = service.transition(command, launch)
    assert launched.status is RevisionExecutionStatus.LAUNCH_PENDING
    before = (len(uow.audit_evidence.items), len(uow.outbox.items))
    assert service.transition(command, launch) == launched
    assert (len(uow.audit_evidence.items), len(uow.outbox.items)) == before


def test_reconciliation_running_and_terminal_rules_fail_closed() -> None:
    command, decision, state, claimed_uow, claim = _claimed_runtime()
    workflow_id = revision_workflow_id(command.action)
    uow = _lifecycle_uow(decision, state, claimed_uow, claim)
    lifecycle = DurableRevisionLifecycleService(lambda: uow)
    launched = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            U(104),
            WORKSPACE,
            claim.claim_id,
            1,
            RevisionExecutionStatus.LAUNCH_PENDING,
            workflow_id,
            NOW + timedelta(minutes=2),
        ),
    )
    reconciled = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            U(105),
            WORKSPACE,
            claim.claim_id,
            launched.version,
            RevisionExecutionStatus.RECONCILIATION_REQUIRED,
            workflow_id,
            NOW + timedelta(minutes=3),
            RevisionLifecycleReason.LAUNCH_OUTCOME_UNKNOWN,
        ),
    )
    running = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            U(106),
            WORKSPACE,
            claim.claim_id,
            reconciled.version,
            RevisionExecutionStatus.RUNNING,
            workflow_id,
            NOW + timedelta(minutes=4),
        ),
    )
    assert running.running_at is not None and running.lifecycle_reason is None
    with pytest.raises(RevisionExecutionContractError, match="illegal"):
        lifecycle.transition(
            command,
            RevisionLifecycleCommand(
                U(107),
                WORKSPACE,
                claim.claim_id,
                running.version,
                RevisionExecutionStatus.LAUNCH_PENDING,
                workflow_id,
                NOW + timedelta(minutes=5),
            ),
        )


def test_completion_requires_passed_exact_result_and_preserves_reservation() -> None:
    command, decision, state, claimed_uow, claim = _claimed_runtime()
    workflow_id = revision_workflow_id(command.action)
    uow = _lifecycle_uow(decision, state, claimed_uow, claim)
    lifecycle = DurableRevisionLifecycleService(lambda: uow, id_factory=lambda: U(108))
    launched = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            U(109),
            WORKSPACE,
            claim.claim_id,
            1,
            RevisionExecutionStatus.LAUNCH_PENDING,
            workflow_id,
            NOW + timedelta(minutes=2),
        ),
    )
    running = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            U(110),
            WORKSPACE,
            claim.claim_id,
            launched.version,
            RevisionExecutionStatus.RUNNING,
            workflow_id,
            NOW + timedelta(minutes=3),
        ),
    )
    submission, validation = _valid_result(running)
    completed = lifecycle.complete(
        command,
        RevisionCompletionCommand(
            U(111),
            WORKSPACE,
            claim.claim_id,
            running.version,
            workflow_id,
            submission,
            validation,
            NOW + timedelta(minutes=6),
        ),
    )
    assert completed.status is RevisionExecutionStatus.COMPLETED
    assert uow.quality_gate_states.value.status is QualityGateStatus.AWAITING_REVIEW
    assert uow.quality_gate_states.value.automated_revision_count == 1
    assert uow.runs.value.status.value == "succeeded"
    assert uow.steps.value.status.value == "succeeded"
    assert completed.result_validation_evidence_id == validation.validation_id


@pytest.mark.parametrize(
    ("terminal", "reason"),
    [
        (RevisionExecutionStatus.FAILED, RevisionLifecycleReason.EXECUTION_FAILED),
        (RevisionExecutionStatus.CANCELLED, RevisionLifecycleReason.CANCELLED_BY_REQUEST),
    ],
)
def test_failed_and_cancelled_are_terminal_without_reservation_refund(
    terminal: RevisionExecutionStatus, reason: RevisionLifecycleReason
) -> None:
    command, decision, state, claimed_uow, claim = _claimed_runtime()
    workflow_id = revision_workflow_id(command.action)
    uow = _lifecycle_uow(decision, state, claimed_uow, claim)
    lifecycle = DurableRevisionLifecycleService(lambda: uow)
    launched = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            U(113),
            WORKSPACE,
            claim.claim_id,
            1,
            RevisionExecutionStatus.LAUNCH_PENDING,
            workflow_id,
            NOW + timedelta(minutes=2),
        ),
    )
    running = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            U(114),
            WORKSPACE,
            claim.claim_id,
            launched.version,
            RevisionExecutionStatus.RUNNING,
            workflow_id,
            NOW + timedelta(minutes=3),
        ),
    )
    ended = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            U(115),
            WORKSPACE,
            claim.claim_id,
            running.version,
            terminal,
            workflow_id,
            NOW + timedelta(minutes=4),
            reason,
        ),
    )
    assert ended.status is terminal
    assert state.automated_revision_count == ended.command.action.reserved_cycle == 1
    with pytest.raises(RevisionExecutionContractError, match="illegal"):
        lifecycle.transition(
            command,
            RevisionLifecycleCommand(
                U(116),
                WORKSPACE,
                claim.claim_id,
                ended.version,
                RevisionExecutionStatus.RUNNING,
                workflow_id,
                NOW + timedelta(minutes=5),
            ),
        )


def test_definite_launch_rejection_fails_without_fabricating_running() -> None:
    command, decision, state, claimed_uow, claim = _claimed_runtime()
    workflow_id = revision_workflow_id(command.action)
    uow = _lifecycle_uow(decision, state, claimed_uow, claim)
    lifecycle = DurableRevisionLifecycleService(lambda: uow)
    with pytest.raises(RevisionExecutionContractError, match="illegal"):
        lifecycle.transition(
            command,
            RevisionLifecycleCommand(
                U(117),
                WORKSPACE,
                claim.claim_id,
                claim.version,
                RevisionExecutionStatus.FAILED,
                workflow_id,
                NOW + timedelta(minutes=2),
                RevisionLifecycleReason.LAUNCH_REJECTED,
            ),
        )
    launched = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            U(118),
            WORKSPACE,
            claim.claim_id,
            claim.version,
            RevisionExecutionStatus.LAUNCH_PENDING,
            workflow_id,
            NOW + timedelta(minutes=2),
        ),
    )
    rejection = RevisionLifecycleCommand(
        U(119),
        WORKSPACE,
        claim.claim_id,
        launched.version,
        RevisionExecutionStatus.FAILED,
        workflow_id,
        NOW + timedelta(minutes=3),
        RevisionLifecycleReason.LAUNCH_REJECTED,
    )
    failed = lifecycle.transition(command, rejection)
    assert failed.failed_at == rejection.occurred_at
    assert failed.running_at is None
    assert failed.launch_pending_at == launched.launch_pending_at
    assert uow.runs.value.status is RunStatus.FAILED
    assert uow.steps.value.status is StepStatus.FAILED
    assert uow.runs.value.started_at is None
    assert uow.steps.value.started_at is None
    assert state.automated_revision_count == failed.command.action.reserved_cycle == 1
    effects = (len(uow.audit_evidence.items), len(uow.outbox.items))
    assert lifecycle.transition(command, rejection) == failed
    assert (len(uow.audit_evidence.items), len(uow.outbox.items)) == effects
    with pytest.raises(RevisionExecutionContractError, match="conflicting"):
        lifecycle.transition(
            command, replace(rejection, occurred_at=rejection.occurred_at + timedelta(seconds=1))
        )
    with pytest.raises(RevisionExecutionContractError):
        replace(failed, failed_at=None)
    with pytest.raises(RevisionExecutionContractError):
        replace(failed, launch_pending_at=None)


def test_launch_rejected_reason_is_rejected_after_running_or_reconciliation() -> None:
    command, decision, state, claimed_uow, claim = _claimed_runtime()
    workflow_id = revision_workflow_id(command.action)
    uow = _lifecycle_uow(decision, state, claimed_uow, claim)
    lifecycle = DurableRevisionLifecycleService(lambda: uow)
    launched = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            U(120),
            WORKSPACE,
            claim.claim_id,
            1,
            RevisionExecutionStatus.LAUNCH_PENDING,
            workflow_id,
            NOW + timedelta(minutes=2),
        ),
    )
    running = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            U(121),
            WORKSPACE,
            claim.claim_id,
            launched.version,
            RevisionExecutionStatus.RUNNING,
            workflow_id,
            NOW + timedelta(minutes=3),
        ),
    )
    with pytest.raises(RevisionExecutionContractError, match="closed failure"):
        lifecycle.transition(
            command,
            RevisionLifecycleCommand(
                U(122),
                WORKSPACE,
                claim.claim_id,
                running.version,
                RevisionExecutionStatus.FAILED,
                workflow_id,
                NOW + timedelta(minutes=4),
                RevisionLifecycleReason.LAUNCH_REJECTED,
            ),
        )
    with pytest.raises(RevisionExecutionContractError):
        replace(running, lifecycle_reason=RevisionLifecycleReason.LAUNCH_REJECTED)
