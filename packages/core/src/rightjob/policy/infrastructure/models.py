"""Policy/Approval-owned SQLAlchemy mappings for the Phase 2.12 proposal."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from rightjob.shared.sqlalchemy import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column


class AuthorizationEvidenceRecord(Base):
    __tablename__ = "authorization_evidence"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_authorization_evidence_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "policy_evaluation_id",
            name="uq_authorization_evidence_workspace_evaluation",
        ),
        UniqueConstraint(
            "workspace_id",
            "id",
            "planning_request_id",
            "plan_id",
            "step_id",
            "action_digest",
            name="uq_authorization_evidence_exact_binding",
        ),
        UniqueConstraint(
            "workspace_id",
            "id",
            "step_id",
            "action_digest",
            name="uq_authorization_evidence_step_binding",
        ),
        CheckConstraint(
            "subject_actor_type IN ('user', 'system')", name="ck_authorization_evidence_actor_type"
        ),
        CheckConstraint(
            "btrim(subject_actor_id) <> ''",
            name="ck_authorization_evidence_actor_id_nonblank",
        ),
        CheckConstraint(
            "operation = 'execute_capability'", name="ck_authorization_evidence_operation"
        ),
        CheckConstraint(
            "policy_decision IN ('allow', 'deny', 'require_approval')",
            name="ck_authorization_evidence_decision",
        ),
        CheckConstraint(
            "effect_classification IN "
            "('read_only', 'reversible', 'consequential', 'external_effect')",
            name="ck_authorization_evidence_effect",
        ),
        CheckConstraint(
            "digest_algorithm = 'sha256' AND snapshot_schema_version = 1",
            name="ck_authorization_evidence_digest_version",
        ),
        CheckConstraint(
            "action_digest ~ '^[0-9a-f]{64}$'", name="ck_authorization_evidence_digest"
        ),
        CheckConstraint(
            "jsonb_typeof(action_snapshot_json) = 'object' AND "
            "octet_length(action_snapshot_json::text) <= 131072",
            name="ck_authorization_evidence_snapshot",
        ),
        CheckConstraint(
            "jsonb_typeof(subject_roles_json) = 'array' AND "
            "octet_length(subject_roles_json::text) <= 16384 AND "
            "jsonb_typeof(subject_permissions_json) = 'array' AND "
            "octet_length(subject_permissions_json::text) <= 16384",
            name="ck_authorization_evidence_subject_arrays",
        ),
        CheckConstraint(
            "jsonb_typeof(reason_codes_json) = 'array' AND "
            "jsonb_array_length(reason_codes_json) > 0 AND "
            "octet_length(reason_codes_json::text) <= 16384 AND "
            "jsonb_typeof(matched_rules_json) = 'array' AND "
            "jsonb_array_length(matched_rules_json) > 0 AND "
            "octet_length(matched_rules_json::text) <= 32768",
            name="ck_authorization_evidence_policy_arrays",
        ),
        CheckConstraint(
            "((subject_user_id IS NULL AND subject_membership_id IS NULL AND "
            "subject_membership_version IS NULL AND subject_membership_active IS NULL) OR "
            "(subject_user_id IS NOT NULL AND subject_membership_id IS NOT NULL AND "
            "subject_membership_version > 0 AND subject_membership_active IS NOT NULL))",
            name="ck_authorization_evidence_membership_snapshot",
        ),
        CheckConstraint(
            "btrim(department_key) <> '' AND btrim(department_version) <> '' AND "
            "btrim(capability_key) <> '' AND btrim(capability_version) <> '' AND "
            "btrim(policy_set_key) <> '' AND btrim(policy_set_version) <> ''",
            name="ck_authorization_evidence_reference_nonblank",
        ),
        CheckConstraint("expires_at > evaluated_at", name="ck_authorization_evidence_expiry"),
        Index(
            "ix_authorization_evidence_workspace_plan_step",
            "workspace_id",
            "plan_id",
            "step_id",
            "evaluated_at",
        ),
        Index(
            "ix_authorization_evidence_workspace_digest_expiry",
            "workspace_id",
            "action_digest",
            "expires_at",
        ),
        Index("ix_authorization_evidence_workspace_correlation", "workspace_id", "correlation_id"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "workspaces.id", name="fk_authorization_evidence_workspace", ondelete="RESTRICT"
        ),
        nullable=False,
    )
    policy_evaluation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    planning_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    step_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    subject_actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    subject_membership_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    subject_membership_version: Mapped[int | None] = mapped_column(Integer)
    subject_membership_active: Mapped[bool | None] = mapped_column(Boolean)
    subject_roles_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    subject_permissions_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    department_definition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    department_key: Mapped[str] = mapped_column(String(100), nullable=False)
    department_version: Mapped[str] = mapped_column(String(50), nullable=False)
    capability_definition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    capability_key: Mapped[str] = mapped_column(String(100), nullable=False)
    capability_version: Mapped[str] = mapped_column(String(50), nullable=False)
    work_category: Mapped[str] = mapped_column(String(50), nullable=False)
    effect_classification: Mapped[str] = mapped_column(String(40), nullable=False)
    action_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    action_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    digest_algorithm: Mapped[str] = mapped_column(String(16), nullable=False)
    snapshot_schema_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    policy_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_codes_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    policy_set_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    policy_set_key: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_set_version: Mapped[str] = mapped_column(String(50), nullable=False)
    matched_rules_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))


class ApprovalRequestRecord(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_approval_requests_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "authorization_evidence_id",
            name="uq_approval_requests_workspace_evidence",
        ),
        UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_approval_requests_workspace_idempotency"
        ),
        UniqueConstraint(
            "workspace_id",
            "id",
            "authorization_evidence_id",
            "action_digest",
            name="uq_approval_requests_exact_binding",
        ),
        UniqueConstraint(
            "workspace_id",
            "id",
            "action_digest",
            name="uq_approval_requests_action_binding",
        ),
        ForeignKeyConstraint(
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
        CheckConstraint(
            "requester_actor_type IN ('user', 'system') AND btrim(requester_actor_id) <> ''",
            name="ck_approval_requests_actor",
        ),
        CheckConstraint(
            "action_digest ~ '^[0-9a-f]{64}$' AND btrim(idempotency_key) <> ''",
            name="ck_approval_requests_binding",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired', 'cancelled', 'superseded')",
            name="ck_approval_requests_status",
        ),
        CheckConstraint(
            "version > 0 AND expires_at > requested_at", name="ck_approval_requests_version_expiry"
        ),
        CheckConstraint(
            "(status = 'pending' AND resolved_at IS NULL) OR "
            "(status <> 'pending' AND resolved_at IS NOT NULL)",
            name="ck_approval_requests_resolution",
        ),
        Index(
            "ix_approval_requests_workspace_status_expiry", "workspace_id", "status", "expires_at"
        ),
        Index(
            "ix_approval_requests_workspace_requester",
            "workspace_id",
            "requester_actor_id",
            "requested_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", name="fk_approval_requests_workspace", ondelete="RESTRICT"),
        nullable=False,
    )
    authorization_evidence_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    planning_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    step_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    requester_actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    requester_actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class ApprovalDecisionRecord(Base):
    __tablename__ = "approval_decisions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_approval_decisions_workspace_id"),
        UniqueConstraint(
            "workspace_id", "approval_request_id", name="uq_approval_decisions_workspace_request"
        ),
        UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_approval_decisions_workspace_idempotency"
        ),
        UniqueConstraint(
            "workspace_id",
            "id",
            "approval_request_id",
            "action_digest",
            name="uq_approval_decisions_exact_binding",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "approval_request_id", "action_digest"],
            [
                "approval_requests.workspace_id",
                "approval_requests.id",
                "approval_requests.action_digest",
            ],
            name="fk_approval_decisions_workspace_request",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "outcome IN ('approved', 'rejected')", name="ck_approval_decisions_outcome"
        ),
        CheckConstraint(
            "approver_actor_type = 'user' AND approver_membership_version > 0",
            name="ck_approval_decisions_approver",
        ),
        CheckConstraint(
            "btrim(approver_actor_id) <> '' AND btrim(authority_rule_key) <> '' AND "
            "btrim(authority_rule_version) <> '' AND btrim(idempotency_key) <> ''",
            name="ck_approval_decisions_reference_nonblank",
        ),
        CheckConstraint(
            "action_digest ~ '^[0-9a-f]{64}$'",
            name="ck_approval_decisions_digest",
        ),
        CheckConstraint(
            "jsonb_typeof(approver_roles_json) = 'array' AND "
            "jsonb_array_length(approver_roles_json) > 0 AND "
            "octet_length(approver_roles_json::text) <= 16384 AND "
            "jsonb_typeof(approver_permissions_json) = 'array' AND "
            "octet_length(approver_permissions_json::text) <= 16384",
            name="ck_approval_decisions_authority_arrays",
        ),
        Index(
            "ix_approval_decisions_workspace_approver",
            "workspace_id",
            "approver_membership_id",
            "decided_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", name="fk_approval_decisions_workspace", ondelete="RESTRICT"),
        nullable=False,
    )
    approval_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    approver_actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    approver_actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    approver_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    approver_membership_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    approver_membership_version: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_roles_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    approver_permissions_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    authority_rule_key: Mapped[str] = mapped_column(String(100), nullable=False)
    authority_rule_version: Mapped[str] = mapped_column(String(50), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)


class ExecutionAuthorizationRecord(Base):
    __tablename__ = "execution_authorizations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_execution_authorizations_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_execution_authorizations_workspace_idempotency",
        ),
        CheckConstraint(
            "digest_algorithm = 'sha256' AND authorization_version = 1",
            name="ck_execution_authorizations_version",
        ),
        CheckConstraint(
            "plan_digest ~ '^[0-9a-f]{64}$'",
            name="ck_execution_authorizations_digest",
        ),
        CheckConstraint(
            "btrim(workflow_type) <> '' AND btrim(workflow_version) <> '' AND "
            "btrim(idempotency_key) <> ''",
            name="ck_execution_authorizations_reference_nonblank",
        ),
        CheckConstraint("expires_at > issued_at", name="ck_execution_authorizations_expiry"),
        Index(
            "ix_execution_authorizations_workspace_plan_expiry",
            "workspace_id",
            "plan_id",
            "expires_at",
        ),
        Index("ix_execution_authorizations_workspace_digest", "workspace_id", "plan_digest"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "workspaces.id", name="fk_execution_authorizations_workspace", ondelete="RESTRICT"
        ),
        nullable=False,
    )
    planning_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    workflow_definition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(50), nullable=False)
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    digest_algorithm: Mapped[str] = mapped_column(String(16), nullable=False)
    authorization_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)


class ExecutionAuthorizationStepRecord(Base):
    __tablename__ = "execution_authorization_steps"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "id", name="uq_execution_authorization_steps_workspace_id"
        ),
        UniqueConstraint(
            "workspace_id",
            "execution_authorization_id",
            "step_id",
            name="uq_execution_authorization_steps_step",
        ),
        UniqueConstraint(
            "workspace_id",
            "execution_authorization_id",
            "sequence",
            name="uq_execution_authorization_steps_sequence",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "execution_authorization_id"],
            ["execution_authorizations.workspace_id", "execution_authorizations.id"],
            name="fk_execution_authorization_steps_authorization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
        CheckConstraint("sequence >= 0", name="ck_execution_authorization_steps_sequence"),
        CheckConstraint(
            "action_digest ~ '^[0-9a-f]{64}$'",
            name="ck_execution_authorization_steps_digest",
        ),
        CheckConstraint(
            "(approval_request_id IS NULL) = (approval_decision_id IS NULL)",
            name="ck_execution_authorization_steps_approval_pair",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "workspaces.id", name="fk_execution_authorization_steps_workspace", ondelete="RESTRICT"
        ),
        nullable=False,
    )
    execution_authorization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    step_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    action_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_evidence_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    approval_request_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    approval_decision_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
