"""Atomic durable-governance persistence with Audit/Outbox evidence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from rightjob.contracts.approval import ApprovalDecision, ApprovalRequest
from rightjob.contracts.authorization import AuthorizationEvidence, ExecutionAuthorization
from rightjob.contracts.events import (
    Actor,
    AuditEvidence,
    AuditOutcome,
    DataSensitivity,
    IntegrationEvent,
    JsonValue,
)
from rightjob.policy.repositories import IdempotencyConflictError, PolicyApprovalUnitOfWork

UnitOfWorkFactory = Callable[[], PolicyApprovalUnitOfWork]
IdFactory = Callable[[], UUID]


class GovernanceRecorder:
    """Persists one governance aggregate and its evidence in one commit."""

    def __init__(self, unit_of_work: UnitOfWorkFactory, id_factory: IdFactory) -> None:
        self._unit_of_work = unit_of_work
        self._id = id_factory

    def record_evidence(self, evidence: AuthorizationEvidence) -> AuthorizationEvidence:
        value = evidence.policy_evaluation
        try:
            with self._unit_of_work() as uow:
                existing = uow.authorization_evidence.get_by_policy_evaluation(
                    evidence.workspace_id, value.decision_id
                )
                if existing is not None:
                    return self._reuse_evidence(existing, evidence)
                uow.authorization_evidence.add(evidence.workspace_id, evidence)
                self._record(
                    uow,
                    evidence.workspace_id,
                    value.subject.actor,
                    "policy.authorization_evidence.recorded",
                    "authorization_evidence",
                    evidence.authorization_evidence_id,
                    value.context.correlation_id,
                    value.context.causation_id,
                    value.evaluated_at,
                    {"decision": value.decision.value, "action_digest": evidence.action_digest},
                    "policy.authorization_evidence.recorded.v1",
                )
                uow.commit()
                return evidence
        except IntegrityError as error:
            self._require_constraint(error, {"uq_authorization_evidence_workspace_evaluation"})
            with self._unit_of_work() as uow:
                existing = uow.authorization_evidence.get_by_policy_evaluation(
                    evidence.workspace_id, value.decision_id
                )
                if existing is None:
                    raise
                return self._reuse_evidence(existing, evidence)

    def create_approval_request(
        self, request: ApprovalRequest, idempotency_key: str
    ) -> ApprovalRequest:
        try:
            with self._unit_of_work() as uow:
                existing = self._existing_request(uow, request, idempotency_key)
                if existing is not None:
                    return self._reuse_request(existing, request)
                uow.approval_requests.add(request.workspace_id, request, idempotency_key)
                self._record(
                    uow,
                    request.workspace_id,
                    request.requester,
                    "approval.requested",
                    "approval_request",
                    request.approval_request_id,
                    request.correlation_id,
                    request.causation_id,
                    request.requested_at,
                    {"action_digest": request.action_digest, "status": request.status.value},
                    "approval.requested.v1",
                )
                uow.commit()
                return request
        except IntegrityError as error:
            self._require_constraint(
                error,
                {
                    "uq_approval_requests_workspace_evidence",
                    "uq_approval_requests_workspace_idempotency",
                },
            )
            with self._unit_of_work() as uow:
                existing = self._existing_request(uow, request, idempotency_key)
                if existing is None:
                    raise
                return self._reuse_request(existing, request)

    def record_decision(
        self, request: ApprovalRequest, decision: ApprovalDecision, idempotency_key: str
    ) -> ApprovalDecision:
        try:
            with self._unit_of_work() as uow:
                existing = self._existing_decision(uow, decision, idempotency_key)
                if existing is not None:
                    return self._reuse_decision(existing, decision)
                uow.approval_decisions.add(request.workspace_id, decision, idempotency_key)
                uow.approval_requests.save(request.workspace_id, request, request.version - 1)
                self._record(
                    uow,
                    request.workspace_id,
                    decision.approver,
                    f"approval.{decision.outcome.value}",
                    "approval_request",
                    request.approval_request_id,
                    decision.correlation_id,
                    decision.causation_id,
                    decision.decided_at,
                    {"action_digest": decision.action_digest, "outcome": decision.outcome.value},
                    f"approval.{decision.outcome.value}.v1",
                )
                uow.commit()
                return decision
        except IntegrityError as error:
            self._require_constraint(
                error,
                {
                    "uq_approval_decisions_workspace_request",
                    "uq_approval_decisions_workspace_idempotency",
                },
            )
            with self._unit_of_work() as uow:
                existing = self._existing_decision(uow, decision, idempotency_key)
                if existing is None:
                    raise
                return self._reuse_decision(existing, decision)

    def issue_authorization(
        self, authorization: ExecutionAuthorization, actor: Actor, idempotency_key: str
    ) -> ExecutionAuthorization:
        try:
            with self._unit_of_work() as uow:
                existing = uow.execution_authorizations.get_by_idempotency_key(
                    authorization.workspace_id, idempotency_key
                )
                if existing is not None:
                    return self._reuse_authorization(existing, authorization)
                uow.execution_authorizations.add(
                    authorization.workspace_id, authorization, idempotency_key
                )
                self._record(
                    uow,
                    authorization.workspace_id,
                    actor,
                    "authorization.issued",
                    "execution_authorization",
                    authorization.execution_authorization_id,
                    authorization.correlation_id,
                    authorization.causation_id,
                    authorization.issued_at,
                    {
                        "plan_digest": authorization.plan_digest,
                        "step_count": len(authorization.steps),
                    },
                    "authorization.issued.v1",
                )
                uow.commit()
                return authorization
        except IntegrityError as error:
            self._require_constraint(error, {"uq_execution_authorizations_workspace_idempotency"})
            with self._unit_of_work() as uow:
                existing = uow.execution_authorizations.get_by_idempotency_key(
                    authorization.workspace_id, idempotency_key
                )
                if existing is None:
                    raise
                return self._reuse_authorization(existing, authorization)

    @staticmethod
    def _reuse_evidence(
        existing: AuthorizationEvidence, proposed: AuthorizationEvidence
    ) -> AuthorizationEvidence:
        if (
            replace(existing, authorization_evidence_id=proposed.authorization_evidence_id)
            != proposed
        ):
            raise IdempotencyConflictError("AuthorizationEvidence idempotency conflict")
        return existing

    @staticmethod
    def _reuse_request(existing: ApprovalRequest, proposed: ApprovalRequest) -> ApprovalRequest:
        immutable_existing = replace(
            existing,
            approval_request_id=proposed.approval_request_id,
            status=proposed.status,
            version=proposed.version,
            resolved_at=proposed.resolved_at,
        )
        if immutable_existing != proposed:
            raise IdempotencyConflictError("ApprovalRequest idempotency conflict")
        return existing

    @staticmethod
    def _reuse_decision(existing: ApprovalDecision, proposed: ApprovalDecision) -> ApprovalDecision:
        if replace(existing, approval_decision_id=proposed.approval_decision_id) != proposed:
            raise IdempotencyConflictError("ApprovalDecision idempotency conflict")
        return existing

    @staticmethod
    def _reuse_authorization(
        existing: ExecutionAuthorization, proposed: ExecutionAuthorization
    ) -> ExecutionAuthorization:
        existing_steps = tuple(
            replace(
                step, execution_authorization_step_id=proposed_step.execution_authorization_step_id
            )
            for step, proposed_step in zip(existing.steps, proposed.steps, strict=False)
        )
        comparable = replace(
            existing,
            execution_authorization_id=proposed.execution_authorization_id,
            steps=existing_steps,
        )
        if len(existing.steps) != len(proposed.steps) or comparable != proposed:
            raise IdempotencyConflictError("ExecutionAuthorization idempotency conflict")
        return existing

    @staticmethod
    def _existing_request(
        uow: PolicyApprovalUnitOfWork,
        request: ApprovalRequest,
        idempotency_key: str,
    ) -> ApprovalRequest | None:
        by_evidence = uow.approval_requests.get_by_evidence(
            request.workspace_id, request.authorization_evidence_id
        )
        by_key = uow.approval_requests.get_by_idempotency_key(request.workspace_id, idempotency_key)
        if (by_evidence is None) != (by_key is None):
            raise IdempotencyConflictError("ApprovalRequest identities resolve differently")
        if (
            by_evidence is not None
            and by_key is not None
            and by_evidence.approval_request_id != by_key.approval_request_id
        ):
            raise IdempotencyConflictError("ApprovalRequest identities resolve differently")
        return by_evidence or by_key

    @staticmethod
    def _existing_decision(
        uow: PolicyApprovalUnitOfWork,
        decision: ApprovalDecision,
        idempotency_key: str,
    ) -> ApprovalDecision | None:
        by_request = uow.approval_decisions.get_by_request(
            decision.workspace_id, decision.approval_request_id
        )
        by_key = uow.approval_decisions.get_by_idempotency_key(
            decision.workspace_id, idempotency_key
        )
        if (by_request is None) != (by_key is None):
            raise IdempotencyConflictError("ApprovalDecision identities resolve differently")
        if (
            by_request is not None
            and by_key is not None
            and by_request.approval_decision_id != by_key.approval_decision_id
        ):
            raise IdempotencyConflictError("ApprovalDecision identities resolve differently")
        return by_request or by_key

    @staticmethod
    def _require_constraint(error: IntegrityError, allowed: set[str]) -> None:
        diagnostic = getattr(error.orig, "diag", None)
        name = getattr(diagnostic, "constraint_name", None)
        if name not in allowed:
            raise error

    def _record(
        self,
        uow: PolicyApprovalUnitOfWork,
        workspace_id: UUID,
        actor: Actor,
        action: str,
        resource_type: str,
        resource_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None,
        occurred_at: datetime,
        payload: dict[str, JsonValue],
        event_type: str,
    ) -> None:
        audit_id, event_id = self._id(), self._id()
        uow.audit_evidence.append(
            workspace_id,
            AuditEvidence(
                audit_id,
                workspace_id,
                actor,
                action,
                resource_type,
                str(resource_id),
                AuditOutcome.SUCCEEDED,
                correlation_id,
                occurred_at,
                DataSensitivity.INTERNAL,
                causation_id,
                after=payload,
            ),
        )
        uow.outbox.add(
            workspace_id,
            IntegrationEvent(
                event_id,
                event_type,
                1,
                1,
                occurred_at,
                workspace_id,
                actor,
                correlation_id,
                "rightjob.policy",
                DataSensitivity.INTERNAL,
                payload,
                f"{event_type}:{resource_id}",
                causation_id,
            ),
        )
