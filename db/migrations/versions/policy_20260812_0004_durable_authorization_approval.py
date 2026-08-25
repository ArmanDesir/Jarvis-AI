"""Create durable authorization and human approval storage.

Revision ID: 20260812_0004
Revises: 20260811_0003
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0004"
down_revision: str | None = "20260811_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
owner = "policy"
tenant_tables = {
    "authorization_evidence",
    "approval_requests",
    "approval_decisions",
    "execution_authorizations",
    "execution_authorization_steps",
}
tenant_scope_exceptions = {}

_WORKSPACE_SETTING = "NULLIF(current_setting('app.current_workspace_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "authorization_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planning_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_actor_type", sa.String(length=20), nullable=False),
        sa.Column("subject_actor_id", sa.String(length=255), nullable=False),
        sa.Column("subject_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject_membership_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject_membership_version", sa.Integer(), nullable=True),
        sa.Column("subject_membership_active", sa.Boolean(), nullable=True),
        sa.Column("subject_roles_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "subject_permissions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("department_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_key", sa.String(length=100), nullable=False),
        sa.Column("department_version", sa.String(length=50), nullable=False),
        sa.Column("capability_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability_key", sa.String(length=100), nullable=False),
        sa.Column("capability_version", sa.String(length=50), nullable=False),
        sa.Column("work_category", sa.String(length=50), nullable=False),
        sa.Column("effect_classification", sa.String(length=40), nullable=False),
        sa.Column("action_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("action_digest", sa.String(length=64), nullable=False),
        sa.Column("digest_algorithm", sa.String(length=16), nullable=False),
        sa.Column("snapshot_schema_version", sa.SmallInteger(), nullable=False),
        sa.Column("policy_decision", sa.String(length=32), nullable=False),
        sa.Column("reason_codes_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("policy_set_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_set_key", sa.String(length=100), nullable=False),
        sa.Column("policy_set_version", sa.String(length=50), nullable=False),
        sa.Column("matched_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "subject_actor_type IN ('user', 'system')",
            name="ck_authorization_evidence_actor_type",
        ),
        sa.CheckConstraint(
            "btrim(subject_actor_id) <> ''",
            name="ck_authorization_evidence_actor_id_nonblank",
        ),
        sa.CheckConstraint(
            "operation = 'execute_capability'",
            name="ck_authorization_evidence_operation",
        ),
        sa.CheckConstraint(
            "policy_decision IN ('allow', 'deny', 'require_approval')",
            name="ck_authorization_evidence_decision",
        ),
        sa.CheckConstraint(
            "effect_classification IN "
            "('read_only', 'reversible', 'consequential', 'external_effect')",
            name="ck_authorization_evidence_effect",
        ),
        sa.CheckConstraint(
            "digest_algorithm = 'sha256' AND snapshot_schema_version = 1",
            name="ck_authorization_evidence_digest_version",
        ),
        sa.CheckConstraint(
            "action_digest ~ '^[0-9a-f]{64}$'",
            name="ck_authorization_evidence_digest",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(action_snapshot_json) = 'object' AND "
            "octet_length(action_snapshot_json::text) <= 131072",
            name="ck_authorization_evidence_snapshot",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(subject_roles_json) = 'array' AND "
            "octet_length(subject_roles_json::text) <= 16384 AND "
            "jsonb_typeof(subject_permissions_json) = 'array' AND "
            "octet_length(subject_permissions_json::text) <= 16384",
            name="ck_authorization_evidence_subject_arrays",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(reason_codes_json) = 'array' AND "
            "jsonb_array_length(reason_codes_json) > 0 AND "
            "octet_length(reason_codes_json::text) <= 16384 AND "
            "jsonb_typeof(matched_rules_json) = 'array' AND "
            "jsonb_array_length(matched_rules_json) > 0 AND "
            "octet_length(matched_rules_json::text) <= 32768",
            name="ck_authorization_evidence_policy_arrays",
        ),
        sa.CheckConstraint(
            "((subject_user_id IS NULL AND subject_membership_id IS NULL AND "
            "subject_membership_version IS NULL AND subject_membership_active IS NULL) OR "
            "(subject_user_id IS NOT NULL AND subject_membership_id IS NOT NULL AND "
            "subject_membership_version > 0 AND subject_membership_active IS NOT NULL))",
            name="ck_authorization_evidence_membership_snapshot",
        ),
        sa.CheckConstraint(
            "btrim(department_key) <> '' AND btrim(department_version) <> '' AND "
            "btrim(capability_key) <> '' AND btrim(capability_version) <> '' AND "
            "btrim(policy_set_key) <> '' AND btrim(policy_set_version) <> ''",
            name="ck_authorization_evidence_reference_nonblank",
        ),
        sa.CheckConstraint(
            "expires_at > evaluated_at",
            name="ck_authorization_evidence_expiry",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_authorization_evidence_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_authorization_evidence"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_authorization_evidence_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "policy_evaluation_id",
            name="uq_authorization_evidence_workspace_evaluation",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            "planning_request_id",
            "plan_id",
            "step_id",
            "action_digest",
            name="uq_authorization_evidence_exact_binding",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            "step_id",
            "action_digest",
            name="uq_authorization_evidence_step_binding",
        ),
    )
    op.create_index(
        "ix_authorization_evidence_workspace_plan_step",
        "authorization_evidence",
        ["workspace_id", "plan_id", "step_id", "evaluated_at"],
        unique=False,
    )
    op.create_index(
        "ix_authorization_evidence_workspace_digest_expiry",
        "authorization_evidence",
        ["workspace_id", "action_digest", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_authorization_evidence_workspace_correlation",
        "authorization_evidence",
        ["workspace_id", "correlation_id"],
        unique=False,
    )
    op.execute("ALTER TABLE authorization_evidence ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE authorization_evidence FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY authorization_evidence_workspace_isolation ON authorization_evidence
        FOR ALL
        USING (workspace_id = {_WORKSPACE_SETTING})
        WITH CHECK (workspace_id = {_WORKSPACE_SETTING})
        """
    )

    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("authorization_evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planning_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_digest", sa.String(length=64), nullable=False),
        sa.Column("requester_actor_type", sa.String(length=20), nullable=False),
        sa.Column("requester_actor_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "requester_actor_type IN ('user', 'system') AND btrim(requester_actor_id) <> ''",
            name="ck_approval_requests_actor",
        ),
        sa.CheckConstraint(
            "action_digest ~ '^[0-9a-f]{64}$' AND btrim(idempotency_key) <> ''",
            name="ck_approval_requests_binding",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired', 'cancelled', 'superseded')",
            name="ck_approval_requests_status",
        ),
        sa.CheckConstraint(
            "version > 0 AND expires_at > requested_at",
            name="ck_approval_requests_version_expiry",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND resolved_at IS NULL) OR "
            "(status <> 'pending' AND resolved_at IS NOT NULL)",
            name="ck_approval_requests_resolution",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_approval_requests_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "workspace_id",
                "authorization_evidence_id",
                "planning_request_id",
                "plan_id",
                "step_id",
                "action_digest",
            ],
            [
                "authorization_evidence.workspace_id",
                "authorization_evidence.id",
                "authorization_evidence.planning_request_id",
                "authorization_evidence.plan_id",
                "authorization_evidence.step_id",
                "authorization_evidence.action_digest",
            ],
            name="fk_approval_requests_workspace_evidence",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_approval_requests"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_approval_requests_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "authorization_evidence_id",
            name="uq_approval_requests_workspace_evidence",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_approval_requests_workspace_idempotency",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            "authorization_evidence_id",
            "action_digest",
            name="uq_approval_requests_exact_binding",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            "action_digest",
            name="uq_approval_requests_action_binding",
        ),
    )
    op.create_index(
        "ix_approval_requests_workspace_status_expiry",
        "approval_requests",
        ["workspace_id", "status", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_workspace_requester",
        "approval_requests",
        ["workspace_id", "requester_actor_id", "requested_at"],
        unique=False,
    )
    op.execute("ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE approval_requests FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY approval_requests_workspace_isolation ON approval_requests
        FOR ALL
        USING (workspace_id = {_WORKSPACE_SETTING})
        WITH CHECK (workspace_id = {_WORKSPACE_SETTING})
        """
    )

    op.create_table(
        "approval_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_digest", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("approver_actor_type", sa.String(length=20), nullable=False),
        sa.Column("approver_actor_id", sa.String(length=255), nullable=False),
        sa.Column("approver_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approver_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approver_membership_version", sa.Integer(), nullable=False),
        sa.Column("approver_roles_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "approver_permissions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("authority_rule_key", sa.String(length=100), nullable=False),
        sa.Column("authority_rule_version", sa.String(length=50), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('approved', 'rejected')",
            name="ck_approval_decisions_outcome",
        ),
        sa.CheckConstraint(
            "approver_actor_type = 'user' AND approver_membership_version > 0",
            name="ck_approval_decisions_approver",
        ),
        sa.CheckConstraint(
            "btrim(approver_actor_id) <> '' AND btrim(authority_rule_key) <> '' AND "
            "btrim(authority_rule_version) <> '' AND btrim(idempotency_key) <> ''",
            name="ck_approval_decisions_reference_nonblank",
        ),
        sa.CheckConstraint(
            "action_digest ~ '^[0-9a-f]{64}$'",
            name="ck_approval_decisions_digest",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(approver_roles_json) = 'array' AND "
            "jsonb_array_length(approver_roles_json) > 0 AND "
            "octet_length(approver_roles_json::text) <= 16384 AND "
            "jsonb_typeof(approver_permissions_json) = 'array' AND "
            "octet_length(approver_permissions_json::text) <= 16384",
            name="ck_approval_decisions_authority_arrays",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_approval_decisions_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "approval_request_id", "action_digest"],
            [
                "approval_requests.workspace_id",
                "approval_requests.id",
                "approval_requests.action_digest",
            ],
            name="fk_approval_decisions_workspace_request",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_approval_decisions"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_approval_decisions_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "approval_request_id",
            name="uq_approval_decisions_workspace_request",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_approval_decisions_workspace_idempotency",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            "approval_request_id",
            "action_digest",
            name="uq_approval_decisions_exact_binding",
        ),
    )
    op.create_index(
        "ix_approval_decisions_workspace_approver",
        "approval_decisions",
        ["workspace_id", "approver_membership_id", "decided_at"],
        unique=False,
    )
    op.execute("ALTER TABLE approval_decisions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE approval_decisions FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY approval_decisions_workspace_isolation ON approval_decisions
        FOR ALL
        USING (workspace_id = {_WORKSPACE_SETTING})
        WITH CHECK (workspace_id = {_WORKSPACE_SETTING})
        """
    )

    op.create_table(
        "execution_authorizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planning_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_type", sa.String(length=255), nullable=False),
        sa.Column("workflow_version", sa.String(length=50), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("digest_algorithm", sa.String(length=16), nullable=False),
        sa.Column("authorization_version", sa.SmallInteger(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "digest_algorithm = 'sha256' AND authorization_version = 1",
            name="ck_execution_authorizations_version",
        ),
        sa.CheckConstraint(
            "plan_digest ~ '^[0-9a-f]{64}$'",
            name="ck_execution_authorizations_digest",
        ),
        sa.CheckConstraint(
            "btrim(workflow_type) <> '' AND btrim(workflow_version) <> '' AND "
            "btrim(idempotency_key) <> ''",
            name="ck_execution_authorizations_reference_nonblank",
        ),
        sa.CheckConstraint(
            "expires_at > issued_at",
            name="ck_execution_authorizations_expiry",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_execution_authorizations_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_execution_authorizations"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_execution_authorizations_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_execution_authorizations_workspace_idempotency",
        ),
    )
    op.create_index(
        "ix_execution_authorizations_workspace_plan_expiry",
        "execution_authorizations",
        ["workspace_id", "plan_id", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_execution_authorizations_workspace_digest",
        "execution_authorizations",
        ["workspace_id", "plan_digest"],
        unique=False,
    )
    op.execute("ALTER TABLE execution_authorizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE execution_authorizations FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY execution_authorizations_workspace_isolation ON execution_authorizations
        FOR ALL
        USING (workspace_id = {_WORKSPACE_SETTING})
        WITH CHECK (workspace_id = {_WORKSPACE_SETTING})
        """
    )

    op.create_table(
        "execution_authorization_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_authorization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("action_digest", sa.String(length=64), nullable=False),
        sa.Column("authorization_evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "sequence >= 0",
            name="ck_execution_authorization_steps_sequence",
        ),
        sa.CheckConstraint(
            "action_digest ~ '^[0-9a-f]{64}$'",
            name="ck_execution_authorization_steps_digest",
        ),
        sa.CheckConstraint(
            "(approval_request_id IS NULL) = (approval_decision_id IS NULL)",
            name="ck_execution_authorization_steps_approval_pair",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_execution_authorization_steps_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "execution_authorization_id"],
            ["execution_authorizations.workspace_id", "execution_authorizations.id"],
            name="fk_execution_authorization_steps_authorization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "authorization_evidence_id", "step_id", "action_digest"],
            [
                "authorization_evidence.workspace_id",
                "authorization_evidence.id",
                "authorization_evidence.step_id",
                "authorization_evidence.action_digest",
            ],
            name="fk_execution_authorization_steps_evidence",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "workspace_id",
                "approval_request_id",
                "authorization_evidence_id",
                "action_digest",
            ],
            [
                "approval_requests.workspace_id",
                "approval_requests.id",
                "approval_requests.authorization_evidence_id",
                "approval_requests.action_digest",
            ],
            name="fk_execution_authorization_steps_approval_request",
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
            name="fk_execution_authorization_steps_approval_decision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_execution_authorization_steps"),
        sa.UniqueConstraint(
            "workspace_id", "id", name="uq_execution_authorization_steps_workspace_id"
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "execution_authorization_id",
            "step_id",
            name="uq_execution_authorization_steps_step",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "execution_authorization_id",
            "sequence",
            name="uq_execution_authorization_steps_sequence",
        ),
    )
    op.execute("ALTER TABLE execution_authorization_steps ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE execution_authorization_steps FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY execution_authorization_steps_workspace_isolation
        ON execution_authorization_steps
        FOR ALL
        USING (workspace_id = {_WORKSPACE_SETTING})
        WITH CHECK (workspace_id = {_WORKSPACE_SETTING})
        """
    )

    op.add_column(
        "execution_requests",
        sa.Column("execution_authorization_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_execution_requests_workspace_authorization",
        "execution_requests",
        "execution_authorizations",
        ["workspace_id", "execution_authorization_id"],
        ["workspace_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_execution_requests_workspace_authorization",
        "execution_requests",
        ["workspace_id", "execution_authorization_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_execution_requests_workspace_authorization",
        "execution_requests",
        type_="unique",
    )
    op.drop_constraint(
        "fk_execution_requests_workspace_authorization",
        "execution_requests",
        type_="foreignkey",
    )
    op.drop_column("execution_requests", "execution_authorization_id")

    op.execute(
        "DROP POLICY execution_authorization_steps_workspace_isolation "
        "ON execution_authorization_steps"
    )
    op.drop_table("execution_authorization_steps")

    op.execute(
        "DROP POLICY execution_authorizations_workspace_isolation ON execution_authorizations"
    )
    op.drop_index(
        "ix_execution_authorizations_workspace_digest",
        table_name="execution_authorizations",
    )
    op.drop_index(
        "ix_execution_authorizations_workspace_plan_expiry",
        table_name="execution_authorizations",
    )
    op.drop_table("execution_authorizations")

    op.execute("DROP POLICY approval_decisions_workspace_isolation ON approval_decisions")
    op.drop_index(
        "ix_approval_decisions_workspace_approver",
        table_name="approval_decisions",
    )
    op.drop_table("approval_decisions")

    op.execute("DROP POLICY approval_requests_workspace_isolation ON approval_requests")
    op.drop_index(
        "ix_approval_requests_workspace_requester",
        table_name="approval_requests",
    )
    op.drop_index(
        "ix_approval_requests_workspace_status_expiry",
        table_name="approval_requests",
    )
    op.drop_table("approval_requests")

    op.execute("DROP POLICY authorization_evidence_workspace_isolation ON authorization_evidence")
    op.drop_index(
        "ix_authorization_evidence_workspace_correlation",
        table_name="authorization_evidence",
    )
    op.drop_index(
        "ix_authorization_evidence_workspace_digest_expiry",
        table_name="authorization_evidence",
    )
    op.drop_index(
        "ix_authorization_evidence_workspace_plan_step",
        table_name="authorization_evidence",
    )
    op.drop_table("authorization_evidence")
