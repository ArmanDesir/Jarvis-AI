"""Create append-only audit evidence and transactional outbox storage.

Revision ID: 20260811_0002
Revises: 20260806_0001
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260811_0002"
down_revision: str | None = "20260806_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
owner = "audit"
tenant_tables = {"audit_entries", "outbox_events"}
tenant_scope_exceptions: dict[str, str] = {}

_WORKSPACE_SETTING = "NULLIF(current_setting('app.current_workspace_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "audit_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("resource_type", sa.String(length=255), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("policy_ref", sa.String(length=255), nullable=True),
        sa.Column("approval_ref", sa.String(length=255), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence_ref", sa.String(length=500), nullable=True),
        sa.Column("sensitivity", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('user', 'ai', 'system', 'service', 'provider')",
            name="ck_audit_entries_actor_type",
        ),
        sa.CheckConstraint(
            "outcome IN ('succeeded', 'failed', 'denied')",
            name="ck_audit_entries_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_audit_entries_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_entries"),
    )
    op.create_index(
        "ix_audit_entries_workspace_created",
        "audit_entries",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_entries_correlation", "audit_entries", ["correlation_id"], unique=False
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("producer", sa.String(length=255), nullable=False),
        sa.Column("sensitivity", sa.String(length=20), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("event_version > 0", name="ck_outbox_events_event_version"),
        sa.CheckConstraint("schema_version > 0", name="ck_outbox_events_schema_version"),
        sa.CheckConstraint("attempts >= 0", name="ck_outbox_events_attempts"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_outbox_events_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_events"),
        sa.UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_outbox_events_workspace_idempotency"
        ),
    )
    op.create_index(
        "ix_outbox_events_pending",
        "outbox_events",
        ["workspace_id", "published_at", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_outbox_events_correlation", "outbox_events", ["correlation_id"], unique=False
    )

    op.execute("ALTER TABLE audit_entries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_entries FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY audit_entries_workspace_isolation ON audit_entries
        USING (workspace_id = {_WORKSPACE_SETTING})
        WITH CHECK (workspace_id = {_WORKSPACE_SETTING})
        """
    )
    op.execute("ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE outbox_events FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY outbox_events_workspace_isolation ON outbox_events
        USING (workspace_id = {_WORKSPACE_SETTING})
        WITH CHECK (workspace_id = {_WORKSPACE_SETTING})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY outbox_events_workspace_isolation ON outbox_events")
    op.drop_index("ix_outbox_events_correlation", table_name="outbox_events")
    op.drop_index("ix_outbox_events_pending", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.execute("DROP POLICY audit_entries_workspace_isolation ON audit_entries")
    op.drop_index("ix_audit_entries_correlation", table_name="audit_entries")
    op.drop_index("ix_audit_entries_workspace_created", table_name="audit_entries")
    op.drop_table("audit_entries")
