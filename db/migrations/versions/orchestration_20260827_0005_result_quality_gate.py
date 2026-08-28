"""Create durable result quality-gate state and append-only decisions.

Revision ID: 20260827_0005
Revises: 20260812_0004
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260827_0005"
down_revision: str | None = "20260812_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
owner = "orchestration"
tenant_tables = {"quality_gate_states", "quality_gate_decisions"}
tenant_scope_exceptions: dict[str, str] = {}

_WORKSPACE = "NULLIF(current_setting('app.current_workspace_id', true), '')::uuid"
_STATUS = "('awaiting_review','revision_required','accepted','needs_human_review')"
_OUTCOME = "('accepted','revision_required','needs_human_review')"
_REASONS = (
    "threshold_met,threshold_not_met,no_prior_comparable_score,score_strictly_improved,"
    "score_not_improved,revision_budget_remaining,revision_budget_exhausted,"
    "reviewer_escalation_requested"
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_execution_steps_workspace_id_run",
        "execution_steps",
        ["workspace_id", "id", "run_id"],
    )
    op.create_table(
        "quality_gate_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("capability_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability_key", sa.String(255), nullable=False),
        sa.Column("capability_version", sa.String(50), nullable=False),
        sa.Column("policy_key", sa.String(255), nullable=False),
        sa.Column("policy_version", sa.String(50), nullable=False),
        sa.Column("criteria_key", sa.String(255), nullable=False),
        sa.Column("criteria_version", sa.String(50), nullable=False),
        sa.Column("score_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("automated_revision_count", sa.SmallInteger(), nullable=False),
        sa.Column("minimum_score", sa.SmallInteger(), nullable=False),
        sa.Column("last_score", sa.SmallInteger(), nullable=False),
        sa.Column("last_artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_artifact_version", sa.Integer(), nullable=False),
        sa.Column("last_artifact_sha256", sa.String(64), nullable=False),
        sa.Column("last_validation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quality_gate_states"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_quality_gate_states_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id", "run_id", "step_id", name="uq_quality_gate_states_workspace_step"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_quality_gate_states_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "step_id", "run_id"],
            ["execution_steps.workspace_id", "execution_steps.id", "execution_steps.run_id"],
            name="fk_quality_gate_states_workspace_step_run",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(f"status IN {_STATUS}", name="ck_quality_gate_states_status"),
        sa.CheckConstraint(
            "automated_revision_count BETWEEN 0 AND 2", name="ck_quality_gate_states_revision_count"
        ),
        sa.CheckConstraint(
            "minimum_score BETWEEN 0 AND 100 AND last_score BETWEEN 0 AND 100",
            name="ck_quality_gate_states_scores",
        ),
        sa.CheckConstraint(
            "last_artifact_version > 0 AND version > 0", name="ck_quality_gate_states_versions"
        ),
        sa.CheckConstraint(
            "last_artifact_sha256 ~ '^[0-9a-f]{64}$'", name="ck_quality_gate_states_sha256"
        ),
        sa.CheckConstraint("updated_at >= created_at", name="ck_quality_gate_states_timestamps"),
    )
    op.create_index(
        "ix_quality_gate_states_workspace_status_updated",
        "quality_gate_states",
        ["workspace_id", "status", "updated_at"],
    )
    op.create_table(
        "quality_gate_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quality_gate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("capability_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability_key", sa.String(255), nullable=False),
        sa.Column("capability_version", sa.String(50), nullable=False),
        sa.Column("policy_key", sa.String(255), nullable=False),
        sa.Column("policy_version", sa.String(50), nullable=False),
        sa.Column("criteria_key", sa.String(255), nullable=False),
        sa.Column("criteria_version", sa.String(50), nullable=False),
        sa.Column("score_key", sa.String(255), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("minimum_score", sa.SmallInteger(), nullable=False),
        sa.Column("prior_score", sa.SmallInteger(), nullable=True),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("validation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("reasons_json", postgresql.JSONB(), nullable=False),
        sa.Column("revision_count_before", sa.SmallInteger(), nullable=False),
        sa.Column("revision_count_after", sa.SmallInteger(), nullable=False),
        sa.Column("state_version_before", sa.Integer(), nullable=True),
        sa.Column("state_version_after", sa.Integer(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quality_gate_decisions"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_quality_gate_decisions_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id", "command_id", name="uq_quality_gate_decisions_workspace_command"
        ),
        sa.UniqueConstraint(
            "workspace_id", "assessment_id", name="uq_quality_gate_decisions_workspace_assessment"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_quality_gate_decisions_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "quality_gate_id"],
            ["quality_gate_states.workspace_id", "quality_gate_states.id"],
            name="fk_quality_gate_decisions_workspace_gate",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "step_id", "run_id"],
            ["execution_steps.workspace_id", "execution_steps.id", "execution_steps.run_id"],
            name="fk_quality_gate_decisions_workspace_step_run",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("id = command_id", name="ck_quality_gate_decisions_identity"),
        sa.CheckConstraint(
            "actor_type IN ('user','system')", name="ck_quality_gate_decisions_actor_type"
        ),
        sa.CheckConstraint(f"outcome IN {_OUTCOME}", name="ck_quality_gate_decisions_outcome"),
        sa.CheckConstraint(
            "score BETWEEN 0 AND 100 AND minimum_score BETWEEN 0 AND 100 AND "
            "(prior_score IS NULL OR prior_score BETWEEN 0 AND 100)",
            name="ck_quality_gate_decisions_scores",
        ),
        sa.CheckConstraint(
            "revision_count_before BETWEEN 0 AND 2 AND revision_count_after BETWEEN 0 AND 2 "
            "AND revision_count_after >= revision_count_before "
            "AND revision_count_after <= revision_count_before + 1",
            name="ck_quality_gate_decisions_revision_counts",
        ),
        sa.CheckConstraint(
            "state_version_after > 0 AND (state_version_before IS NULL OR "
            "(state_version_before > 0 AND "
            "state_version_after = state_version_before + 1))",
            name="ck_quality_gate_decisions_state_versions",
        ),
        sa.CheckConstraint(
            "artifact_version > 0", name="ck_quality_gate_decisions_artifact_version"
        ),
        sa.CheckConstraint(
            "artifact_sha256 ~ '^[0-9a-f]{64}$'", name="ck_quality_gate_decisions_sha256"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(reasons_json) = 'array' AND "
            "jsonb_array_length(reasons_json) BETWEEN 1 AND 8",
            name="ck_quality_gate_decisions_reasons_shape",
        ),
        sa.CheckConstraint(
            f"reasons_json <@ to_jsonb(string_to_array('{_REASONS}', ','))",
            name="ck_quality_gate_decisions_reasons_values",
        ),
    )
    op.create_index(
        "ix_quality_gate_decisions_workspace_gate_decided",
        "quality_gate_decisions",
        ["workspace_id", "quality_gate_id", "decided_at"],
    )
    op.execute("ALTER TABLE quality_gate_states ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE quality_gate_states FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY quality_gate_states_workspace_isolation ON quality_gate_states FOR ALL "
        f"USING (workspace_id = {_WORKSPACE}) WITH CHECK (workspace_id = {_WORKSPACE})"
    )
    op.execute("ALTER TABLE quality_gate_decisions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE quality_gate_decisions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY quality_gate_decisions_workspace_isolation ON quality_gate_decisions "
        f"FOR ALL USING (workspace_id = {_WORKSPACE}) WITH CHECK (workspace_id = {_WORKSPACE})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY quality_gate_decisions_workspace_isolation ON quality_gate_decisions")
    op.drop_index(
        "ix_quality_gate_decisions_workspace_gate_decided", table_name="quality_gate_decisions"
    )
    op.drop_table("quality_gate_decisions")
    op.execute("DROP POLICY quality_gate_states_workspace_isolation ON quality_gate_states")
    op.drop_index(
        "ix_quality_gate_states_workspace_status_updated", table_name="quality_gate_states"
    )
    op.drop_table("quality_gate_states")
    op.drop_constraint("uq_execution_steps_workspace_id_run", "execution_steps", type_="unique")
