"""Create durable authorized revision execution claims.

Revision ID: 20260827_0006
Revises: 20260827_0005
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260827_0006"
down_revision: str | None = "20260827_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
owner = "orchestration"
tenant_tables = {"revision_execution_claims"}
tenant_scope_exceptions: dict[str, str] = {}

_WORKSPACE = "NULLIF(current_setting('app.current_workspace_id', true), '')::uuid"


def upgrade() -> None:
    op.alter_column("execution_requests", "execution_authorization_id", nullable=True)
    op.add_column(
        "execution_requests",
        sa.Column("revision_authorization_evidence_id", postgresql.UUID(as_uuid=True)),
    )
    op.create_foreign_key(
        "fk_execution_requests_workspace_revision_authorization",
        "execution_requests",
        "authorization_evidence",
        ["workspace_id", "revision_authorization_evidence_id"],
        ["workspace_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_execution_requests_authorization_kind",
        "execution_requests",
        "(execution_authorization_id IS NULL) <> (revision_authorization_evidence_id IS NULL)",
    )

    op.create_table(
        "revision_execution_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quality_gate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quality_decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reserved_cycle", sa.SmallInteger(), nullable=False),
        sa.Column("planning_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("department_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_key", sa.String(100), nullable=False),
        sa.Column("department_version", sa.String(50), nullable=False),
        sa.Column("capability_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability_key", sa.String(100), nullable=False),
        sa.Column("capability_version", sa.String(50), nullable=False),
        sa.Column("quality_policy_key", sa.String(100), nullable=False),
        sa.Column("quality_policy_version", sa.String(50), nullable=False),
        sa.Column("action_type", sa.String(40), nullable=False),
        sa.Column("action_digest", sa.String(64), nullable=False),
        sa.Column(
            "prior_execution_authorization_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("authorization_evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_artifact_version", sa.Integer(), nullable=False),
        sa.Column("source_artifact_sha256", sa.String(64), nullable=False),
        sa.Column("target_artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_artifact_version", sa.Integer(), nullable=False),
        sa.Column("execution_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("workflow_id", sa.String(255), nullable=True),
        sa.Column("lifecycle_reason", sa.String(40), nullable=True),
        sa.Column("launch_pending_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("running_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciliation_required_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result_artifact_version", sa.Integer(), nullable=True),
        sa.Column("result_artifact_sha256", sa.String(64), nullable=True),
        sa.Column("result_validation_evidence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_lifecycle_command_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_lifecycle_command_digest", sa.String(64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_revision_execution_claims"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_revision_execution_claims_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id", "command_id", name="uq_revision_execution_claims_workspace_command"
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "quality_gate_id",
            "quality_decision_id",
            "reserved_cycle",
            name="uq_revision_execution_claims_gate_decision_cycle",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "execution_request_id",
            name="uq_revision_execution_claims_execution_request",
        ),
        sa.UniqueConstraint(
            "workspace_id", "execution_run_id", name="uq_revision_execution_claims_execution_run"
        ),
        sa.UniqueConstraint(
            "workspace_id", "execution_step_id", name="uq_revision_execution_claims_execution_step"
        ),
        sa.UniqueConstraint(
            "workspace_id", "workflow_id", name="uq_revision_execution_claims_workspace_workflow"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_revision_execution_claims_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "quality_gate_id"],
            ["quality_gate_states.workspace_id", "quality_gate_states.id"],
            name="fk_revision_execution_claims_gate",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "quality_decision_id"],
            ["quality_gate_decisions.workspace_id", "quality_gate_decisions.id"],
            name="fk_revision_execution_claims_decision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_step_id", "source_run_id"],
            ["execution_steps.workspace_id", "execution_steps.id", "execution_steps.run_id"],
            name="fk_revision_execution_claims_source_step",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "authorization_evidence_id", "source_step_id", "action_digest"],
            [
                "authorization_evidence.workspace_id",
                "authorization_evidence.id",
                "authorization_evidence.step_id",
                "authorization_evidence.action_digest",
            ],
            name="fk_revision_execution_claims_authorization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "approval_request_id", "authorization_evidence_id", "action_digest"],
            [
                "approval_requests.workspace_id",
                "approval_requests.id",
                "approval_requests.authorization_evidence_id",
                "approval_requests.action_digest",
            ],
            name="fk_revision_execution_claims_approval_request",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "approval_decision_id", "approval_request_id", "action_digest"],
            [
                "approval_decisions.workspace_id",
                "approval_decisions.id",
                "approval_decisions.approval_request_id",
                "approval_decisions.action_digest",
            ],
            name="fk_revision_execution_claims_approval_decision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "execution_request_id"],
            ["execution_requests.workspace_id", "execution_requests.id"],
            name="fk_revision_execution_claims_execution_request",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "execution_run_id"],
            ["execution_runs.workspace_id", "execution_runs.id"],
            name="fk_revision_execution_claims_execution_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "execution_step_id", "execution_run_id"],
            ["execution_steps.workspace_id", "execution_steps.id", "execution_steps.run_id"],
            name="fk_revision_execution_claims_execution_step",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("reserved_cycle IN (1,2)", name="ck_revision_execution_claims_cycle"),
        sa.CheckConstraint(
            "action_type = 'regenerate_artifact'", name="ck_revision_execution_claims_action"
        ),
        sa.CheckConstraint(
            "status IN ('claimed','launch_pending','running','completed','failed',"
            "'cancelled','reconciliation_required')",
            name="ck_revision_execution_claims_status",
        ),
        sa.CheckConstraint(
            "(status = 'claimed') = (workflow_id IS NULL)",
            name="ck_revision_execution_claims_workflow_state",
        ),
        sa.CheckConstraint(
            "status = 'claimed' OR launch_pending_at IS NOT NULL",
            name="ck_revision_execution_claims_launch_timestamp",
        ),
        sa.CheckConstraint(
            "status NOT IN ('running','completed','failed','cancelled') OR "
            "running_at IS NOT NULL OR "
            "(status = 'failed' AND lifecycle_reason = 'launch_rejected') OR "
            "(reconciliation_required_at IS NOT NULL AND ("
            "(status = 'completed' AND lifecycle_reason IS NULL) OR "
            "(status = 'failed' AND lifecycle_reason IN "
            "('workflow_failed','workflow_terminated','workflow_timed_out')) OR "
            "(status = 'cancelled' AND lifecycle_reason = 'workflow_cancelled')))",
            name="ck_revision_execution_claims_running_timestamp",
        ),
        sa.CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name="ck_revision_execution_claims_completed_timestamp",
        ),
        sa.CheckConstraint(
            "(status = 'failed') = (failed_at IS NOT NULL)",
            name="ck_revision_execution_claims_failed_timestamp",
        ),
        sa.CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)",
            name="ck_revision_execution_claims_cancelled_timestamp",
        ),
        sa.CheckConstraint(
            "status <> 'reconciliation_required' OR reconciliation_required_at IS NOT NULL",
            name="ck_revision_execution_claims_reconciliation_timestamp",
        ),
        sa.CheckConstraint(
            "lifecycle_reason IS NULL OR lifecycle_reason IN "
            "('launch_rejected','launch_outcome_unknown','execution_failed',"
            "'validation_failed','cancelled_by_request','workflow_failed',"
            "'workflow_cancelled','workflow_terminated','workflow_timed_out')",
            name="ck_revision_execution_claims_reason",
        ),
        sa.CheckConstraint(
            "(status IN ('failed','cancelled','reconciliation_required')) = "
            "(lifecycle_reason IS NOT NULL)",
            name="ck_revision_execution_claims_reason_required",
        ),
        sa.CheckConstraint(
            "(status <> 'failed' OR lifecycle_reason IN "
            "('launch_rejected','execution_failed','validation_failed','workflow_failed',"
            "'workflow_terminated','workflow_timed_out')) AND "
            "(lifecycle_reason <> 'launch_rejected' OR "
            "(status = 'failed' AND running_at IS NULL)) AND "
            "(status <> 'cancelled' OR lifecycle_reason IN "
            "('cancelled_by_request','workflow_cancelled')) AND "
            "(status <> 'reconciliation_required' OR "
            "lifecycle_reason = 'launch_outcome_unknown') AND "
            "(lifecycle_reason NOT IN ('workflow_failed','workflow_cancelled',"
            "'workflow_terminated','workflow_timed_out') OR "
            "reconciliation_required_at IS NOT NULL)",
            name="ck_revision_execution_claims_reason_status",
        ),
        sa.CheckConstraint(
            "(result_artifact_id IS NULL) = (result_artifact_version IS NULL) AND "
            "(result_artifact_id IS NULL) = (result_artifact_sha256 IS NULL) AND "
            "(result_artifact_id IS NULL) = (result_validation_evidence_id IS NULL)",
            name="ck_revision_execution_claims_result_pair",
        ),
        sa.CheckConstraint(
            "(status = 'completed') = (result_artifact_id IS NOT NULL)",
            name="ck_revision_execution_claims_completed_result",
        ),
        sa.CheckConstraint(
            "result_artifact_id IS NULL OR "
            "(result_artifact_id = target_artifact_id AND "
            "result_artifact_version = target_artifact_version AND "
            "result_artifact_sha256 ~ '^[0-9a-f]{64}$' AND "
            "result_artifact_sha256 <> source_artifact_sha256)",
            name="ck_revision_execution_claims_result_identity",
        ),
        sa.CheckConstraint(
            "(last_lifecycle_command_id IS NULL) = (last_lifecycle_command_digest IS NULL) AND "
            "(last_lifecycle_command_digest IS NULL OR "
            "last_lifecycle_command_digest ~ '^[0-9a-f]{64}$')",
            name="ck_revision_execution_claims_lifecycle_command",
        ),
        sa.CheckConstraint(
            "action_digest ~ '^[0-9a-f]{64}$' AND source_artifact_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_revision_execution_claims_hashes",
        ),
        sa.CheckConstraint(
            "target_artifact_id = source_artifact_id AND "
            "target_artifact_version = source_artifact_version + 1",
            name="ck_revision_execution_claims_artifact_progression",
        ),
        sa.CheckConstraint("version > 0", name="ck_revision_execution_claims_version"),
        sa.CheckConstraint(
            "(approval_request_id IS NULL) = (approval_decision_id IS NULL)",
            name="ck_revision_execution_claims_approval_pair",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at AND claimed_at = created_at",
            name="ck_revision_execution_claims_timestamps",
        ),
    )
    op.create_index(
        "ix_revision_execution_claims_workspace_gate_status",
        "revision_execution_claims",
        ["workspace_id", "quality_gate_id", "status"],
    )
    op.create_index(
        "ix_revision_execution_claims_workspace_authorization",
        "revision_execution_claims",
        ["workspace_id", "authorization_evidence_id"],
    )
    op.execute("ALTER TABLE revision_execution_claims ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE revision_execution_claims FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY revision_execution_claims_workspace_isolation ON revision_execution_claims "
        f"FOR ALL USING (workspace_id = {_WORKSPACE}) WITH CHECK (workspace_id = {_WORKSPACE})"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY revision_execution_claims_workspace_isolation ON revision_execution_claims"
    )
    op.drop_index(
        "ix_revision_execution_claims_workspace_authorization",
        table_name="revision_execution_claims",
    )
    op.drop_index(
        "ix_revision_execution_claims_workspace_gate_status", table_name="revision_execution_claims"
    )
    op.drop_table("revision_execution_claims")
    op.execute(
        "DELETE FROM execution_steps WHERE run_id IN "
        "(SELECT id FROM execution_runs WHERE execution_request_id IN "
        "(SELECT id FROM execution_requests WHERE revision_authorization_evidence_id IS NOT NULL))"
    )
    op.execute(
        "DELETE FROM execution_runs WHERE execution_request_id IN "
        "(SELECT id FROM execution_requests WHERE revision_authorization_evidence_id IS NOT NULL)"
    )
    op.execute(
        "DELETE FROM execution_requests WHERE revision_authorization_evidence_id IS NOT NULL"
    )
    op.drop_constraint(
        "ck_execution_requests_authorization_kind", "execution_requests", type_="check"
    )
    op.drop_constraint(
        "fk_execution_requests_workspace_revision_authorization",
        "execution_requests",
        type_="foreignkey",
    )
    op.drop_column("execution_requests", "revision_authorization_evidence_id")
    op.alter_column("execution_requests", "execution_authorization_id", nullable=False)
