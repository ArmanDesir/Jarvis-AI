"""Audit/Outbox persistence and transaction boundaries."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Protocol, Self, Sequence
from uuid import UUID

from rightjob.contracts.events import AuditEvidence, IntegrationEvent


class AuditEvidenceRepository(Protocol):
    def append(self, workspace_id: UUID, evidence: AuditEvidence) -> None: ...


class OutboxRepository(Protocol):
    def add(self, workspace_id: UUID, event: IntegrationEvent) -> None: ...

    def list_pending(self, workspace_id: UUID, limit: int) -> Sequence[IntegrationEvent]: ...

    def mark_published(
        self, workspace_id: UUID, event_id: UUID, published_at: datetime
    ) -> None: ...


class EventDeduplicator(Protocol):
    """Consumer-owned atomic claim boundary keyed by immutable event ID."""

    def claim(self, workspace_id: UUID, consumer: str, event_id: UUID) -> bool: ...


class AuditUnitOfWork(Protocol):
    audit_evidence: AuditEvidenceRepository
    outbox: OutboxRepository

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
