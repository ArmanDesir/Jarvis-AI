"""Orchestration-owned persistence and transaction ports."""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Protocol, Self, Sequence
from uuid import UUID

from rightjob.contracts.authorization import ExecutionAuthorizationConsumer
from rightjob.contracts.events import AuditEvidence, IntegrationEvent, JsonValue
from rightjob.contracts.revision import QualityGateDecision, QualityGateState
from rightjob.contracts.revision_execution import RevisionExecutionClaim, RevisionExecutionCommand
from rightjob.orchestration.domain import ExecutionRequest, ExecutionRun, ExecutionStep


class ConcurrentExecutionUpdateError(RuntimeError):
    """The canonical execution changed after it was loaded."""


class ConcurrentQualityGateUpdateError(RuntimeError):
    """Quality-gate state changed after it was loaded."""


class ConcurrentRevisionExecutionUpdateError(RuntimeError):
    """Revision execution lifecycle changed after it was loaded."""


class AuditEvidenceAppender(Protocol):
    def append(self, workspace_id: UUID, evidence: AuditEvidence) -> None: ...


class OutboxAppender(Protocol):
    def add(self, workspace_id: UUID, event: IntegrationEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class RevisionExecutionRequestBinding:
    request_id: UUID
    workspace_id: UUID
    revision_authorization_evidence_id: UUID
    workflow_definition_id: UUID
    workflow_type: str
    workflow_version: str
    input: dict[str, JsonValue]


class ExecutionRequestRepository(Protocol):
    def add(self, workspace_id: UUID, request: ExecutionRequest) -> None: ...

    def get_revision_binding(
        self, workspace_id: UUID, request_id: UUID
    ) -> RevisionExecutionRequestBinding | None: ...


class ExecutionRunRepository(Protocol):
    def add(self, workspace_id: UUID, run: ExecutionRun) -> None: ...

    def get(self, workspace_id: UUID, run_id: UUID) -> ExecutionRun | None: ...

    def save(self, workspace_id: UUID, run: ExecutionRun, expected_version: int) -> None: ...


class ExecutionStepRepository(Protocol):
    def add_all(self, workspace_id: UUID, steps: Sequence[ExecutionStep]) -> None: ...

    def get(self, workspace_id: UUID, step_id: UUID) -> ExecutionStep | None: ...

    def list_for_run(self, workspace_id: UUID, run_id: UUID) -> Sequence[ExecutionStep]: ...

    def save(self, workspace_id: UUID, step: ExecutionStep, expected_version: int) -> None: ...


class QualityGateStateRepository(Protocol):
    def get(self, workspace_id: UUID, quality_gate_id: UUID) -> QualityGateState | None: ...

    def add(self, workspace_id: UUID, state: QualityGateState, minimum_score: int) -> None: ...

    def assert_version(
        self, workspace_id: UUID, quality_gate_id: UUID, expected_version: int
    ) -> None: ...

    def save(
        self,
        workspace_id: UUID,
        state: QualityGateState,
        minimum_score: int,
        expected_version: int,
    ) -> None: ...


class QualityGateDecisionRepository(Protocol):
    def get_current(
        self, workspace_id: UUID, quality_gate_id: UUID, decision_id: UUID
    ) -> QualityGateDecision | None: ...

    def get_by_command(
        self, workspace_id: UUID, command_id: UUID
    ) -> QualityGateDecision | None: ...

    def append(
        self, workspace_id: UUID, decision: QualityGateDecision, state_version_before: int | None
    ) -> None: ...


class RevisionExecutionClaimRepository(Protocol):
    def get_by_command(
        self, workspace_id: UUID, command: RevisionExecutionCommand
    ) -> RevisionExecutionClaim | None: ...

    def add(self, workspace_id: UUID, claim: RevisionExecutionClaim) -> None: ...

    def save(
        self, workspace_id: UUID, claim: RevisionExecutionClaim, expected_version: int
    ) -> None: ...


class ExecutionUnitOfWork(Protocol):
    requests: ExecutionRequestRepository
    runs: ExecutionRunRepository
    steps: ExecutionStepRepository
    audit_evidence: AuditEvidenceAppender
    outbox: OutboxAppender
    authorizations: ExecutionAuthorizationConsumer
    quality_gate_states: QualityGateStateRepository
    quality_gate_decisions: QualityGateDecisionRepository
    revision_execution_claims: RevisionExecutionClaimRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...
