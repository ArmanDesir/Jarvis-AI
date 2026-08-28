"""Orchestration-owned persistence and transaction ports."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self, Sequence
from uuid import UUID

from rightjob.contracts.authorization import ExecutionAuthorizationConsumer
from rightjob.contracts.events import AuditEvidence, IntegrationEvent
from rightjob.contracts.revision import QualityGateDecision, QualityGateState
from rightjob.orchestration.domain import ExecutionRequest, ExecutionRun, ExecutionStep


class ConcurrentExecutionUpdateError(RuntimeError):
    """The canonical execution changed after it was loaded."""


class ConcurrentQualityGateUpdateError(RuntimeError):
    """Quality-gate state changed after it was loaded."""


class AuditEvidenceAppender(Protocol):
    def append(self, workspace_id: UUID, evidence: AuditEvidence) -> None: ...


class OutboxAppender(Protocol):
    def add(self, workspace_id: UUID, event: IntegrationEvent) -> None: ...


class ExecutionRequestRepository(Protocol):
    def add(self, workspace_id: UUID, request: ExecutionRequest) -> None: ...


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

    def save(
        self,
        workspace_id: UUID,
        state: QualityGateState,
        minimum_score: int,
        expected_version: int,
    ) -> None: ...


class QualityGateDecisionRepository(Protocol):
    def get_by_command(
        self, workspace_id: UUID, command_id: UUID
    ) -> QualityGateDecision | None: ...

    def append(
        self, workspace_id: UUID, decision: QualityGateDecision, state_version_before: int | None
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
