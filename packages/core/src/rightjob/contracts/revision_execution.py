"""Published contracts for authorized bounded revision execution claims."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from rightjob.contracts.capabilities import CapabilityReference, SemanticVersion
from rightjob.contracts.departments import DepartmentReference
from rightjob.contracts.events import JsonValue
from rightjob.contracts.review import (
    ArtifactReference,
    ResultValidationEvidence,
)

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class RevisionExecutionContractError(ValueError):
    """Revision execution input is malformed, stale, or inconsistent."""


class RevisionActionType(StrEnum):
    REGENERATE_ARTIFACT = "regenerate_artifact"


class RevisionExecutionStatus(StrEnum):
    CLAIMED = "claimed"
    LAUNCH_PENDING = "launch_pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    CANCELLED = "cancelled"


class RevisionExecutionOutcome(StrEnum):
    CLAIMED = "claimed"
    REPLAYED = "replayed"


class RevisionExecutionReason(StrEnum):
    RESERVED_CYCLE_CLAIMED = "reserved_cycle_claimed"
    EXACT_COMMAND_REPLAY = "exact_command_replay"
    POLICY_ALLOWED = "policy_allowed"
    POLICY_APPROVAL_SATISFIED = "policy_approval_satisfied"


class RevisionLifecycleReason(StrEnum):
    LAUNCH_REJECTED = "launch_rejected"
    LAUNCH_OUTCOME_UNKNOWN = "launch_outcome_unknown"
    EXECUTION_FAILED = "execution_failed"
    VALIDATION_FAILED = "validation_failed"
    CANCELLED_BY_REQUEST = "cancelled_by_request"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    WORKFLOW_TERMINATED = "workflow_terminated"
    WORKFLOW_TIMED_OUT = "workflow_timed_out"


@dataclass(frozen=True, slots=True)
class SafeRevisionAction:
    workspace_id: UUID
    quality_gate_id: UUID
    quality_decision_id: UUID
    reserved_cycle: int
    planning_request_id: UUID
    plan_id: UUID
    run_id: UUID
    step_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    department: DepartmentReference
    capability: CapabilityReference
    source_artifact: ArtifactReference
    target_artifact_id: UUID
    target_artifact_version: int
    quality_policy_key: str
    quality_policy_version: SemanticVersion
    action_type: RevisionActionType
    workflow_definition_id: UUID
    workflow_type: str
    workflow_version: SemanticVersion
    prior_execution_authorization_id: UUID

    def __post_init__(self) -> None:
        _uuids(
            self.workspace_id,
            self.quality_gate_id,
            self.quality_decision_id,
            self.planning_request_id,
            self.plan_id,
            self.run_id,
            self.step_id,
            self.correlation_id,
            self.target_artifact_id,
            self.workflow_definition_id,
            self.prior_execution_authorization_id,
        )
        if self.causation_id is not None:
            _uuids(self.causation_id)
        _integer("reserved_cycle", self.reserved_cycle, 1, 2)
        _exact("department", self.department, DepartmentReference)
        _exact("capability", self.capability, CapabilityReference)
        _artifact(self.source_artifact)
        if self.target_artifact_id != self.source_artifact.artifact_id:
            raise RevisionExecutionContractError("revision must target the same artifact identity")
        _integer("target_artifact_version", self.target_artifact_version, 2, 2_147_483_647)
        if self.target_artifact_version != self.source_artifact.version + 1:
            raise RevisionExecutionContractError(
                "revision target must be the next artifact version"
            )
        _key("quality_policy_key", self.quality_policy_key)
        _version("quality_policy_version", self.quality_policy_version)
        _exact("action_type", self.action_type, RevisionActionType)
        _key("workflow_type", self.workflow_type)
        _version("workflow_version", self.workflow_version)


@dataclass(frozen=True, slots=True)
class RevisionExecutionAuthorizationReference:
    authorization_evidence_id: UUID
    workspace_id: UUID
    action_digest: str
    policy_evaluation_id: UUID
    issued_at: datetime
    expires_at: datetime
    approval_request_id: UUID | None = None
    approval_decision_id: UUID | None = None

    def __post_init__(self) -> None:
        _uuids(
            self.authorization_evidence_id,
            self.workspace_id,
            self.policy_evaluation_id,
        )
        _digest("action_digest", self.action_digest)
        _aware("issued_at", self.issued_at)
        _aware("expires_at", self.expires_at)
        if self.expires_at <= self.issued_at:
            raise RevisionExecutionContractError("authorization must expire after issuance")
        if (self.approval_request_id is None) != (self.approval_decision_id is None):
            raise RevisionExecutionContractError("approval identities must be supplied together")
        if self.approval_request_id is not None:
            _uuids(self.approval_request_id, self.approval_decision_id)


@dataclass(frozen=True, slots=True)
class RevisionExecutionCommand:
    command_id: UUID
    action: SafeRevisionAction
    authorization: RevisionExecutionAuthorizationReference
    expected_quality_gate_state_version: int
    issued_at: datetime

    def __post_init__(self) -> None:
        _uuids(self.command_id)
        _exact("action", self.action, SafeRevisionAction)
        _exact("authorization", self.authorization, RevisionExecutionAuthorizationReference)
        _integer(
            "expected_quality_gate_state_version",
            self.expected_quality_gate_state_version,
            1,
            2_147_483_647,
        )
        _aware("issued_at", self.issued_at)
        if self.authorization.workspace_id != self.action.workspace_id:
            raise RevisionExecutionContractError("authorization Workspace does not match action")


@dataclass(frozen=True, slots=True)
class RevisionExecutionClaim:
    claim_id: UUID
    command: RevisionExecutionCommand
    action_digest: str
    execution_request_id: UUID
    execution_run_id: UUID
    execution_step_id: UUID
    status: RevisionExecutionStatus
    claimed_at: datetime
    version: int = 1
    workflow_id: str | None = None
    lifecycle_reason: RevisionLifecycleReason | None = None
    launch_pending_at: datetime | None = None
    running_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    cancelled_at: datetime | None = None
    reconciliation_required_at: datetime | None = None
    result_artifact: ArtifactReference | None = None
    result_validation_evidence_id: UUID | None = None
    last_lifecycle_command_id: UUID | None = None
    last_lifecycle_command_digest: str | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        _uuids(
            self.claim_id,
            self.execution_request_id,
            self.execution_run_id,
            self.execution_step_id,
        )
        _exact("command", self.command, RevisionExecutionCommand)
        _digest("action_digest", self.action_digest)
        _exact("status", self.status, RevisionExecutionStatus)
        _aware("claimed_at", self.claimed_at)
        _integer("version", self.version, 1, 2_147_483_647)
        updated_at = self.updated_at or self.claimed_at
        _aware("updated_at", updated_at)
        if updated_at < self.claimed_at:
            raise RevisionExecutionContractError("claim update cannot predate claim")
        if self.status is RevisionExecutionStatus.CLAIMED:
            if self.workflow_id is not None or self.launch_pending_at is not None:
                raise RevisionExecutionContractError("CLAIMED cannot own workflow launch state")
        else:
            _workflow_id(self.workflow_id, self.command.action)
            if self.launch_pending_at is None:
                raise RevisionExecutionContractError("launched lifecycle requires launch timestamp")
        for name, value in (
            ("launch_pending_at", self.launch_pending_at),
            ("running_at", self.running_at),
            ("completed_at", self.completed_at),
            ("failed_at", self.failed_at),
            ("cancelled_at", self.cancelled_at),
            ("reconciliation_required_at", self.reconciliation_required_at),
        ):
            if value is not None:
                _aware(name, value)
                if value < self.claimed_at:
                    raise RevisionExecutionContractError("lifecycle timestamp predates claim")
        _lifecycle_shape(self)
        if (self.last_lifecycle_command_id is None) != (self.last_lifecycle_command_digest is None):
            raise RevisionExecutionContractError("lifecycle command identity must be paired")
        if self.last_lifecycle_command_id is not None:
            _uuids(self.last_lifecycle_command_id)
            assert self.last_lifecycle_command_digest is not None
            _digest("lifecycle command digest", self.last_lifecycle_command_digest)


@dataclass(frozen=True, slots=True)
class RevisionLifecycleCommand:
    command_id: UUID
    workspace_id: UUID
    claim_id: UUID
    expected_version: int
    target_status: RevisionExecutionStatus
    workflow_id: str
    occurred_at: datetime
    reason: RevisionLifecycleReason | None = None

    def __post_init__(self) -> None:
        _uuids(self.command_id, self.workspace_id, self.claim_id)
        _integer("expected_version", self.expected_version, 1, 2_147_483_647)
        _exact("target_status", self.target_status, RevisionExecutionStatus)
        if self.target_status in (
            RevisionExecutionStatus.CLAIMED,
            RevisionExecutionStatus.COMPLETED,
        ):
            raise RevisionExecutionContractError("target status requires a specialized boundary")
        _bounded("workflow_id", self.workflow_id, 1, 255)
        _aware("occurred_at", self.occurred_at)
        if self.reason is not None:
            _exact("reason", self.reason, RevisionLifecycleReason)


@dataclass(frozen=True, slots=True)
class RevisionCompletionCommand:
    command_id: UUID
    workspace_id: UUID
    claim_id: UUID
    expected_version: int
    workflow_id: str
    submission: RevisionArtifactSubmission
    validation: ResultValidationEvidence
    completed_at: datetime

    def __post_init__(self) -> None:
        _uuids(self.command_id, self.workspace_id, self.claim_id)
        _integer("expected_version", self.expected_version, 1, 2_147_483_647)
        _bounded("workflow_id", self.workflow_id, 1, 255)
        _exact("submission", self.submission, RevisionArtifactSubmission)
        _exact("validation", self.validation, ResultValidationEvidence)
        _aware("completed_at", self.completed_at)


@dataclass(frozen=True, slots=True)
class RevisionExecutionEvidence:
    claim_id: UUID
    command_id: UUID
    workspace_id: UUID
    quality_gate_id: UUID
    quality_decision_id: UUID
    reserved_cycle: int
    authorization_evidence_id: UUID
    action_digest: str
    source_artifact: ArtifactReference
    target_artifact_id: UUID
    target_artifact_version: int
    outcome: RevisionExecutionOutcome
    reasons: tuple[RevisionExecutionReason, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        _uuids(
            self.claim_id,
            self.command_id,
            self.workspace_id,
            self.quality_gate_id,
            self.quality_decision_id,
            self.authorization_evidence_id,
            self.target_artifact_id,
        )
        _integer("reserved_cycle", self.reserved_cycle, 1, 2)
        _digest("action_digest", self.action_digest)
        _artifact(self.source_artifact)
        _integer("target_artifact_version", self.target_artifact_version, 2, 2_147_483_647)
        _exact("outcome", self.outcome, RevisionExecutionOutcome)
        if type(self.reasons) is not tuple or not 1 <= len(self.reasons) <= 4:
            raise RevisionExecutionContractError("reasons must be a bounded nonempty tuple")
        if any(type(reason) is not RevisionExecutionReason for reason in self.reasons):
            raise RevisionExecutionContractError("reasons contain an invalid member")
        if len(set(self.reasons)) != len(self.reasons):
            raise RevisionExecutionContractError("reasons must be unique")
        _aware("recorded_at", self.recorded_at)


@dataclass(frozen=True, slots=True)
class RevisionArtifactSubmission:
    claim_id: UUID
    workspace_id: UUID
    quality_gate_id: UUID
    run_id: UUID
    step_id: UUID
    capability: CapabilityReference
    source_artifact: ArtifactReference
    result_artifact: ArtifactReference
    validation_id: UUID
    submitted_at: datetime

    def __post_init__(self) -> None:
        _uuids(
            self.claim_id,
            self.workspace_id,
            self.quality_gate_id,
            self.run_id,
            self.step_id,
            self.validation_id,
        )
        _exact("capability", self.capability, CapabilityReference)
        _artifact(self.source_artifact)
        _artifact(self.result_artifact)
        if self.result_artifact.artifact_id != self.source_artifact.artifact_id:
            raise RevisionExecutionContractError("result artifact identity must not change")
        if self.result_artifact.version != self.source_artifact.version + 1:
            raise RevisionExecutionContractError("result must be the next artifact version")
        if self.result_artifact.sha256 == self.source_artifact.sha256:
            raise RevisionExecutionContractError("revision result must change artifact SHA-256")
        _aware("submitted_at", self.submitted_at)


def safe_revision_action_snapshot(action: SafeRevisionAction) -> dict[str, JsonValue]:
    """Project only closed identities needed to authorize one revision action."""
    _exact("action", action, SafeRevisionAction)
    return {
        "schema_version": 1,
        "action_type": action.action_type.value,
        "workspace_id": str(action.workspace_id),
        "quality_gate_id": str(action.quality_gate_id),
        "quality_decision_id": str(action.quality_decision_id),
        "reserved_cycle": action.reserved_cycle,
        "planning_request_id": str(action.planning_request_id),
        "plan_id": str(action.plan_id),
        "run_id": str(action.run_id),
        "step_id": str(action.step_id),
        "correlation_id": str(action.correlation_id),
        "causation_id": str(action.causation_id) if action.causation_id else None,
        "department": {
            "id": str(action.department.department_definition_id),
            "key": action.department.department_key,
            "version": str(action.department.semantic_version),
        },
        "capability": {
            "id": str(action.capability.capability_definition_id),
            "key": action.capability.capability_key,
            "version": str(action.capability.semantic_version),
        },
        "source_artifact": {
            "id": str(action.source_artifact.artifact_id),
            "version": action.source_artifact.version,
            "sha256": action.source_artifact.sha256,
        },
        "target_artifact": {
            "id": str(action.target_artifact_id),
            "version": action.target_artifact_version,
        },
        "quality_policy": {
            "key": action.quality_policy_key,
            "version": str(action.quality_policy_version),
        },
        "execution_target": {
            "workflow_definition_id": str(action.workflow_definition_id),
            "workflow_type": action.workflow_type,
            "workflow_version": str(action.workflow_version),
        },
        "prior_execution_authorization_id": str(action.prior_execution_authorization_id),
    }


def _exact(name: str, value: object, expected: type[object]) -> None:
    if type(value) is not expected:
        raise RevisionExecutionContractError(f"{name} must be a {expected.__name__}")


def _uuids(*values: UUID | None) -> None:
    if any(type(value) is not UUID or value.int == 0 for value in values):
        raise RevisionExecutionContractError("identifiers must be non-nil UUIDs")


def _aware(name: str, value: datetime) -> None:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise RevisionExecutionContractError(f"{name} must be timezone-aware")


def _integer(name: str, value: int, minimum: int, maximum: int) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise RevisionExecutionContractError(f"{name} must be an integer in range")


def _key(name: str, value: str) -> None:
    if type(value) is not str or re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", value) is None:
        raise RevisionExecutionContractError(f"{name} must be a canonical key")


def _version(name: str, value: SemanticVersion) -> None:
    _exact(name, value, SemanticVersion)
    if type(value.prerelease) is not tuple or type(value.build) is not tuple:
        raise RevisionExecutionContractError(f"{name} must be immutable")
    try:
        SemanticVersion.parse(str(value))
    except (TypeError, ValueError) as error:
        raise RevisionExecutionContractError(f"{name} must be semantic") from error


def _artifact(value: ArtifactReference) -> None:
    _exact("artifact", value, ArtifactReference)
    _uuids(value.artifact_id)
    _integer("artifact version", value.version, 1, 2_147_483_647)
    _digest("artifact SHA-256", value.sha256)


def _digest(name: str, value: str) -> None:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise RevisionExecutionContractError(f"{name} must be lowercase SHA-256")


def revision_workflow_id(action: SafeRevisionAction) -> str:
    """Return the one deterministic workflow identity for a reserved revision."""
    _exact("action", action, SafeRevisionAction)
    return (
        f"revision:{action.workspace_id}:{action.quality_gate_id}:"
        f"{action.quality_decision_id}:{action.reserved_cycle}"
    )


def _workflow_id(value: str | None, action: SafeRevisionAction) -> None:
    if value != revision_workflow_id(action):
        raise RevisionExecutionContractError("workflow identity does not bind the revision")


def _bounded(name: str, value: str, minimum: int, maximum: int) -> None:
    if type(value) is not str or not minimum <= len(value) <= maximum:
        raise RevisionExecutionContractError(f"{name} must be bounded text")


def _lifecycle_shape(claim: RevisionExecutionClaim) -> None:
    status = claim.status
    required = {
        RevisionExecutionStatus.RUNNING: claim.running_at,
        RevisionExecutionStatus.COMPLETED: claim.completed_at,
        RevisionExecutionStatus.FAILED: claim.failed_at,
        RevisionExecutionStatus.CANCELLED: claim.cancelled_at,
        RevisionExecutionStatus.RECONCILIATION_REQUIRED: claim.reconciliation_required_at,
    }
    if status in required and required[status] is None:
        raise RevisionExecutionContractError("lifecycle status requires its timestamp")
    reason_required = status in (
        RevisionExecutionStatus.FAILED,
        RevisionExecutionStatus.CANCELLED,
        RevisionExecutionStatus.RECONCILIATION_REQUIRED,
    )
    if reason_required != (claim.lifecycle_reason is not None):
        raise RevisionExecutionContractError("lifecycle status/reason do not match")
    if claim.lifecycle_reason is not None:
        _exact("lifecycle_reason", claim.lifecycle_reason, RevisionLifecycleReason)
    if claim.lifecycle_reason is RevisionLifecycleReason.LAUNCH_REJECTED and (
        status is not RevisionExecutionStatus.FAILED or claim.running_at is not None
    ):
        raise RevisionExecutionContractError("launch rejection must fail before running")
    recovery_reasons = {
        RevisionLifecycleReason.WORKFLOW_FAILED,
        RevisionLifecycleReason.WORKFLOW_CANCELLED,
        RevisionLifecycleReason.WORKFLOW_TERMINATED,
        RevisionLifecycleReason.WORKFLOW_TIMED_OUT,
    }
    if claim.lifecycle_reason in recovery_reasons:
        if claim.reconciliation_required_at is None:
            raise RevisionExecutionContractError(
                "workflow recovery requires reconciliation evidence"
            )
        if claim.lifecycle_reason is RevisionLifecycleReason.WORKFLOW_CANCELLED:
            if status is not RevisionExecutionStatus.CANCELLED:
                raise RevisionExecutionContractError("workflow cancellation reason/status mismatch")
        elif status is not RevisionExecutionStatus.FAILED:
            raise RevisionExecutionContractError("workflow failure reason/status mismatch")
    elif (
        status is RevisionExecutionStatus.FAILED
        and claim.running_at is None
        and claim.lifecycle_reason is not RevisionLifecycleReason.LAUNCH_REJECTED
    ):
        raise RevisionExecutionContractError("execution failure requires running timestamp")
    if (
        status is RevisionExecutionStatus.CANCELLED
        and claim.running_at is None
        and claim.lifecycle_reason is not RevisionLifecycleReason.WORKFLOW_CANCELLED
    ):
        raise RevisionExecutionContractError("cancellation requires running or reconciliation")
    if (
        status is RevisionExecutionStatus.COMPLETED
        and claim.running_at is None
        and claim.reconciliation_required_at is None
    ):
        raise RevisionExecutionContractError("completion requires running or reconciliation")
    result_pair = (claim.result_artifact is None, claim.result_validation_evidence_id is None)
    if result_pair[0] != result_pair[1]:
        raise RevisionExecutionContractError("result artifact and validation identity must pair")
    if status is RevisionExecutionStatus.COMPLETED:
        if claim.result_artifact is None or claim.result_validation_evidence_id is None:
            raise RevisionExecutionContractError("COMPLETED requires validated result linkage")
        _artifact(claim.result_artifact)
        _uuids(claim.result_validation_evidence_id)
        action = claim.command.action
        if (
            claim.result_artifact.artifact_id != action.target_artifact_id
            or claim.result_artifact.version != action.target_artifact_version
            or claim.result_artifact.sha256 == action.source_artifact.sha256
        ):
            raise RevisionExecutionContractError("completed result does not match revision target")
    elif claim.result_artifact is not None:
        raise RevisionExecutionContractError("only COMPLETED may contain result linkage")
