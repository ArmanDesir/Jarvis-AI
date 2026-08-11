"""Workspace-scoped SQLAlchemy audit and outbox repositories."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from rightjob.audit.infrastructure.models import AuditEntryRecord, OutboxEventRecord
from rightjob.contracts.events import (
    Actor,
    ActorType,
    AuditEvidence,
    DataSensitivity,
    IntegrationEvent,
)


def _set_workspace_context(session: Session, workspace_id: UUID) -> None:
    session.execute(select(func.set_config("app.current_workspace_id", str(workspace_id), True)))


def _require_scope(workspace_id: UUID, record_workspace_id: UUID) -> None:
    if workspace_id != record_workspace_id:
        raise ValueError("record workspace must match repository scope")


class SqlAlchemyAuditEvidenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, workspace_id: UUID, evidence: AuditEvidence) -> None:
        _require_scope(workspace_id, evidence.workspace_id)
        _set_workspace_context(self._session, workspace_id)
        self._session.add(
            AuditEntryRecord(
                id=evidence.id,
                workspace_id=evidence.workspace_id,
                actor_type=evidence.actor.type.value,
                actor_id=evidence.actor.id,
                action=evidence.action,
                resource_type=evidence.resource_type,
                resource_id=evidence.resource_id,
                outcome=evidence.outcome.value,
                correlation_id=evidence.correlation_id,
                causation_id=evidence.causation_id,
                policy_ref=evidence.policy_ref,
                approval_ref=evidence.approval_ref,
                before_json=evidence.before,
                after_json=evidence.after,
                evidence_ref=evidence.evidence_ref,
                sensitivity=evidence.sensitivity.value,
                occurred_at=evidence.occurred_at,
                created_at=datetime.now(timezone.utc),
            )
        )


class SqlAlchemyOutboxRepository:
    """Can share any aggregate-owning SQLAlchemy Session for an atomic commit."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, workspace_id: UUID, event: IntegrationEvent) -> None:
        _require_scope(workspace_id, event.workspace_id)
        _set_workspace_context(self._session, workspace_id)
        self._session.add(
            OutboxEventRecord(
                id=event.event_id,
                workspace_id=event.workspace_id,
                event_type=event.event_type,
                event_version=event.event_version,
                schema_version=event.schema_version,
                occurred_at=event.occurred_at,
                actor_type=event.actor.type.value,
                actor_id=event.actor.id,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                producer=event.producer,
                sensitivity=event.sensitivity.value,
                payload_json=event.payload,
                idempotency_key=event.idempotency_key,
                published_at=None,
                attempts=0,
                created_at=datetime.now(timezone.utc),
            )
        )

    def list_pending(self, workspace_id: UUID, limit: int) -> Sequence[IntegrationEvent]:
        if limit < 1:
            raise ValueError("limit must be positive")
        _set_workspace_context(self._session, workspace_id)
        records = self._session.scalars(
            select(OutboxEventRecord)
            .where(
                OutboxEventRecord.workspace_id == workspace_id,
                OutboxEventRecord.published_at.is_(None),
            )
            .order_by(OutboxEventRecord.occurred_at, OutboxEventRecord.id)
            .limit(limit)
        )
        return [_event(record) for record in records]

    def mark_published(self, workspace_id: UUID, event_id: UUID, published_at: datetime) -> None:
        if published_at.tzinfo is None or published_at.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        _set_workspace_context(self._session, workspace_id)
        self._session.execute(
            update(OutboxEventRecord)
            .where(
                OutboxEventRecord.id == event_id,
                OutboxEventRecord.workspace_id == workspace_id,
                OutboxEventRecord.published_at.is_(None),
            )
            .values(published_at=published_at)
        )


def _event(record: OutboxEventRecord) -> IntegrationEvent:
    return IntegrationEvent(
        event_id=record.id,
        event_type=record.event_type,
        event_version=record.event_version,
        schema_version=record.schema_version,
        occurred_at=record.occurred_at,
        workspace_id=record.workspace_id,
        actor=Actor(ActorType(record.actor_type), record.actor_id),
        correlation_id=record.correlation_id,
        causation_id=record.causation_id,
        producer=record.producer,
        sensitivity=DataSensitivity(record.sensitivity),
        payload=record.payload_json,
        idempotency_key=record.idempotency_key,
    )
