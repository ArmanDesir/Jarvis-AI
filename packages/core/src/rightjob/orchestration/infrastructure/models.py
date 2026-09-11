"""Proposed Phase 2.7 SQLAlchemy mappings; no migration is created here."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from rightjob.shared.sqlalchemy import Base


class ExecutionRequestRecord(Base):
    __tablename__ = "execution_requests"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_execution_requests_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "execution_authorization_id",
            name="uq_execution_requests_workspace_authorization",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "execution_authorization_id"],
            ["execution_authorizations.workspace_id", "execution_authorizations.id"],
            name="fk_execution_requests_workspace_authorization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "revision_authorization_evidence_id"],
            ["authorization_evidence.workspace_id", "authorization_evidence.id"],
            name="fk_execution_requests_workspace_revision_authorization",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(execution_authorization_id IS NULL) <> (revision_authorization_evidence_id IS NULL)",
            name="ck_execution_requests_authorization_kind",
        ),
        CheckConstraint(
            "actor_type IN ('user', 'system')",
            name="ck_execution_requests_actor_type",
        ),
        CheckConstraint("btrim(actor_id) <> ''", name="ck_execution_requests_actor_id_nonblank"),
        CheckConstraint(
            "btrim(workflow_type) <> ''", name="ck_execution_requests_workflow_type_nonblank"
        ),
        CheckConstraint(
            "btrim(workflow_version) <> ''",
            name="ck_execution_requests_workflow_version_nonblank",
        ),
        CheckConstraint(
            "jsonb_typeof(input_json) = 'object'", name="ck_execution_requests_input_object"
        ),
        CheckConstraint(
            "octet_length(input_json::text) <= 65536",
            name="ck_execution_requests_input_size",
        ),
        Index("ix_execution_requests_workspace_created", "workspace_id", "created_at"),
        Index("ix_execution_requests_workspace_correlation", "workspace_id", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", name="fk_execution_requests_workspace", ondelete="RESTRICT"),
        nullable=False,
    )
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    initiator_type: Mapped[str] = mapped_column(String(20), nullable=False)
    execution_authorization_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    revision_authorization_evidence_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    workflow_definition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(50), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RevisionExecutionClaimRecord(Base):
    __tablename__ = "revision_execution_claims"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_revision_execution_claims_workspace_id"),
        UniqueConstraint(
            "workspace_id", "command_id", name="uq_revision_execution_claims_workspace_command"
        ),
        UniqueConstraint(
            "workspace_id",
            "quality_gate_id",
            "quality_decision_id",
            "reserved_cycle",
            name="uq_revision_execution_claims_gate_decision_cycle",
        ),
        CheckConstraint("reserved_cycle IN (1,2)", name="ck_revision_execution_claims_cycle"),
        CheckConstraint(
            "action_type = 'regenerate_artifact'", name="ck_revision_execution_claims_action"
        ),
        CheckConstraint(
            "status IN ('claimed','launch_pending','running','completed','failed',"
            "'cancelled','reconciliation_required')",
            name="ck_revision_execution_claims_status",
        ),
        CheckConstraint(
            "(status = 'claimed') = (workflow_id IS NULL)",
            name="ck_revision_execution_claims_workflow_state",
        ),
        CheckConstraint(
            "status = 'claimed' OR launch_pending_at IS NOT NULL",
            name="ck_revision_execution_claims_launch_timestamp",
        ),
        CheckConstraint(
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
        CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name="ck_revision_execution_claims_completed_timestamp",
        ),
        CheckConstraint(
            "(status = 'failed') = (failed_at IS NOT NULL)",
            name="ck_revision_execution_claims_failed_timestamp",
        ),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)",
            name="ck_revision_execution_claims_cancelled_timestamp",
        ),
        CheckConstraint(
            "status <> 'reconciliation_required' OR reconciliation_required_at IS NOT NULL",
            name="ck_revision_execution_claims_reconciliation_timestamp",
        ),
        CheckConstraint(
            "lifecycle_reason IS NULL OR lifecycle_reason IN "
            "('launch_rejected','launch_outcome_unknown','execution_failed',"
            "'validation_failed','cancelled_by_request','workflow_failed',"
            "'workflow_cancelled','workflow_terminated','workflow_timed_out')",
            name="ck_revision_execution_claims_reason",
        ),
        CheckConstraint(
            "(result_artifact_id IS NULL) = (result_artifact_version IS NULL) AND "
            "(result_artifact_id IS NULL) = (result_artifact_sha256 IS NULL) AND "
            "(result_artifact_id IS NULL) = (result_validation_evidence_id IS NULL)",
            name="ck_revision_execution_claims_result_pair",
        ),
        CheckConstraint(
            "(status = 'completed') = (result_artifact_id IS NOT NULL)",
            name="ck_revision_execution_claims_completed_result",
        ),
        CheckConstraint(
            "(status IN ('failed','cancelled','reconciliation_required')) = "
            "(lifecycle_reason IS NOT NULL)",
            name="ck_revision_execution_claims_reason_required",
        ),
        CheckConstraint(
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
        CheckConstraint("version > 0", name="ck_revision_execution_claims_version"),
        UniqueConstraint(
            "workspace_id", "workflow_id", name="uq_revision_execution_claims_workspace_workflow"
        ),
        Index(
            "ix_revision_execution_claims_workspace_gate_status",
            "workspace_id",
            "quality_gate_id",
            "status",
        ),
        Index(
            "ix_revision_execution_claims_workspace_authorization",
            "workspace_id",
            "authorization_evidence_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    quality_gate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    quality_decision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reserved_cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    planning_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_step_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    department_definition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    department_key: Mapped[str] = mapped_column(String(100), nullable=False)
    department_version: Mapped[str] = mapped_column(String(50), nullable=False)
    capability_definition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    capability_key: Mapped[str] = mapped_column(String(100), nullable=False)
    capability_version: Mapped[str] = mapped_column(String(50), nullable=False)
    quality_policy_key: Mapped[str] = mapped_column(String(100), nullable=False)
    quality_policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    action_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    prior_execution_authorization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    authorization_evidence_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    approval_request_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    approval_decision_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_artifact_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_artifact_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    target_artifact_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    target_artifact_version: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    execution_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    execution_step_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    workflow_id: Mapped[str | None] = mapped_column(String(255))
    lifecycle_reason: Mapped[str | None] = mapped_column(String(40))
    launch_pending_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    running_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconciliation_required_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_artifact_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    result_artifact_version: Mapped[int | None] = mapped_column(Integer)
    result_artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    result_validation_evidence_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    last_lifecycle_command_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    last_lifecycle_command_digest: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExecutionRunRecord(Base):
    __tablename__ = "execution_runs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_execution_runs_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "execution_request_id",
            name="uq_execution_runs_workspace_request",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "execution_request_id"],
            ["execution_requests.workspace_id", "execution_requests.id"],
            name="fk_execution_runs_workspace_request",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "actor_type IN ('user', 'system')",
            name="ck_execution_runs_actor_type",
        ),
        CheckConstraint("btrim(actor_id) <> ''", name="ck_execution_runs_actor_id_nonblank"),
        CheckConstraint(
            "btrim(workflow_type) <> ''", name="ck_execution_runs_workflow_type_nonblank"
        ),
        CheckConstraint(
            "btrim(workflow_version) <> ''",
            name="ck_execution_runs_workflow_version_nonblank",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'waiting', 'succeeded', 'failed', "
            "'cancelled', 'reconciliation_required')",
            name="ck_execution_runs_status",
        ),
        CheckConstraint(
            "reconciliation_state IN ('not_required', 'required', 'resolved')",
            name="ck_execution_runs_reconciliation_state",
        ),
        CheckConstraint("version > 0", name="ck_execution_runs_version"),
        Index("ix_execution_runs_workspace_status_created", "workspace_id", "status", "created_at"),
        Index("ix_execution_runs_workspace_correlation", "workspace_id", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", name="fk_execution_runs_workspace", ondelete="RESTRICT"),
        nullable=False,
    )
    execution_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    workflow_definition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    initiator_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciliation_state: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class ExecutionStepRecord(Base):
    __tablename__ = "execution_steps"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_execution_steps_workspace_id"),
        UniqueConstraint(
            "workspace_id", "id", "run_id", name="uq_execution_steps_workspace_id_run"
        ),
        UniqueConstraint(
            "workspace_id", "run_id", "sequence", name="uq_execution_steps_workspace_run_sequence"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "run_id"],
            ["execution_runs.workspace_id", "execution_runs.id"],
            name="fk_execution_steps_workspace_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'waiting', 'succeeded', 'failed', "
            "'cancelled', 'reconciliation_required')",
            name="ck_execution_steps_status",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts > 0 AND attempt_count <= max_attempts",
            name="ck_execution_steps_attempts",
        ),
        CheckConstraint(
            "failure_classification IS NULL OR failure_classification IN "
            "('validation', 'business', 'infrastructure_transient', "
            "'infrastructure_exhausted', 'cancelled', 'unknown_outcome', 'internal_defect')",
            name="ck_execution_steps_failure_classification",
        ),
        CheckConstraint("sequence >= 0", name="ck_execution_steps_sequence"),
        CheckConstraint(
            "(status = 'failed' AND failure_classification IS NOT NULL) OR "
            "(status = 'reconciliation_required' AND "
            "failure_classification = 'unknown_outcome') OR "
            "(status NOT IN ('failed', 'reconciliation_required') AND "
            "failure_classification IS NULL)",
            name="ck_execution_steps_status_failure",
        ),
        CheckConstraint("btrim(step_type) <> ''", name="ck_execution_steps_step_type_nonblank"),
        CheckConstraint("btrim(input_ref) <> ''", name="ck_execution_steps_input_ref_nonblank"),
        CheckConstraint(
            "output_evidence_ref IS NULL OR btrim(output_evidence_ref) <> ''",
            name="ck_execution_steps_output_evidence_ref_nonblank",
        ),
        CheckConstraint("version > 0", name="ck_execution_steps_version"),
        Index("ix_execution_steps_workspace_status", "workspace_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", name="fk_execution_steps_workspace", ondelete="RESTRICT"),
        nullable=False,
    )
    step_type: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    input_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    output_evidence_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_classification: Mapped[str | None] = mapped_column(String(40), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class QualityGateStateRecord(Base):
    __tablename__ = "quality_gate_states"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    step_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    capability_definition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    capability_key: Mapped[str] = mapped_column(String(255), nullable=False)
    capability_version: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_key: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    criteria_key: Mapped[str] = mapped_column(String(255), nullable=False)
    criteria_version: Mapped[str] = mapped_column(String(50), nullable=False)
    score_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    automated_revision_count: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_score: Mapped[int] = mapped_column(Integer, nullable=False)
    last_score: Mapped[int] = mapped_column(Integer, nullable=False)
    last_artifact_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    last_artifact_version: Mapped[int] = mapped_column(Integer, nullable=False)
    last_artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    last_validation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    last_assessment_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    last_decision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QualityGateDecisionRecord(Base):
    __tablename__ = "quality_gate_decisions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    command_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    quality_gate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    step_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    capability_definition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    capability_key: Mapped[str] = mapped_column(String(255), nullable=False)
    capability_version: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_key: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    criteria_key: Mapped[str] = mapped_column(String(255), nullable=False)
    criteria_version: Mapped[str] = mapped_column(String(50), nullable=False)
    score_key: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_score: Mapped[int] = mapped_column(Integer, nullable=False)
    prior_score: Mapped[int | None] = mapped_column(Integer)
    artifact_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    artifact_version: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    assessment_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    revision_count_before: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_count_after: Mapped[int] = mapped_column(Integer, nullable=False)
    state_version_before: Mapped[int | None] = mapped_column(Integer)
    state_version_after: Mapped[int] = mapped_column(Integer, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
