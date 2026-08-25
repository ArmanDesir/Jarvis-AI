"""Workspace-scoped SQLAlchemy Policy/Approval repositories."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from rightjob.contracts.approval import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRequest,
    ApprovalStatus,
)
from rightjob.contracts.authorization import (
    AuthorizationError,
    AuthorizationEvidence,
    ExecutionAuthorization,
    ExecutionAuthorizationReference,
    ExecutionAuthorizationStep,
)
from rightjob.contracts.capabilities import (
    CapabilityReference,
    EffectClassification,
    SemanticVersion,
)
from rightjob.contracts.departments import DepartmentReference, WorkCategory
from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.policy import (
    MembershipFacts,
    PolicyAction,
    PolicyContext,
    PolicyDecision,
    PolicyEvaluation,
    PolicyOperation,
    PolicyReasonCode,
    PolicyRuleReference,
    PolicySetReference,
    PolicySubject,
)
from rightjob.policy.infrastructure.models import (
    ApprovalDecisionRecord,
    ApprovalRequestRecord,
    AuthorizationEvidenceRecord,
    ExecutionAuthorizationRecord,
    ExecutionAuthorizationStepRecord,
)
from rightjob.policy.repositories import ConcurrentApprovalUpdateError
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session


def _scope(session: Session, workspace_id: UUID) -> None:
    session.execute(select(func.set_config("app.current_workspace_id", str(workspace_id), True)))


class SqlAlchemyAuthorizationEvidenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, workspace_id: UUID, evidence: AuthorizationEvidence) -> None:
        if workspace_id != evidence.workspace_id:
            raise ValueError("evidence Workspace mismatch")
        _scope(self._session, workspace_id)
        value = evidence.policy_evaluation
        membership = value.subject.membership
        self._session.add(
            AuthorizationEvidenceRecord(
                id=evidence.authorization_evidence_id,
                workspace_id=workspace_id,
                policy_evaluation_id=value.decision_id,
                planning_request_id=value.context.planning_request_id,
                plan_id=value.context.plan_id,
                step_id=value.action.step_id,
                subject_actor_type=value.subject.actor.type.value,
                subject_actor_id=value.subject.actor.id,
                subject_user_id=membership.user_id if membership else None,
                subject_membership_id=membership.membership_id if membership else None,
                subject_membership_version=membership.version if membership else None,
                subject_membership_active=membership.active if membership else None,
                subject_roles_json=list(membership.roles) if membership else [],
                subject_permissions_json=list(membership.permissions) if membership else [],
                operation=value.action.operation.value,
                department_definition_id=value.action.department.department_definition_id,
                department_key=value.action.department.department_key,
                department_version=str(value.action.department.semantic_version),
                capability_definition_id=value.action.capability.capability_definition_id,
                capability_key=value.action.capability.capability_key,
                capability_version=str(value.action.capability.semantic_version),
                work_category=value.action.work_category.value,
                effect_classification=value.action.effect_classification.value,
                action_snapshot_json=evidence.action_snapshot,
                action_digest=evidence.action_digest,
                digest_algorithm="sha256",
                snapshot_schema_version=1,
                policy_decision=value.decision.value,
                reason_codes_json=[item.value for item in value.reason_codes],
                policy_set_id=value.policy_set.policy_set_id,
                policy_set_key=value.policy_set.policy_set_key,
                policy_set_version=str(value.policy_set.semantic_version),
                matched_rules_json=[
                    {"key": item.rule_key, "version": str(item.rule_version)}
                    for item in value.matched_rules
                ],
                evaluated_at=value.evaluated_at,
                expires_at=value.expires_at,
                correlation_id=value.context.correlation_id,
                causation_id=value.context.causation_id,
            )
        )

    def get_by_policy_evaluation(
        self, workspace_id: UUID, policy_evaluation_id: UUID
    ) -> AuthorizationEvidence | None:
        _scope(self._session, workspace_id)
        record = self._session.scalar(
            select(AuthorizationEvidenceRecord).where(
                AuthorizationEvidenceRecord.workspace_id == workspace_id,
                AuthorizationEvidenceRecord.policy_evaluation_id == policy_evaluation_id,
            )
        )
        return _evidence(record) if record else None


class SqlAlchemyApprovalRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, workspace_id: UUID, request: ApprovalRequest, idempotency_key: str) -> None:
        if workspace_id != request.workspace_id:
            raise ValueError("request Workspace mismatch")
        _scope(self._session, workspace_id)
        self._session.add(
            ApprovalRequestRecord(
                id=request.approval_request_id,
                workspace_id=workspace_id,
                authorization_evidence_id=request.authorization_evidence_id,
                planning_request_id=request.planning_request_id,
                plan_id=request.plan_id,
                step_id=request.step_id,
                action_digest=request.action_digest,
                requester_actor_type=request.requester.type.value,
                requester_actor_id=request.requester.id,
                status=request.status.value,
                requested_at=request.requested_at,
                expires_at=request.expires_at,
                resolved_at=request.resolved_at,
                correlation_id=request.correlation_id,
                causation_id=request.causation_id,
                idempotency_key=idempotency_key,
                version=request.version,
            )
        )

    def get(self, workspace_id: UUID, request_id: UUID) -> ApprovalRequest | None:
        _scope(self._session, workspace_id)
        record = self._session.scalar(
            select(ApprovalRequestRecord).where(
                ApprovalRequestRecord.workspace_id == workspace_id,
                ApprovalRequestRecord.id == request_id,
            )
        )
        if record is None:
            return None
        return _approval_request(record)

    def get_by_evidence(self, workspace_id: UUID, evidence_id: UUID) -> ApprovalRequest | None:
        _scope(self._session, workspace_id)
        record = self._session.scalar(
            select(ApprovalRequestRecord).where(
                ApprovalRequestRecord.workspace_id == workspace_id,
                ApprovalRequestRecord.authorization_evidence_id == evidence_id,
            )
        )
        return _approval_request(record) if record else None

    def get_by_idempotency_key(
        self, workspace_id: UUID, idempotency_key: str
    ) -> ApprovalRequest | None:
        _scope(self._session, workspace_id)
        record = self._session.scalar(
            select(ApprovalRequestRecord).where(
                ApprovalRequestRecord.workspace_id == workspace_id,
                ApprovalRequestRecord.idempotency_key == idempotency_key,
            )
        )
        return _approval_request(record) if record else None

    def save(self, workspace_id: UUID, request: ApprovalRequest, expected_version: int) -> None:
        if request.version != expected_version + 1:
            raise ValueError("approval version must increment once")
        _scope(self._session, workspace_id)
        result = self._session.execute(
            update(ApprovalRequestRecord)
            .where(
                ApprovalRequestRecord.workspace_id == workspace_id,
                ApprovalRequestRecord.id == request.approval_request_id,
                ApprovalRequestRecord.version == expected_version,
                ApprovalRequestRecord.status == ApprovalStatus.PENDING.value,
            )
            .values(
                status=request.status.value,
                resolved_at=request.resolved_at,
                version=request.version,
            )
        )
        if cast(CursorResult[Any], result).rowcount != 1:
            raise ConcurrentApprovalUpdateError("approval request changed concurrently")


def _approval_request(record: ApprovalRequestRecord) -> ApprovalRequest:
    return ApprovalRequest(
        record.id,
        record.authorization_evidence_id,
        record.workspace_id,
        record.planning_request_id,
        record.plan_id,
        record.step_id,
        record.action_digest,
        Actor(ActorType(record.requester_actor_type), record.requester_actor_id),
        ApprovalStatus(record.status),
        record.requested_at,
        record.expires_at,
        record.correlation_id,
        record.causation_id,
        record.version,
        record.resolved_at,
    )


class SqlAlchemyApprovalDecisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, workspace_id: UUID, decision: ApprovalDecision, idempotency_key: str) -> None:
        if workspace_id != decision.workspace_id:
            raise ValueError("decision Workspace mismatch")
        _scope(self._session, workspace_id)
        self._session.add(
            ApprovalDecisionRecord(
                id=decision.approval_decision_id,
                workspace_id=workspace_id,
                approval_request_id=decision.approval_request_id,
                action_digest=decision.action_digest,
                outcome=decision.outcome.value,
                approver_actor_type=decision.approver.type.value,
                approver_actor_id=decision.approver.id,
                approver_user_id=decision.membership.user_id,
                approver_membership_id=decision.membership.membership_id,
                approver_membership_version=decision.membership.version,
                approver_roles_json=list(decision.membership.roles),
                approver_permissions_json=list(decision.membership.permissions),
                authority_rule_key=decision.authority_rule_key,
                authority_rule_version=decision.authority_rule_version,
                decided_at=decision.decided_at,
                correlation_id=decision.correlation_id,
                causation_id=decision.causation_id,
                idempotency_key=idempotency_key,
            )
        )

    def get_by_request(self, workspace_id: UUID, request_id: UUID) -> ApprovalDecision | None:
        _scope(self._session, workspace_id)
        record = self._session.scalar(
            select(ApprovalDecisionRecord).where(
                ApprovalDecisionRecord.workspace_id == workspace_id,
                ApprovalDecisionRecord.approval_request_id == request_id,
            )
        )
        return _approval_decision(record) if record else None

    def get_by_idempotency_key(
        self, workspace_id: UUID, idempotency_key: str
    ) -> ApprovalDecision | None:
        _scope(self._session, workspace_id)
        record = self._session.scalar(
            select(ApprovalDecisionRecord).where(
                ApprovalDecisionRecord.workspace_id == workspace_id,
                ApprovalDecisionRecord.idempotency_key == idempotency_key,
            )
        )
        return _approval_decision(record) if record else None


class SqlAlchemyExecutionAuthorizationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self, workspace_id: UUID, authorization: ExecutionAuthorization, idempotency_key: str
    ) -> None:
        if workspace_id != authorization.workspace_id:
            raise ValueError("authorization Workspace mismatch")
        _scope(self._session, workspace_id)
        self._session.add(
            ExecutionAuthorizationRecord(
                id=authorization.execution_authorization_id,
                workspace_id=workspace_id,
                planning_request_id=authorization.planning_request_id,
                plan_id=authorization.plan_id,
                workflow_definition_id=authorization.workflow_definition_id,
                workflow_type=authorization.workflow_type,
                workflow_version=authorization.workflow_version,
                plan_digest=authorization.plan_digest,
                digest_algorithm="sha256",
                authorization_version=authorization.authorization_version,
                issued_at=authorization.issued_at,
                expires_at=authorization.expires_at,
                correlation_id=authorization.correlation_id,
                causation_id=authorization.causation_id,
                idempotency_key=idempotency_key,
            )
        )
        self._session.add_all(
            ExecutionAuthorizationStepRecord(
                id=step.execution_authorization_step_id,
                workspace_id=workspace_id,
                execution_authorization_id=authorization.execution_authorization_id,
                step_id=step.step_id,
                sequence=step.sequence,
                action_digest=step.action_digest,
                authorization_evidence_id=step.authorization_evidence_id,
                approval_request_id=step.approval_request_id,
                approval_decision_id=step.approval_decision_id,
            )
            for step in authorization.steps
        )

    def get_by_idempotency_key(
        self, workspace_id: UUID, idempotency_key: str
    ) -> ExecutionAuthorization | None:
        _scope(self._session, workspace_id)
        record = self._session.scalar(
            select(ExecutionAuthorizationRecord).where(
                ExecutionAuthorizationRecord.workspace_id == workspace_id,
                ExecutionAuthorizationRecord.idempotency_key == idempotency_key,
            )
        )
        if record is None:
            return None
        steps = tuple(
            self._session.scalars(
                select(ExecutionAuthorizationStepRecord)
                .where(
                    ExecutionAuthorizationStepRecord.workspace_id == workspace_id,
                    ExecutionAuthorizationStepRecord.execution_authorization_id == record.id,
                )
                .order_by(ExecutionAuthorizationStepRecord.sequence)
            )
        )
        return ExecutionAuthorization(
            record.id,
            record.workspace_id,
            record.planning_request_id,
            record.plan_id,
            record.workflow_definition_id,
            record.workflow_type,
            record.workflow_version,
            record.plan_digest,
            tuple(
                ExecutionAuthorizationStep(
                    step.id,
                    step.step_id,
                    step.sequence,
                    step.action_digest,
                    step.authorization_evidence_id,
                    step.approval_request_id,
                    step.approval_decision_id,
                )
                for step in steps
            ),
            record.issued_at,
            record.expires_at,
            record.correlation_id,
            record.causation_id,
            record.authorization_version,
        )


def _evidence(record: AuthorizationEvidenceRecord) -> AuthorizationEvidence:
    policy_set = PolicySetReference(
        record.policy_set_id,
        record.policy_set_key,
        SemanticVersion.parse(record.policy_set_version),
    )
    membership = None
    if record.subject_membership_id is not None:
        assert record.subject_user_id is not None
        assert record.subject_membership_version is not None
        assert record.subject_membership_active is not None
        membership = MembershipFacts(
            record.subject_membership_id,
            record.subject_user_id,
            record.workspace_id,
            record.subject_membership_active,
            tuple(record.subject_roles_json),
            tuple(record.subject_permissions_json),
            record.subject_membership_version,
        )
    evaluation = PolicyEvaluation(
        record.policy_evaluation_id,
        PolicySubject(
            Actor(ActorType(record.subject_actor_type), record.subject_actor_id),
            record.workspace_id,
            membership,
        ),
        PolicyAction(
            PolicyOperation(record.operation),
            record.plan_id,
            record.step_id,
            DepartmentReference(
                record.department_definition_id,
                record.department_key,
                SemanticVersion.parse(record.department_version),
            ),
            CapabilityReference(
                record.capability_definition_id,
                record.capability_key,
                SemanticVersion.parse(record.capability_version),
            ),
            WorkCategory(record.work_category),
            EffectClassification(record.effect_classification),
        ),
        PolicyContext(
            record.workspace_id,
            record.correlation_id,
            record.causation_id,
            record.planning_request_id,
            record.plan_id,
        ),
        PolicyDecision(record.policy_decision),
        tuple(PolicyReasonCode(item) for item in record.reason_codes_json),
        policy_set,
        tuple(
            PolicyRuleReference(
                policy_set,
                item["key"],
                SemanticVersion.parse(item["version"]),
            )
            for item in record.matched_rules_json
        ),
        record.evaluated_at,
        record.expires_at,
    )
    return AuthorizationEvidence(
        record.id,
        evaluation,
        record.action_snapshot_json,
        record.action_digest,
    )


def _approval_decision(record: ApprovalDecisionRecord) -> ApprovalDecision:
    membership = MembershipFacts(
        record.approver_membership_id,
        record.approver_user_id,
        record.workspace_id,
        True,
        tuple(record.approver_roles_json),
        tuple(record.approver_permissions_json),
        record.approver_membership_version,
    )
    return ApprovalDecision(
        record.id,
        record.approval_request_id,
        record.workspace_id,
        record.action_digest,
        ApprovalOutcome(record.outcome),
        Actor(ActorType(record.approver_actor_type), record.approver_actor_id),
        membership,
        record.decided_at,
        record.correlation_id,
        record.causation_id,
        record.authority_rule_key,
        record.authority_rule_version,
    )


class SqlAlchemyExecutionAuthorizationConsumer:
    def __init__(self, session: Session) -> None:
        self._session = session

    def consume(
        self,
        reference: ExecutionAuthorizationReference,
        execution_id: UUID,
        workflow_definition_id: UUID,
        workflow_type: str,
        workflow_version: str,
        ordered_step_ids: tuple[UUID, ...],
        at: Any,
    ) -> None:
        _scope(self._session, reference.workspace_id)
        record = self._session.scalar(
            select(ExecutionAuthorizationRecord).where(
                ExecutionAuthorizationRecord.workspace_id == reference.workspace_id,
                ExecutionAuthorizationRecord.id == reference.execution_authorization_id,
                ExecutionAuthorizationRecord.plan_id == reference.plan_id,
                ExecutionAuthorizationRecord.plan_digest == reference.plan_digest,
                ExecutionAuthorizationRecord.workflow_definition_id == workflow_definition_id,
                ExecutionAuthorizationRecord.workflow_type == workflow_type,
                ExecutionAuthorizationRecord.workflow_version == workflow_version,
            )
        )
        if record is None or at >= record.expires_at:
            raise AuthorizationError("execution authorization is missing, mismatched, or expired")
        authorized_steps = tuple(
            self._session.scalars(
                select(ExecutionAuthorizationStepRecord.step_id)
                .where(
                    ExecutionAuthorizationStepRecord.workspace_id == reference.workspace_id,
                    ExecutionAuthorizationStepRecord.execution_authorization_id == record.id,
                )
                .order_by(ExecutionAuthorizationStepRecord.sequence)
            )
        )
        if authorized_steps != ordered_step_ids:
            raise AuthorizationError("execution steps do not match authorization")
