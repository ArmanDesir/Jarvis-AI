"""Audit and transactional-outbox SQLAlchemy mappings."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from rightjob.shared.sqlalchemy import Base


class AuditEntryRecord(Base):
    __tablename__ = "audit_entries"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'ai', 'system', 'service', 'provider')",
            name="ck_audit_entries_actor_type",
        ),
        CheckConstraint(
            "outcome IN ('succeeded', 'failed', 'denied')",
            name="ck_audit_entries_outcome",
        ),
        Index("ix_audit_entries_workspace_created", "workspace_id", "created_at"),
        Index("ix_audit_entries_correlation", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    policy_ref: Mapped[str | None] = mapped_column(String(255))
    approval_ref: Mapped[str | None] = mapped_column(String(255))
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    evidence_ref: Mapped[str | None] = mapped_column(String(500))
    sensitivity: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutboxEventRecord(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint("event_version > 0", name="ck_outbox_events_event_version"),
        CheckConstraint("schema_version > 0", name="ck_outbox_events_schema_version"),
        CheckConstraint("attempts >= 0", name="ck_outbox_events_attempts"),
        UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_outbox_events_workspace_idempotency"
        ),
        Index("ix_outbox_events_pending", "workspace_id", "published_at", "occurred_at"),
        Index("ix_outbox_events_correlation", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    producer: Mapped[str] = mapped_column(String(255), nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(20), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
