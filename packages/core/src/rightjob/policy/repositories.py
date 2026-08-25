"""Policy/Approval persistence and transaction ports."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from rightjob.contracts.approval import ApprovalDecision, ApprovalRequest
from rightjob.contracts.authorization import AuthorizationEvidence, ExecutionAuthorization
from rightjob.contracts.events import AuditEvidence, IntegrationEvent


class AuditEvidenceAppender(Protocol):
    def append(self, workspace_id: UUID, evidence: AuditEvidence) -> None: ...


class OutboxAppender(Protocol):
    def add(self, workspace_id: UUID, event: IntegrationEvent) -> None: ...


class ConcurrentApprovalUpdateError(RuntimeError):
    pass


class IdempotencyConflictError(RuntimeError):
    """An idempotency identity was reused for different semantic content."""


class AuthorizationEvidenceRepository(Protocol):
    def add(self, workspace_id: UUID, evidence: AuthorizationEvidence) -> None: ...
    def get_by_policy_evaluation(
        self, workspace_id: UUID, policy_evaluation_id: UUID
    ) -> AuthorizationEvidence | None: ...


class ApprovalRequestRepository(Protocol):
    def add(self, workspace_id: UUID, request: ApprovalRequest, idempotency_key: str) -> None: ...
    def get(self, workspace_id: UUID, request_id: UUID) -> ApprovalRequest | None: ...
    def get_by_evidence(self, workspace_id: UUID, evidence_id: UUID) -> ApprovalRequest | None: ...
    def get_by_idempotency_key(
        self, workspace_id: UUID, idempotency_key: str
    ) -> ApprovalRequest | None: ...
    def save(self, workspace_id: UUID, request: ApprovalRequest, expected_version: int) -> None: ...


class ApprovalDecisionRepository(Protocol):
    def add(self, workspace_id: UUID, decision: ApprovalDecision, idempotency_key: str) -> None: ...
    def get_by_request(self, workspace_id: UUID, request_id: UUID) -> ApprovalDecision | None: ...
    def get_by_idempotency_key(
        self, workspace_id: UUID, idempotency_key: str
    ) -> ApprovalDecision | None: ...


class ExecutionAuthorizationRepository(Protocol):
    def add(
        self, workspace_id: UUID, authorization: ExecutionAuthorization, idempotency_key: str
    ) -> None: ...
    def get_by_idempotency_key(
        self, workspace_id: UUID, idempotency_key: str
    ) -> ExecutionAuthorization | None: ...


class PolicyApprovalUnitOfWork(Protocol):
    authorization_evidence: AuthorizationEvidenceRepository
    approval_requests: ApprovalRequestRepository
    approval_decisions: ApprovalDecisionRepository
    execution_authorizations: ExecutionAuthorizationRepository
    audit_evidence: AuditEvidenceAppender
    outbox: OutboxAppender

    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...
