"""Workspace-scoped SQLAlchemy execution repositories."""

from __future__ import annotations

from typing import Any, Sequence, cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from rightjob.contracts.capabilities import CapabilityReference, SemanticVersion
from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.review import ArtifactReference
from rightjob.contracts.revision import (
    QualityGateCommand,
    QualityGateDecision,
    QualityGateDecisionEvidence,
    QualityGateOutcome,
    QualityGateReason,
    QualityGateState,
    QualityGateStatus,
)
from rightjob.orchestration.application.repositories import (
    ConcurrentExecutionUpdateError,
    ConcurrentQualityGateUpdateError,
)
from rightjob.orchestration.domain import (
    ExecutionRequest,
    ExecutionRun,
    ExecutionStep,
    FailureClassification,
    InitiatorType,
    ReconciliationState,
    RunStatus,
    StepStatus,
)
from rightjob.orchestration.infrastructure.models import (
    ExecutionRequestRecord,
    ExecutionRunRecord,
    ExecutionStepRecord,
    QualityGateDecisionRecord,
    QualityGateStateRecord,
)


def _scope(session: Session, workspace_id: UUID) -> None:
    session.execute(select(func.set_config("app.current_workspace_id", str(workspace_id), True)))


def _require_scope(workspace_id: UUID, record_workspace_id: UUID) -> None:
    if workspace_id != record_workspace_id:
        raise ValueError("record workspace must match repository scope")


def _require_updated(result: Any) -> None:
    if cast(CursorResult[Any], result).rowcount != 1:
        raise ConcurrentExecutionUpdateError("execution was changed or removed")


def _run(record: ExecutionRunRecord) -> ExecutionRun:
    return ExecutionRun(
        id=record.id,
        execution_request_id=record.execution_request_id,
        workspace_id=record.workspace_id,
        workflow_definition_id=record.workflow_definition_id,
        workflow_type=record.workflow_type,
        workflow_version=record.workflow_version,
        status=RunStatus(record.status),
        correlation_id=record.correlation_id,
        causation_id=record.causation_id,
        actor=Actor(ActorType(record.actor_type), record.actor_id),
        initiator_type=InitiatorType(record.initiator_type),
        created_at=record.created_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        cancellation_requested_at=record.cancellation_requested_at,
        cancelled_at=record.cancelled_at,
        reconciliation_state=ReconciliationState(record.reconciliation_state),
        version=record.version,
    )


def _step(record: ExecutionStepRecord) -> ExecutionStep:
    return ExecutionStep(
        id=record.id,
        run_id=record.run_id,
        workspace_id=record.workspace_id,
        step_type=record.step_type,
        sequence=record.sequence,
        status=StepStatus(record.status),
        attempt_count=record.attempt_count,
        max_attempts=record.max_attempts,
        input_ref=record.input_ref,
        output_evidence_ref=record.output_evidence_ref,
        started_at=record.started_at,
        completed_at=record.completed_at,
        failure_classification=(
            FailureClassification(record.failure_classification)
            if record.failure_classification
            else None
        ),
        version=record.version,
    )


class SqlAlchemyExecutionRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, workspace_id: UUID, request: ExecutionRequest) -> None:
        _require_scope(workspace_id, request.workspace_id)
        _scope(self._session, workspace_id)
        self._session.add(
            ExecutionRequestRecord(
                id=request.execution_id,
                workspace_id=request.workspace_id,
                correlation_id=request.correlation_id,
                causation_id=request.causation_id,
                actor_type=request.actor.type.value,
                actor_id=request.actor.id,
                initiator_type=request.initiator_type.value,
                execution_authorization_id=request.authorization.execution_authorization_id,
                workflow_definition_id=request.workflow_definition_id,
                workflow_type=request.workflow_type,
                workflow_version=request.workflow_version,
                input_json=request.input,
                created_at=request.created_at,
            )
        )


class SqlAlchemyExecutionRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, workspace_id: UUID, run: ExecutionRun) -> None:
        _require_scope(workspace_id, run.workspace_id)
        _scope(self._session, workspace_id)
        self._session.add(ExecutionRunRecord(**self._values(run)))

    def get(self, workspace_id: UUID, run_id: UUID) -> ExecutionRun | None:
        _scope(self._session, workspace_id)
        record = self._session.scalar(
            select(ExecutionRunRecord).where(
                ExecutionRunRecord.workspace_id == workspace_id,
                ExecutionRunRecord.id == run_id,
            )
        )
        return _run(record) if record else None

    def save(self, workspace_id: UUID, run: ExecutionRun, expected_version: int) -> None:
        _require_scope(workspace_id, run.workspace_id)
        if run.version != expected_version + 1:
            raise ValueError("saved run must increment version exactly once")
        _scope(self._session, workspace_id)
        values = self._values(run)
        values.pop("id")
        values.pop("workspace_id")
        result = self._session.execute(
            update(ExecutionRunRecord)
            .where(
                ExecutionRunRecord.workspace_id == workspace_id,
                ExecutionRunRecord.id == run.id,
                ExecutionRunRecord.version == expected_version,
            )
            .values(**values)
        )
        _require_updated(result)

    @staticmethod
    def _values(run: ExecutionRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "execution_request_id": run.execution_request_id,
            "workspace_id": run.workspace_id,
            "workflow_definition_id": run.workflow_definition_id,
            "workflow_type": run.workflow_type,
            "workflow_version": run.workflow_version,
            "status": run.status.value,
            "correlation_id": run.correlation_id,
            "causation_id": run.causation_id,
            "actor_type": run.actor.type.value,
            "actor_id": run.actor.id,
            "initiator_type": run.initiator_type.value,
            "created_at": run.created_at,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "cancellation_requested_at": run.cancellation_requested_at,
            "cancelled_at": run.cancelled_at,
            "reconciliation_state": run.reconciliation_state.value,
            "version": run.version,
        }


class SqlAlchemyExecutionStepRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_all(self, workspace_id: UUID, steps: Sequence[ExecutionStep]) -> None:
        for step in steps:
            _require_scope(workspace_id, step.workspace_id)
        _scope(self._session, workspace_id)
        self._session.add_all(ExecutionStepRecord(**self._values(step)) for step in steps)

    def get(self, workspace_id: UUID, step_id: UUID) -> ExecutionStep | None:
        _scope(self._session, workspace_id)
        record = self._session.scalar(
            select(ExecutionStepRecord).where(
                ExecutionStepRecord.workspace_id == workspace_id,
                ExecutionStepRecord.id == step_id,
            )
        )
        return _step(record) if record else None

    def list_for_run(self, workspace_id: UUID, run_id: UUID) -> Sequence[ExecutionStep]:
        _scope(self._session, workspace_id)
        records = self._session.scalars(
            select(ExecutionStepRecord)
            .where(
                ExecutionStepRecord.workspace_id == workspace_id,
                ExecutionStepRecord.run_id == run_id,
            )
            .order_by(ExecutionStepRecord.sequence)
        )
        return [_step(record) for record in records]

    def save(self, workspace_id: UUID, step: ExecutionStep, expected_version: int) -> None:
        _require_scope(workspace_id, step.workspace_id)
        if step.version != expected_version + 1:
            raise ValueError("saved step must increment version exactly once")
        _scope(self._session, workspace_id)
        values = self._values(step)
        values.pop("id")
        values.pop("workspace_id")
        result = self._session.execute(
            update(ExecutionStepRecord)
            .where(
                ExecutionStepRecord.workspace_id == workspace_id,
                ExecutionStepRecord.id == step.id,
                ExecutionStepRecord.version == expected_version,
            )
            .values(**values)
        )
        _require_updated(result)

    @staticmethod
    def _values(step: ExecutionStep) -> dict[str, Any]:
        return {
            "id": step.id,
            "run_id": step.run_id,
            "workspace_id": step.workspace_id,
            "step_type": step.step_type,
            "sequence": step.sequence,
            "status": step.status.value,
            "attempt_count": step.attempt_count,
            "max_attempts": step.max_attempts,
            "input_ref": step.input_ref,
            "output_evidence_ref": step.output_evidence_ref,
            "started_at": step.started_at,
            "completed_at": step.completed_at,
            "failure_classification": (
                step.failure_classification.value if step.failure_classification else None
            ),
            "version": step.version,
        }


def _quality_state(record: QualityGateStateRecord) -> QualityGateState:
    return QualityGateState(
        record.id,
        record.workspace_id,
        record.run_id,
        record.step_id,
        record.correlation_id,
        record.causation_id,
        CapabilityReference(
            record.capability_definition_id,
            record.capability_key,
            SemanticVersion.parse(record.capability_version),
        ),
        record.policy_key,
        SemanticVersion.parse(record.policy_version),
        record.criteria_key,
        SemanticVersion.parse(record.criteria_version),
        record.score_key,
        QualityGateStatus(record.status),
        record.automated_revision_count,
        ArtifactReference(
            record.last_artifact_id,
            record.last_artifact_version,
            record.last_artifact_sha256,
        ),
        record.last_validation_id,
        record.last_assessment_id,
        record.last_score,
        record.last_decision_id,
        record.version,
        record.updated_at,
    )


def _state_values(state: QualityGateState, minimum_score: int) -> dict[str, Any]:
    return {
        "id": state.quality_gate_id,
        "workspace_id": state.workspace_id,
        "run_id": state.run_id,
        "step_id": state.step_id,
        "correlation_id": state.correlation_id,
        "causation_id": state.causation_id,
        "capability_definition_id": state.capability.capability_definition_id,
        "capability_key": state.capability.capability_key,
        "capability_version": str(state.capability.semantic_version),
        "policy_key": state.policy_key,
        "policy_version": str(state.policy_version),
        "criteria_key": state.criteria_key,
        "criteria_version": str(state.criteria_version),
        "score_key": state.score_key,
        "status": state.status.value,
        "automated_revision_count": state.automated_revision_count,
        "minimum_score": minimum_score,
        "last_score": state.last_score,
        "last_artifact_id": state.last_artifact.artifact_id,
        "last_artifact_version": state.last_artifact.version,
        "last_artifact_sha256": state.last_artifact.sha256,
        "last_validation_id": state.last_validation_id,
        "last_assessment_id": state.last_assessment_id,
        "last_decision_id": state.last_decision_id,
        "version": state.version,
        "updated_at": state.updated_at,
    }


class SqlAlchemyQualityGateStateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, workspace_id: UUID, quality_gate_id: UUID) -> QualityGateState | None:
        _scope(self._session, workspace_id)
        record = self._session.scalar(
            select(QualityGateStateRecord).where(
                QualityGateStateRecord.workspace_id == workspace_id,
                QualityGateStateRecord.id == quality_gate_id,
            )
        )
        return _quality_state(record) if record else None

    def add(self, workspace_id: UUID, state: QualityGateState, minimum_score: int) -> None:
        _require_scope(workspace_id, state.workspace_id)
        _scope(self._session, workspace_id)
        values = _state_values(state, minimum_score)
        values["created_at"] = state.updated_at
        self._session.add(QualityGateStateRecord(**values))

    def save(
        self,
        workspace_id: UUID,
        state: QualityGateState,
        minimum_score: int,
        expected_version: int,
    ) -> None:
        _require_scope(workspace_id, state.workspace_id)
        if state.version != expected_version + 1:
            raise ValueError("saved quality-gate state must increment version exactly once")
        _scope(self._session, workspace_id)
        values = _state_values(state, minimum_score)
        values.pop("id")
        values.pop("workspace_id")
        result = self._session.execute(
            update(QualityGateStateRecord)
            .where(
                QualityGateStateRecord.workspace_id == workspace_id,
                QualityGateStateRecord.id == state.quality_gate_id,
                QualityGateStateRecord.version == expected_version,
            )
            .values(**values)
        )
        if cast(CursorResult[Any], result).rowcount != 1:
            raise ConcurrentQualityGateUpdateError("quality-gate state was changed or removed")


class SqlAlchemyQualityGateDecisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_command(self, workspace_id: UUID, command_id: UUID) -> QualityGateDecision | None:
        _scope(self._session, workspace_id)
        record = self._session.scalar(
            select(QualityGateDecisionRecord).where(
                QualityGateDecisionRecord.workspace_id == workspace_id,
                QualityGateDecisionRecord.command_id == command_id,
            )
        )
        if record is None:
            return None
        state_record = self._session.scalar(
            select(QualityGateStateRecord).where(
                QualityGateStateRecord.workspace_id == workspace_id,
                QualityGateStateRecord.id == record.quality_gate_id,
            )
        )
        if state_record is None or state_record.last_decision_id != record.id:
            raise ConcurrentQualityGateUpdateError("recorded decision is not current")
        command = QualityGateCommand(
            record.command_id,
            record.quality_gate_id,
            record.workspace_id,
            record.run_id,
            record.step_id,
            record.correlation_id,
            record.causation_id,
            ArtifactReference(record.artifact_id, record.artifact_version, record.artifact_sha256),
            Actor(ActorType(record.actor_type), record.actor_id),
            record.state_version_before,
            record.decided_at,
        )
        evidence = QualityGateDecisionEvidence(
            record.id,
            record.command_id,
            record.quality_gate_id,
            record.workspace_id,
            record.run_id,
            record.step_id,
            record.correlation_id,
            record.causation_id,
            CapabilityReference(
                record.capability_definition_id,
                record.capability_key,
                SemanticVersion.parse(record.capability_version),
            ),
            record.policy_key,
            SemanticVersion.parse(record.policy_version),
            record.criteria_key,
            SemanticVersion.parse(record.criteria_version),
            record.score_key,
            record.score,
            record.minimum_score,
            record.prior_score,
            command.artifact,
            record.validation_id,
            record.assessment_id,
            record.revision_count_before,
            record.revision_count_after,
            record.decided_at,
        )
        return QualityGateDecision(
            command,
            QualityGateOutcome(record.outcome),
            tuple(QualityGateReason(item) for item in record.reasons_json),
            evidence,
            _quality_state(state_record),
        )

    def append(
        self, workspace_id: UUID, decision: QualityGateDecision, state_version_before: int | None
    ) -> None:
        _require_scope(workspace_id, decision.command.workspace_id)
        _scope(self._session, workspace_id)
        self._session.flush()
        command, evidence = decision.command, decision.evidence
        self._session.add(
            QualityGateDecisionRecord(
                id=evidence.decision_id,
                command_id=command.command_id,
                quality_gate_id=command.quality_gate_id,
                workspace_id=workspace_id,
                run_id=command.run_id,
                step_id=command.step_id,
                correlation_id=command.correlation_id,
                causation_id=command.causation_id,
                actor_type=command.actor.type.value,
                actor_id=command.actor.id,
                capability_definition_id=evidence.capability.capability_definition_id,
                capability_key=evidence.capability.capability_key,
                capability_version=str(evidence.capability.semantic_version),
                policy_key=evidence.policy_key,
                policy_version=str(evidence.policy_version),
                criteria_key=evidence.criteria_key,
                criteria_version=str(evidence.criteria_version),
                score_key=evidence.score_key,
                score=evidence.score,
                minimum_score=evidence.minimum_score,
                prior_score=evidence.prior_score,
                artifact_id=evidence.artifact.artifact_id,
                artifact_version=evidence.artifact.version,
                artifact_sha256=evidence.artifact.sha256,
                validation_id=evidence.validation_id,
                assessment_id=evidence.assessment_id,
                outcome=decision.outcome.value,
                reasons_json=[reason.value for reason in decision.reasons],
                revision_count_before=evidence.revision_count_before,
                revision_count_after=evidence.revision_count_after,
                state_version_before=state_version_before,
                state_version_after=decision.next_state.version,
                decided_at=evidence.decided_at,
            )
        )
