"""Pure authority and idempotent claim rules for bounded revision execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from rightjob.contracts.approval import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRequest,
    ApprovalStatus,
)
from rightjob.contracts.authorization import (
    AuthorizationEvidence,
    action_digest,
    require_evidence_current,
)
from rightjob.contracts.capabilities import CapabilityCatalog
from rightjob.contracts.departments import DepartmentCatalog
from rightjob.contracts.events import (
    Actor,
    ActorType,
    AuditEvidence,
    AuditOutcome,
    DataSensitivity,
    IntegrationEvent,
    JsonValue,
)
from rightjob.contracts.policy import PolicyDecision
from rightjob.contracts.review import ResultValidationOutcome
from rightjob.contracts.revision import (
    QualityGateDecision,
    QualityGateOutcome,
    QualityGateState,
    QualityGateStatus,
)
from rightjob.contracts.revision_execution import (
    RevisionCompletionCommand,
    RevisionExecutionClaim,
    RevisionExecutionCommand,
    RevisionExecutionContractError,
    RevisionExecutionEvidence,
    RevisionExecutionOutcome,
    RevisionExecutionReason,
    RevisionExecutionStatus,
    RevisionLifecycleCommand,
    RevisionLifecycleReason,
    safe_revision_action_snapshot,
)
from rightjob.orchestration.application.repositories import ExecutionUnitOfWork
from rightjob.orchestration.domain import (
    ExecutionRequest,
    ExecutionRun,
    ExecutionStep,
    FailureClassification,
    InitiatorType,
    RequestedStep,
    RunStatus,
    StepStatus,
)

RevisionClaimUnitOfWorkFactory = Callable[[], ExecutionUnitOfWork]


class RevisionExecutionClaimService:
    """Verify fresh authority and prepare one persistence-neutral claim."""

    def __init__(
        self,
        capabilities: CapabilityCatalog,
        departments: DepartmentCatalog,
    ) -> None:
        self._capabilities = capabilities
        self._departments = departments

    def claim(
        self,
        command: RevisionExecutionCommand,
        decision: QualityGateDecision,
        state: QualityGateState,
        authorization: AuthorizationEvidence,
        approval_request: ApprovalRequest | None = None,
        approval_decision: ApprovalDecision | None = None,
        existing_claim: RevisionExecutionClaim | None = None,
    ) -> tuple[RevisionExecutionClaim, RevisionExecutionEvidence]:
        _exact(command, RevisionExecutionCommand, "command")
        _exact(decision, QualityGateDecision, "decision")
        _exact(state, QualityGateState, "state")
        _exact(authorization, AuthorizationEvidence, "authorization")
        if existing_claim is not None:
            _exact(existing_claim, RevisionExecutionClaim, "existing_claim")
            if existing_claim.command.command_id != command.command_id:
                raise RevisionExecutionContractError("reserved cycle is already claimed")
            if existing_claim.command != command:
                raise RevisionExecutionContractError("conflicting duplicate revision command")
            return existing_claim, _evidence(existing_claim, RevisionExecutionOutcome.REPLAYED)

        action = command.action
        if decision.outcome is not QualityGateOutcome.REVISION_REQUIRED:
            raise RevisionExecutionContractError("decision must require revision")
        if state.status is not QualityGateStatus.REVISION_REQUIRED or decision.next_state != state:
            raise RevisionExecutionContractError(
                "quality-gate state is not the exact decision state"
            )
        if command.expected_quality_gate_state_version != state.version:
            raise RevisionExecutionContractError("quality-gate state version is stale")
        evidence = decision.evidence
        bindings = (
            action.workspace_id == state.workspace_id == evidence.workspace_id,
            action.quality_gate_id == state.quality_gate_id == evidence.quality_gate_id,
            action.quality_decision_id == state.last_decision_id == evidence.decision_id,
            action.run_id == state.run_id == evidence.run_id,
            action.step_id == state.step_id == evidence.step_id,
            action.correlation_id == state.correlation_id == evidence.correlation_id,
            action.causation_id == state.causation_id == evidence.causation_id,
            action.capability == state.capability == evidence.capability,
            action.source_artifact == state.last_artifact == evidence.artifact,
            action.quality_policy_key == state.policy_key == evidence.policy_key,
            action.quality_policy_version == state.policy_version == evidence.policy_version,
            action.reserved_cycle
            == state.automated_revision_count
            == evidence.revision_count_after,
            evidence.revision_count_after == evidence.revision_count_before + 1,
        )
        if not all(bindings):
            raise RevisionExecutionContractError(
                "revision action does not bind exact gate evidence"
            )

        try:
            capability = self._capabilities.get_enabled(
                action.capability.capability_key, action.capability.semantic_version
            )
            department = self._departments.get_enabled(
                action.department.department_key, action.department.semantic_version
            )
        except (LookupError, ValueError) as error:
            raise RevisionExecutionContractError(
                "enabled Registry definition is unavailable"
            ) from error
        if capability.reference != action.capability:
            raise RevisionExecutionContractError("Capability Registry identity does not match")
        if (
            department.reference != action.department
            or action.capability not in department.capability_references
        ):
            raise RevisionExecutionContractError("Department Registry ownership does not match")
        policy = capability.quality_gate_policy
        if (
            policy is None
            or policy.policy_key != action.quality_policy_key
            or policy.semantic_version != action.quality_policy_version
        ):
            raise RevisionExecutionContractError("current Capability quality policy does not match")

        self._authorize(command, authorization, approval_request, approval_decision)
        claim = RevisionExecutionClaim(
            command.command_id,
            command,
            command.authorization.action_digest,
            uuid5(NAMESPACE_URL, f"rightjob:revision:request:{command.command_id}"),
            uuid5(NAMESPACE_URL, f"rightjob:revision:run:{command.command_id}"),
            uuid5(NAMESPACE_URL, f"rightjob:revision:step:{command.command_id}"),
            RevisionExecutionStatus.CLAIMED,
            command.issued_at,
            updated_at=command.issued_at,
        )
        return claim, _evidence(claim, RevisionExecutionOutcome.CLAIMED)

    def _authorize(
        self,
        command: RevisionExecutionCommand,
        authorization: AuthorizationEvidence,
        approval_request: ApprovalRequest | None,
        approval_decision: ApprovalDecision | None,
    ) -> None:
        action, reference = command.action, command.authorization
        try:
            require_evidence_current(authorization, command.issued_at)
        except ValueError as error:
            raise RevisionExecutionContractError(
                "fresh authorization evidence is required"
            ) from error
        snapshot = safe_revision_action_snapshot(action)
        digest = action_digest(snapshot)
        evaluation = authorization.policy_evaluation
        if (
            authorization.authorization_evidence_id != reference.authorization_evidence_id
            or authorization.authorization_evidence_id == action.prior_execution_authorization_id
            or authorization.action_snapshot != snapshot
            or authorization.action_digest != digest
            or reference.action_digest != digest
            or reference.policy_evaluation_id != evaluation.decision_id
            or reference.issued_at != evaluation.evaluated_at
            or reference.expires_at != evaluation.expires_at
            or reference.workspace_id != action.workspace_id
        ):
            raise RevisionExecutionContractError(
                "authorization does not bind the exact revision action"
            )
        policy_bindings = (
            evaluation.context.workspace_id == action.workspace_id,
            evaluation.context.planning_request_id == action.planning_request_id,
            evaluation.context.plan_id == action.plan_id,
            evaluation.context.correlation_id == action.correlation_id,
            evaluation.context.causation_id == action.causation_id,
            evaluation.action.plan_id == action.plan_id,
            evaluation.action.step_id == action.step_id,
            evaluation.action.department == action.department,
            evaluation.action.capability == action.capability,
        )
        if not all(policy_bindings) or evaluation.decision is PolicyDecision.DENY:
            raise RevisionExecutionContractError("current Policy evaluation does not permit action")
        if evaluation.decision is PolicyDecision.ALLOW:
            if approval_request is not None or approval_decision is not None:
                raise RevisionExecutionContractError(
                    "Policy ALLOW must not consume unrelated approval"
                )
            if reference.approval_request_id is not None:
                raise RevisionExecutionContractError(
                    "Policy ALLOW authorization must not bind approval"
                )
            return
        if approval_request is None or approval_decision is None:
            raise RevisionExecutionContractError("current Policy requires fresh human approval")
        if (
            approval_request.approval_request_id != reference.approval_request_id
            or approval_decision.approval_decision_id != reference.approval_decision_id
            or approval_request.authorization_evidence_id != authorization.authorization_evidence_id
            or approval_request.workspace_id != action.workspace_id
            or approval_request.action_digest != digest
            or approval_request.status is not ApprovalStatus.APPROVED
            or approval_decision.approval_request_id != approval_request.approval_request_id
            or approval_decision.workspace_id != action.workspace_id
            or approval_decision.action_digest != digest
            or approval_decision.outcome is not ApprovalOutcome.APPROVED
            or approval_decision.decided_at >= command.issued_at
            or command.issued_at >= approval_request.expires_at
        ):
            raise RevisionExecutionContractError("fresh approval does not bind the revision action")


class DurableRevisionExecutionClaimService:
    """Atomically persist one authorized claim and queued execution linkage."""

    def __init__(
        self,
        claims: RevisionExecutionClaimService,
        unit_of_work: RevisionClaimUnitOfWorkFactory,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._claims = claims
        self._unit_of_work = unit_of_work
        self._id = id_factory

    def claim(
        self,
        command: RevisionExecutionCommand,
        authorization: AuthorizationEvidence,
        approval_request: ApprovalRequest | None = None,
        approval_decision: ApprovalDecision | None = None,
    ) -> RevisionExecutionClaim:
        workspace_id = command.action.workspace_id
        with self._unit_of_work() as uow:
            existing = uow.revision_execution_claims.get_by_command(workspace_id, command)
            if existing is not None:
                return existing
            state = uow.quality_gate_states.get(workspace_id, command.action.quality_gate_id)
            decision = uow.quality_gate_decisions.get_current(
                workspace_id,
                command.action.quality_gate_id,
                command.action.quality_decision_id,
            )
            if state is None or decision is None:
                raise RevisionExecutionContractError("current quality-gate evidence is unavailable")
            uow.quality_gate_states.assert_version(
                workspace_id,
                command.action.quality_gate_id,
                command.expected_quality_gate_state_version,
            )
            claim, evidence = self._claims.claim(
                command,
                decision,
                state,
                authorization,
                approval_request,
                approval_decision,
            )
            request, run, step = _execution_linkage(claim, authorization)
            uow.requests.add(workspace_id, request)
            uow.runs.add(workspace_id, run)
            uow.steps.add_all(workspace_id, (step,))
            uow.revision_execution_claims.add(workspace_id, claim)
            self._record(uow, claim, evidence, authorization)
            uow.commit()
            return claim

    def _record(
        self,
        uow: ExecutionUnitOfWork,
        claim: RevisionExecutionClaim,
        evidence: RevisionExecutionEvidence,
        authorization: AuthorizationEvidence,
    ) -> None:
        action = claim.command.action
        payload: dict[str, JsonValue] = {
            "claim_id": str(claim.claim_id),
            "quality_gate_id": str(action.quality_gate_id),
            "quality_decision_id": str(action.quality_decision_id),
            "reserved_cycle": action.reserved_cycle,
            "action_type": action.action_type.value,
            "action_digest": claim.action_digest,
            "capability_key": action.capability.capability_key,
            "capability_version": str(action.capability.semantic_version),
            "source_artifact_id": str(action.source_artifact.artifact_id),
            "source_artifact_version": action.source_artifact.version,
            "source_artifact_sha256": action.source_artifact.sha256,
            "target_artifact_version": action.target_artifact_version,
            "authorization_evidence_id": str(authorization.authorization_evidence_id),
            "execution_request_id": str(claim.execution_request_id),
            "execution_run_id": str(claim.execution_run_id),
            "execution_step_id": str(claim.execution_step_id),
            "status": claim.status.value,
            "reasons": [reason.value for reason in evidence.reasons],
        }
        actor = authorization.policy_evaluation.subject.actor
        uow.audit_evidence.append(
            action.workspace_id,
            AuditEvidence(
                id=self._id(),
                workspace_id=action.workspace_id,
                actor=actor,
                action="revision_execution.claimed",
                resource_type="revision_execution_claim",
                resource_id=str(claim.claim_id),
                outcome=AuditOutcome.SUCCEEDED,
                correlation_id=action.correlation_id,
                causation_id=action.causation_id,
                occurred_at=claim.claimed_at,
                after=payload,
            ),
        )
        uow.outbox.add(
            action.workspace_id,
            IntegrationEvent(
                event_id=self._id(),
                event_type="revision_execution.claimed.v1",
                event_version=1,
                schema_version=1,
                workspace_id=action.workspace_id,
                actor=actor,
                occurred_at=claim.claimed_at,
                correlation_id=action.correlation_id,
                causation_id=action.causation_id,
                producer="orchestration",
                sensitivity=DataSensitivity.INTERNAL,
                payload=payload,
                idempotency_key=f"revision-claim:{claim.command.command_id}",
            ),
        )


def _execution_linkage(
    claim: RevisionExecutionClaim, authorization: AuthorizationEvidence
) -> tuple[ExecutionRequest, ExecutionRun, ExecutionStep]:
    action = claim.command.action
    actor = authorization.policy_evaluation.subject.actor
    step_type = "revision.regenerate_artifact"
    request = ExecutionRequest(
        claim.execution_request_id,
        action.workspace_id,
        action.correlation_id,
        action.causation_id,
        actor,
        InitiatorType.SYSTEM,
        claim.command.authorization,
        action.workflow_definition_id,
        action.workflow_type,
        str(action.workflow_version),
        (RequestedStep(claim.execution_step_id, step_type, 0, f"revision:{claim.claim_id}"),),
        safe_revision_action_snapshot(action),
        claim.claimed_at,
    )
    run = ExecutionRun(
        claim.execution_run_id,
        claim.execution_request_id,
        action.workspace_id,
        action.workflow_definition_id,
        action.workflow_type,
        str(action.workflow_version),
        RunStatus.QUEUED,
        action.correlation_id,
        action.causation_id,
        actor,
        InitiatorType.SYSTEM,
        claim.claimed_at,
    )
    step = ExecutionStep(
        claim.execution_step_id,
        claim.execution_run_id,
        action.workspace_id,
        step_type,
        0,
        StepStatus.PENDING,
        0,
        1,
        f"revision:{claim.claim_id}",
    )
    return request, run, step


def _evidence(
    claim: RevisionExecutionClaim, outcome: RevisionExecutionOutcome
) -> RevisionExecutionEvidence:
    action = claim.command.action
    reason = (
        RevisionExecutionReason.RESERVED_CYCLE_CLAIMED
        if outcome is RevisionExecutionOutcome.CLAIMED
        else RevisionExecutionReason.EXACT_COMMAND_REPLAY
    )
    authority_reason = (
        RevisionExecutionReason.POLICY_APPROVAL_SATISFIED
        if claim.command.authorization.approval_request_id is not None
        else RevisionExecutionReason.POLICY_ALLOWED
    )
    return RevisionExecutionEvidence(
        claim.claim_id,
        claim.command.command_id,
        action.workspace_id,
        action.quality_gate_id,
        action.quality_decision_id,
        action.reserved_cycle,
        claim.command.authorization.authorization_evidence_id,
        claim.action_digest,
        action.source_artifact,
        action.target_artifact_id,
        action.target_artifact_version,
        outcome,
        (reason, authority_reason),
        claim.claimed_at,
    )


def _exact(value: object, expected: type[object], name: str) -> None:
    if type(value) is not expected:
        raise RevisionExecutionContractError(f"{name} must be a {expected.__name__}")


_LIFECYCLE_TRANSITIONS = {
    RevisionExecutionStatus.CLAIMED: frozenset({RevisionExecutionStatus.LAUNCH_PENDING}),
    RevisionExecutionStatus.LAUNCH_PENDING: frozenset(
        {
            RevisionExecutionStatus.RUNNING,
            RevisionExecutionStatus.FAILED,
            RevisionExecutionStatus.RECONCILIATION_REQUIRED,
        }
    ),
    RevisionExecutionStatus.RECONCILIATION_REQUIRED: frozenset(
        {
            RevisionExecutionStatus.RUNNING,
            RevisionExecutionStatus.FAILED,
            RevisionExecutionStatus.CANCELLED,
        }
    ),
    RevisionExecutionStatus.RUNNING: frozenset(
        {
            RevisionExecutionStatus.FAILED,
            RevisionExecutionStatus.CANCELLED,
        }
    ),
    RevisionExecutionStatus.COMPLETED: frozenset(),
    RevisionExecutionStatus.FAILED: frozenset(),
    RevisionExecutionStatus.CANCELLED: frozenset(),
}


class DurableRevisionLifecycleService:
    """Persist lifecycle evidence without launching or executing a workflow."""

    def __init__(
        self,
        unit_of_work: RevisionClaimUnitOfWorkFactory,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._id = id_factory

    def transition(
        self,
        claim_command: RevisionExecutionCommand,
        command: RevisionLifecycleCommand,
    ) -> RevisionExecutionClaim:
        _exact(claim_command, RevisionExecutionCommand, "claim_command")
        _exact(command, RevisionLifecycleCommand, "command")
        with self._unit_of_work() as uow:
            claim = self._load(uow, claim_command, command.workspace_id, command.claim_id)
            digest = action_digest(_lifecycle_snapshot(command))
            replay = _replay(claim, command.command_id, digest)
            if replay:
                return claim
            if command.expected_version != claim.version:
                raise RevisionExecutionContractError("revision lifecycle version is stale")
            if command.workflow_id != _workflow_id(claim):
                raise RevisionExecutionContractError("workflow identity does not match claim")
            if command.target_status not in _LIFECYCLE_TRANSITIONS[claim.status]:
                raise RevisionExecutionContractError("illegal revision lifecycle transition")
            return self._apply_transition(uow, claim, command, digest)

    def prepare_launch(
        self,
        claim_command: RevisionExecutionCommand,
        command: RevisionLifecycleCommand,
        capabilities: CapabilityCatalog,
        departments: DepartmentCatalog,
    ) -> RevisionExecutionClaim:
        """Atomically revalidate exact durable authority before Temporal contact."""
        if command.target_status is not RevisionExecutionStatus.LAUNCH_PENDING:
            raise RevisionExecutionContractError("launch preparation must target LAUNCH_PENDING")
        with self._unit_of_work() as uow:
            claim = self._load(uow, claim_command, command.workspace_id, command.claim_id)
            digest = action_digest(_lifecycle_snapshot(command))
            if _replay(claim, command.command_id, digest):
                return claim
            if claim.status is not RevisionExecutionStatus.CLAIMED:
                raise RevisionExecutionContractError("exact durable CLAIMED authority is required")
            if command.expected_version != claim.version:
                raise RevisionExecutionContractError("revision lifecycle version is stale")
            if command.workflow_id != _workflow_id(claim):
                raise RevisionExecutionContractError("workflow identity does not match claim")
            self._verify_runtime_binding(uow, claim, capabilities, departments)
            run, step = self._execution(uow, claim)
            if run.status is not RunStatus.QUEUED or step.status is not StepStatus.PENDING:
                raise RevisionExecutionContractError("revision launch authority is stale")
            return self._apply_transition(uow, claim, command, digest)

    def verify_runtime_authority(
        self,
        claim_command: RevisionExecutionCommand,
        presented: RevisionExecutionClaim,
        allowed_statuses: frozenset[RevisionExecutionStatus],
        capabilities: CapabilityCatalog,
        departments: DepartmentCatalog,
    ) -> RevisionExecutionClaim:
        """Reload and verify exact durable authority before any Temporal contact."""
        with self._unit_of_work() as uow:
            durable = self._load(
                uow, claim_command, claim_command.action.workspace_id, presented.claim_id
            )
            identity_matches = (
                durable.command == presented.command
                and durable.claim_id == presented.claim_id
                and durable.action_digest == presented.action_digest
                and durable.execution_request_id == presented.execution_request_id
                and durable.execution_run_id == presented.execution_run_id
                and durable.execution_step_id == presented.execution_step_id
                and durable.workflow_id == presented.workflow_id
            )
            if not identity_matches or durable.status not in allowed_statuses:
                raise RevisionExecutionContractError(
                    "exact current durable revision claim is required"
                )
            if durable.status in {
                RevisionExecutionStatus.COMPLETED,
                RevisionExecutionStatus.FAILED,
                RevisionExecutionStatus.CANCELLED,
            }:
                return durable
            if durable.version != presented.version:
                raise RevisionExecutionContractError("revision lifecycle version is stale")
            self._verify_runtime_binding(uow, durable, capabilities, departments)
            return durable

    def _verify_runtime_binding(
        self,
        uow: ExecutionUnitOfWork,
        claim: RevisionExecutionClaim,
        capabilities: CapabilityCatalog,
        departments: DepartmentCatalog,
    ) -> None:
        action = claim.command.action
        state = uow.quality_gate_states.get(action.workspace_id, action.quality_gate_id)
        decision = uow.quality_gate_decisions.get_current(
            action.workspace_id, action.quality_gate_id, action.quality_decision_id
        )
        request = uow.requests.get_revision_binding(action.workspace_id, claim.execution_request_id)
        run, step = self._execution(uow, claim)
        try:
            capability = capabilities.get_enabled(
                action.capability.capability_key, action.capability.semantic_version
            )
            department = departments.get_enabled(
                action.department.department_key, action.department.semantic_version
            )
        except (LookupError, ValueError) as error:
            raise RevisionExecutionContractError(
                "enabled revision runtime definition is unavailable"
            ) from error
        evidence = decision.evidence if decision is not None else None
        if (
            state is None
            or decision is None
            or evidence is None
            or state.status is not QualityGateStatus.REVISION_REQUIRED
            or state.version != claim.command.expected_quality_gate_state_version
            or decision.next_state != state
            or state.last_decision_id != action.quality_decision_id
            or state.automated_revision_count != action.reserved_cycle
            or state.last_artifact != action.source_artifact
            or evidence.workspace_id != action.workspace_id
            or evidence.quality_gate_id != action.quality_gate_id
            or evidence.decision_id != action.quality_decision_id
            or evidence.run_id != action.run_id
            or evidence.step_id != action.step_id
            or evidence.capability != action.capability
            or evidence.artifact != action.source_artifact
            or evidence.revision_count_after != action.reserved_cycle
            or request is None
            or request.workspace_id != action.workspace_id
            or request.revision_authorization_evidence_id
            != claim.command.authorization.authorization_evidence_id
            or request.workflow_definition_id != action.workflow_definition_id
            or request.workflow_type != action.workflow_type
            or request.workflow_version != str(action.workflow_version)
            or request.input != safe_revision_action_snapshot(action)
            or run.execution_request_id != claim.execution_request_id
            or step.run_id != claim.execution_run_id
            or capability.reference != action.capability
            or department.reference != action.department
            or action.capability not in department.capability_references
        ):
            raise RevisionExecutionContractError("revision launch authority is stale")

    def _apply_transition(
        self,
        uow: ExecutionUnitOfWork,
        claim: RevisionExecutionClaim,
        command: RevisionLifecycleCommand,
        digest: str,
    ) -> RevisionExecutionClaim:
        next_claim = _transition_claim(claim, command, digest)
        self._transition_execution(uow, claim, next_claim, command.occurred_at)
        uow.revision_execution_claims.save(
            command.workspace_id, next_claim, command.expected_version
        )
        self._record_transition(uow, next_claim, command.command_id, command.occurred_at)
        uow.commit()
        return next_claim

    def complete(
        self,
        claim_command: RevisionExecutionCommand,
        command: RevisionCompletionCommand,
    ) -> RevisionExecutionClaim:
        _exact(claim_command, RevisionExecutionCommand, "claim_command")
        _exact(command, RevisionCompletionCommand, "command")
        with self._unit_of_work() as uow:
            claim = self._load(uow, claim_command, command.workspace_id, command.claim_id)
            digest = action_digest(_completion_snapshot(command))
            if _replay(claim, command.command_id, digest):
                return claim
            if claim.status not in {
                RevisionExecutionStatus.RUNNING,
                RevisionExecutionStatus.RECONCILIATION_REQUIRED,
            }:
                raise RevisionExecutionContractError("revision is not eligible to complete")
            if command.expected_version != claim.version:
                raise RevisionExecutionContractError("revision lifecycle version is stale")
            self._validate_completion(claim, command)
            completed = replace(
                claim,
                status=RevisionExecutionStatus.COMPLETED,
                lifecycle_reason=None,
                completed_at=command.completed_at,
                result_artifact=command.submission.result_artifact,
                result_validation_evidence_id=command.validation.validation_id,
                last_lifecycle_command_id=command.command_id,
                last_lifecycle_command_digest=digest,
                version=claim.version + 1,
                updated_at=command.completed_at,
            )
            run, step = self._execution(uow, claim)
            if claim.status is RevisionExecutionStatus.RECONCILIATION_REQUIRED:
                completed_run = replace(
                    run,
                    status=RunStatus.SUCCEEDED,
                    completed_at=command.completed_at,
                    version=run.version + 1,
                )
                completed_step = replace(
                    step,
                    status=StepStatus.SUCCEEDED,
                    completed_at=command.completed_at,
                    output_evidence_ref=f"validation:{command.validation.validation_id}",
                    version=step.version + 1,
                )
            else:
                completed_run = run.transition(RunStatus.SUCCEEDED, command.completed_at)
                completed_step = step.transition(
                    StepStatus.SUCCEEDED,
                    command.completed_at,
                    evidence_ref=f"validation:{command.validation.validation_id}",
                )
            state = uow.quality_gate_states.get(
                command.workspace_id, claim.command.action.quality_gate_id
            )
            decision = uow.quality_gate_decisions.get_current(
                command.workspace_id,
                claim.command.action.quality_gate_id,
                claim.command.action.quality_decision_id,
            )
            if state is None or decision is None:
                raise RevisionExecutionContractError("quality-gate completion state is unavailable")
            if (
                state.status is not QualityGateStatus.REVISION_REQUIRED
                or state.version != claim.command.expected_quality_gate_state_version
                or state.automated_revision_count != claim.command.action.reserved_cycle
                or state.last_decision_id != claim.command.action.quality_decision_id
            ):
                raise RevisionExecutionContractError("quality-gate completion binding is stale")
            awaiting_review = replace(
                state,
                status=QualityGateStatus.AWAITING_REVIEW,
                last_artifact=command.submission.result_artifact,
                last_validation_id=command.validation.validation_id,
                version=state.version + 1,
                updated_at=command.completed_at,
            )
            uow.revision_execution_claims.save(
                command.workspace_id, completed, command.expected_version
            )
            uow.runs.save(command.workspace_id, completed_run, run.version)
            uow.steps.save(command.workspace_id, completed_step, step.version)
            uow.quality_gate_states.save(
                command.workspace_id,
                awaiting_review,
                decision.evidence.minimum_score,
                state.version,
            )
            self._record_transition(uow, completed, command.command_id, command.completed_at)
            uow.commit()
            return completed

    @staticmethod
    def _load(
        uow: ExecutionUnitOfWork,
        claim_command: RevisionExecutionCommand,
        workspace_id: UUID,
        claim_id: UUID,
    ) -> RevisionExecutionClaim:
        if workspace_id != claim_command.action.workspace_id:
            raise RevisionExecutionContractError("lifecycle Workspace does not match claim")
        claim = uow.revision_execution_claims.get_by_command(workspace_id, claim_command)
        if claim is None or claim.claim_id != claim_id:
            raise RevisionExecutionContractError("durable revision claim is unavailable")
        return claim

    @staticmethod
    def _execution(
        uow: ExecutionUnitOfWork, claim: RevisionExecutionClaim
    ) -> tuple[ExecutionRun, ExecutionStep]:
        workspace_id = claim.command.action.workspace_id
        run = uow.runs.get(workspace_id, claim.execution_run_id)
        step = uow.steps.get(workspace_id, claim.execution_step_id)
        if (
            run is None
            or step is None
            or run.execution_request_id != claim.execution_request_id
            or step.run_id != claim.execution_run_id
        ):
            raise RevisionExecutionContractError("revision execution linkage does not match")
        return run, step

    def _transition_execution(
        self,
        uow: ExecutionUnitOfWork,
        claim: RevisionExecutionClaim,
        next_claim: RevisionExecutionClaim,
        occurred_at: datetime,
    ) -> None:
        status = next_claim.status
        if status is RevisionExecutionStatus.LAUNCH_PENDING:
            return
        if (
            status is RevisionExecutionStatus.FAILED
            and next_claim.lifecycle_reason is RevisionLifecycleReason.LAUNCH_REJECTED
        ):
            run, step = self._execution(uow, claim)
            if (
                run.status is not RunStatus.QUEUED
                or step.status is not StepStatus.PENDING
                or run.started_at is not None
                or step.started_at is not None
            ):
                raise RevisionExecutionContractError(
                    "pre-launch rejection requires queued unstarted execution linkage"
                )
            failed_run = replace(
                run,
                status=RunStatus.FAILED,
                completed_at=occurred_at,
                version=run.version + 1,
            )
            failed_step = replace(
                step,
                status=StepStatus.FAILED,
                completed_at=occurred_at,
                failure_classification=FailureClassification.INFRASTRUCTURE_EXHAUSTED,
                version=step.version + 1,
            )
            workspace_id = claim.command.action.workspace_id
            uow.runs.save(workspace_id, failed_run, run.version)
            uow.steps.save(workspace_id, failed_step, step.version)
            return
        run, step = self._execution(uow, claim)
        if status is RevisionExecutionStatus.RECONCILIATION_REQUIRED:
            changed_run = run.transition(RunStatus.RECONCILIATION_REQUIRED, occurred_at)
            uow.runs.save(claim.command.action.workspace_id, changed_run, run.version)
            return
        if claim.status is RevisionExecutionStatus.RECONCILIATION_REQUIRED and status in {
            RevisionExecutionStatus.FAILED,
            RevisionExecutionStatus.CANCELLED,
        }:
            run_status = (
                RunStatus.FAILED
                if status is RevisionExecutionStatus.FAILED
                else RunStatus.CANCELLED
            )
            step_status = (
                StepStatus.FAILED
                if status is RevisionExecutionStatus.FAILED
                else StepStatus.CANCELLED
            )
            changed_run = run.transition(run_status, occurred_at)
            changed_step = replace(
                step,
                status=step_status,
                completed_at=occurred_at,
                failure_classification=(
                    FailureClassification.INFRASTRUCTURE_EXHAUSTED
                    if step_status is StepStatus.FAILED
                    else None
                ),
                version=step.version + 1,
            )
            workspace_id = claim.command.action.workspace_id
            uow.runs.save(workspace_id, changed_run, run.version)
            uow.steps.save(workspace_id, changed_step, step.version)
            return
        if status is RevisionExecutionStatus.RUNNING:
            changed_run = run.transition(RunStatus.RUNNING, occurred_at)
            changed_step = step.transition(StepStatus.RUNNING, occurred_at)
        elif status is RevisionExecutionStatus.FAILED:
            changed_run = run.transition(RunStatus.FAILED, occurred_at)
            changed_step = step.transition(
                StepStatus.FAILED,
                occurred_at,
                failure=FailureClassification.INFRASTRUCTURE_EXHAUSTED,
            )
        elif status is RevisionExecutionStatus.CANCELLED:
            changed_run = run.transition(RunStatus.CANCELLED, occurred_at)
            changed_step = step.transition(StepStatus.CANCELLED, occurred_at)
        else:
            return
        uow.runs.save(claim.command.action.workspace_id, changed_run, run.version)
        uow.steps.save(claim.command.action.workspace_id, changed_step, step.version)

    @staticmethod
    def _validate_completion(
        claim: RevisionExecutionClaim, command: RevisionCompletionCommand
    ) -> None:
        action, submission, validation = (
            claim.command.action,
            command.submission,
            command.validation,
        )
        if command.workflow_id != claim.workflow_id or command.workflow_id != _workflow_id(claim):
            raise RevisionExecutionContractError("completion workflow identity does not match")
        if (
            submission.claim_id != claim.claim_id
            or submission.workspace_id != action.workspace_id
            or submission.quality_gate_id != action.quality_gate_id
            or submission.run_id != claim.execution_run_id
            or submission.step_id != claim.execution_step_id
            or submission.capability != action.capability
            or submission.source_artifact != action.source_artifact
            or submission.result_artifact.artifact_id != action.target_artifact_id
            or submission.result_artifact.version != action.target_artifact_version
            or submission.validation_id != validation.validation_id
        ):
            raise RevisionExecutionContractError("revision artifact submission does not match")
        provenance = validation.provenance
        if (
            validation.outcome is not ResultValidationOutcome.PASSED
            or provenance.workspace_id != action.workspace_id
            or provenance.run_id != claim.execution_run_id
            or provenance.step_id != claim.execution_step_id
            or provenance.correlation_id != action.correlation_id
            or provenance.causation_id != action.causation_id
            or provenance.capability != action.capability
            or provenance.artifact != submission.result_artifact
            or command.completed_at < validation.validated_at
            or validation.validated_at < submission.submitted_at
        ):
            raise RevisionExecutionContractError("passed result validation does not bind revision")

    def _record_transition(
        self,
        uow: ExecutionUnitOfWork,
        claim: RevisionExecutionClaim,
        command_id: UUID,
        occurred_at: datetime,
    ) -> None:
        action = claim.command.action
        payload: dict[str, JsonValue] = {
            "claim_id": str(claim.claim_id),
            "quality_gate_id": str(action.quality_gate_id),
            "quality_decision_id": str(action.quality_decision_id),
            "cycle": action.reserved_cycle,
            "workflow_id": claim.workflow_id,
            "status": claim.status.value,
            "reason": claim.lifecycle_reason.value if claim.lifecycle_reason else None,
            "result_artifact_id": (
                str(claim.result_artifact.artifact_id) if claim.result_artifact else None
            ),
            "result_artifact_version": (
                claim.result_artifact.version if claim.result_artifact else None
            ),
            "result_artifact_sha256": (
                claim.result_artifact.sha256 if claim.result_artifact else None
            ),
            "validation_id": (
                str(claim.result_validation_evidence_id)
                if claim.result_validation_evidence_id
                else None
            ),
            "version": claim.version,
        }
        actor = Actor(ActorType.SYSTEM, "orchestration")
        uow.audit_evidence.append(
            action.workspace_id,
            AuditEvidence(
                id=self._id(),
                workspace_id=action.workspace_id,
                actor=actor,
                action="revision_execution.lifecycle_changed",
                resource_type="revision_execution_claim",
                resource_id=str(claim.claim_id),
                outcome=AuditOutcome.SUCCEEDED,
                correlation_id=action.correlation_id,
                causation_id=action.causation_id,
                occurred_at=occurred_at,
                after=payload,
            ),
        )
        uow.outbox.add(
            action.workspace_id,
            IntegrationEvent(
                event_id=self._id(),
                event_type="revision_execution.lifecycle_changed.v1",
                event_version=1,
                schema_version=1,
                occurred_at=occurred_at,
                workspace_id=action.workspace_id,
                actor=actor,
                correlation_id=action.correlation_id,
                causation_id=action.causation_id,
                producer="orchestration",
                sensitivity=DataSensitivity.INTERNAL,
                payload=payload,
                idempotency_key=f"revision-lifecycle:{command_id}",
            ),
        )


def _workflow_id(claim: RevisionExecutionClaim) -> str:
    action = claim.command.action
    return (
        f"revision:{action.workspace_id}:{action.quality_gate_id}:"
        f"{action.quality_decision_id}:{action.reserved_cycle}"
    )


def _lifecycle_snapshot(command: RevisionLifecycleCommand) -> dict[str, JsonValue]:
    return {
        "command_id": str(command.command_id),
        "workspace_id": str(command.workspace_id),
        "claim_id": str(command.claim_id),
        "expected_version": command.expected_version,
        "target_status": command.target_status.value,
        "workflow_id": command.workflow_id,
        "reason": command.reason.value if command.reason else None,
        "occurred_at": command.occurred_at.isoformat(),
    }


def _completion_snapshot(command: RevisionCompletionCommand) -> dict[str, JsonValue]:
    artifact = command.submission.result_artifact
    return {
        "command_id": str(command.command_id),
        "workspace_id": str(command.workspace_id),
        "claim_id": str(command.claim_id),
        "expected_version": command.expected_version,
        "workflow_id": command.workflow_id,
        "artifact_id": str(artifact.artifact_id),
        "artifact_version": artifact.version,
        "artifact_sha256": artifact.sha256,
        "validation_id": str(command.validation.validation_id),
        "completed_at": command.completed_at.isoformat(),
    }


def _replay(claim: RevisionExecutionClaim, command_id: UUID, digest: str) -> bool:
    if claim.last_lifecycle_command_id != command_id:
        return False
    if claim.last_lifecycle_command_digest != digest:
        raise RevisionExecutionContractError("conflicting lifecycle command replay")
    return True


def _transition_claim(
    claim: RevisionExecutionClaim, command: RevisionLifecycleCommand, digest: str
) -> RevisionExecutionClaim:
    status = command.target_status
    reason = command.reason
    if status is RevisionExecutionStatus.RECONCILIATION_REQUIRED:
        if reason is not RevisionLifecycleReason.LAUNCH_OUTCOME_UNKNOWN:
            raise RevisionExecutionContractError("reconciliation requires unknown launch reason")
    elif status is RevisionExecutionStatus.FAILED:
        if claim.status is RevisionExecutionStatus.LAUNCH_PENDING:
            allowed = reason is RevisionLifecycleReason.LAUNCH_REJECTED
        elif claim.status is RevisionExecutionStatus.RECONCILIATION_REQUIRED:
            allowed = reason in {
                RevisionLifecycleReason.WORKFLOW_FAILED,
                RevisionLifecycleReason.WORKFLOW_TERMINATED,
                RevisionLifecycleReason.WORKFLOW_TIMED_OUT,
            }
        else:
            allowed = reason in {
                RevisionLifecycleReason.EXECUTION_FAILED,
                RevisionLifecycleReason.VALIDATION_FAILED,
            }
        if not allowed:
            raise RevisionExecutionContractError("failure requires a closed failure reason")
    elif status is RevisionExecutionStatus.CANCELLED:
        allowed_cancel = (
            RevisionLifecycleReason.WORKFLOW_CANCELLED
            if claim.status is RevisionExecutionStatus.RECONCILIATION_REQUIRED
            else RevisionLifecycleReason.CANCELLED_BY_REQUEST
        )
        if reason is not allowed_cancel:
            raise RevisionExecutionContractError("cancellation requires cancellation reason")
    elif reason is not None:
        raise RevisionExecutionContractError("non-exception transition cannot contain reason")
    return replace(
        claim,
        status=status,
        workflow_id=command.workflow_id,
        lifecycle_reason=reason,
        last_lifecycle_command_id=command.command_id,
        last_lifecycle_command_digest=digest,
        version=claim.version + 1,
        updated_at=command.occurred_at,
        launch_pending_at=(
            command.occurred_at
            if status is RevisionExecutionStatus.LAUNCH_PENDING
            else claim.launch_pending_at
        ),
        running_at=(
            command.occurred_at if status is RevisionExecutionStatus.RUNNING else claim.running_at
        ),
        failed_at=(
            command.occurred_at if status is RevisionExecutionStatus.FAILED else claim.failed_at
        ),
        cancelled_at=(
            command.occurred_at
            if status is RevisionExecutionStatus.CANCELLED
            else claim.cancelled_at
        ),
        reconciliation_required_at=(
            command.occurred_at
            if status is RevisionExecutionStatus.RECONCILIATION_REQUIRED
            else claim.reconciliation_required_at
        ),
    )
