"""Create canonical execution request, run, and step storage.

Revision ID: 20260811_0003
Revises: 20260811_0002
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260811_0003"
down_revision: str | None = "20260811_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
owner = "orchestration"
tenant_tables = {"execution_requests", "execution_runs", "execution_steps"}
tenant_scope_exceptions: dict[str, str] = {}

_WORKSPACE_SETTING = "NULLIF(current_setting('app.current_workspace_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "execution_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("initiator_type", sa.String(length=20), nullable=False),
        sa.Column("workflow_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_type", sa.String(length=255), nullable=False),
        sa.Column("workflow_version", sa.String(length=50), nullable=False),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system')",
            name="ck_execution_requests_actor_type",
        ),
        sa.CheckConstraint(
            "btrim(actor_id) <> ''",
            name="ck_execution_requests_actor_id_nonblank",
        ),
        sa.CheckConstraint(
            "btrim(workflow_type) <> ''",
            name="ck_execution_requests_workflow_type_nonblank",
        ),
        sa.CheckConstraint(
            "btrim(workflow_version) <> ''",
            name="ck_execution_requests_workflow_version_nonblank",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(input_json) = 'object'",
            name="ck_execution_requests_input_object",
        ),
        sa.CheckConstraint(
            "octet_length(input_json::text) <= 65536",
            name="ck_execution_requests_input_size",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_execution_requests_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_execution_requests"),
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            name="uq_execution_requests_workspace_id",
        ),
    )
    op.create_index(
        "ix_execution_requests_workspace_created",
        "execution_requests",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_execution_requests_workspace_correlation",
        "execution_requests",
        ["workspace_id", "correlation_id"],
        unique=False,
    )

    op.create_table(
        "execution_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_type", sa.String(length=255), nullable=False),
        sa.Column("workflow_version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("initiator_type", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciliation_state", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system')",
            name="ck_execution_runs_actor_type",
        ),
        sa.CheckConstraint(
            "btrim(actor_id) <> ''",
            name="ck_execution_runs_actor_id_nonblank",
        ),
        sa.CheckConstraint(
            "btrim(workflow_type) <> ''",
            name="ck_execution_runs_workflow_type_nonblank",
        ),
        sa.CheckConstraint(
            "btrim(workflow_version) <> ''",
            name="ck_execution_runs_workflow_version_nonblank",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'waiting', 'succeeded', 'failed', "
            "'cancelled', 'reconciliation_required')",
            name="ck_execution_runs_status",
        ),
        sa.CheckConstraint(
            "reconciliation_state IN ('not_required', 'required', 'resolved')",
            name="ck_execution_runs_reconciliation_state",
        ),
        sa.CheckConstraint("version > 0", name="ck_execution_runs_version"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_execution_runs_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "execution_request_id"],
            ["execution_requests.workspace_id", "execution_requests.id"],
            name="fk_execution_runs_workspace_request",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_execution_runs"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_execution_runs_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "execution_request_id",
            name="uq_execution_runs_workspace_request",
        ),
    )
    op.create_index(
        "ix_execution_runs_workspace_status_created",
        "execution_runs",
        ["workspace_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_execution_runs_workspace_correlation",
        "execution_runs",
        ["workspace_id", "correlation_id"],
        unique=False,
    )

    op.create_table(
        "execution_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_type", sa.String(length=255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("input_ref", sa.String(length=500), nullable=False),
        sa.Column("output_evidence_ref", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_classification", sa.String(length=40), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'waiting', 'succeeded', 'failed', "
            "'cancelled', 'reconciliation_required')",
            name="ck_execution_steps_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts > 0 AND attempt_count <= max_attempts",
            name="ck_execution_steps_attempts",
        ),
        sa.CheckConstraint(
            "failure_classification IS NULL OR failure_classification IN "
            "('validation', 'business', 'infrastructure_transient', "
            "'infrastructure_exhausted', 'cancelled', 'unknown_outcome', 'internal_defect')",
            name="ck_execution_steps_failure_classification",
        ),
        sa.CheckConstraint("sequence >= 0", name="ck_execution_steps_sequence"),
        sa.CheckConstraint(
            "(status = 'failed' AND failure_classification IS NOT NULL) OR "
            "(status = 'reconciliation_required' AND "
            "failure_classification = 'unknown_outcome') OR "
            "(status NOT IN ('failed', 'reconciliation_required') AND "
            "failure_classification IS NULL)",
            name="ck_execution_steps_status_failure",
        ),
        sa.CheckConstraint(
            "btrim(step_type) <> ''",
            name="ck_execution_steps_step_type_nonblank",
        ),
        sa.CheckConstraint(
            "btrim(input_ref) <> ''",
            name="ck_execution_steps_input_ref_nonblank",
        ),
        sa.CheckConstraint(
            "output_evidence_ref IS NULL OR btrim(output_evidence_ref) <> ''",
            name="ck_execution_steps_output_evidence_ref_nonblank",
        ),
        sa.CheckConstraint("version > 0", name="ck_execution_steps_version"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_execution_steps_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "run_id"],
            ["execution_runs.workspace_id", "execution_runs.id"],
            name="fk_execution_steps_workspace_run",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_execution_steps"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_execution_steps_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "run_id",
            "sequence",
            name="uq_execution_steps_workspace_run_sequence",
        ),
    )
    op.create_index(
        "ix_execution_steps_workspace_status",
        "execution_steps",
        ["workspace_id", "status"],
        unique=False,
    )

    op.execute("ALTER TABLE execution_requests ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE execution_requests FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY execution_requests_workspace_isolation ON execution_requests
        FOR ALL
        USING (workspace_id = {_WORKSPACE_SETTING})
        WITH CHECK (workspace_id = {_WORKSPACE_SETTING})
        """
    )
    op.execute("ALTER TABLE execution_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE execution_runs FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY execution_runs_workspace_isolation ON execution_runs
        FOR ALL
        USING (workspace_id = {_WORKSPACE_SETTING})
        WITH CHECK (workspace_id = {_WORKSPACE_SETTING})
        """
    )
    op.execute("ALTER TABLE execution_steps ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE execution_steps FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY execution_steps_workspace_isolation ON execution_steps
        FOR ALL
        USING (workspace_id = {_WORKSPACE_SETTING})
        WITH CHECK (workspace_id = {_WORKSPACE_SETTING})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY execution_steps_workspace_isolation ON execution_steps")
    op.drop_index("ix_execution_steps_workspace_status", table_name="execution_steps")
    op.drop_table("execution_steps")
    op.execute("DROP POLICY execution_runs_workspace_isolation ON execution_runs")
    op.drop_index("ix_execution_runs_workspace_correlation", table_name="execution_runs")
    op.drop_index("ix_execution_runs_workspace_status_created", table_name="execution_runs")
    op.drop_table("execution_runs")
    op.execute("DROP POLICY execution_requests_workspace_isolation ON execution_requests")
    op.drop_index("ix_execution_requests_workspace_correlation", table_name="execution_requests")
    op.drop_index("ix_execution_requests_workspace_created", table_name="execution_requests")
    op.drop_table("execution_requests")
