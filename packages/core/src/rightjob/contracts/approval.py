"""Published durable human approval contracts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from rightjob.contracts.authorization import AuthorizationError, AuthorizationEvidence, reject_deny
from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.policy import MembershipFacts, PolicyDecision


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class ApprovalOutcome(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    approval_request_id: UUID
    authorization_evidence_id: UUID
    workspace_id: UUID
    planning_request_id: UUID
    plan_id: UUID
    step_id: UUID
    action_digest: str
    requester: Actor
    status: ApprovalStatus
    requested_at: datetime
    expires_at: datetime
    correlation_id: UUID
    causation_id: UUID | None
    version: int = 1
    resolved_at: datetime | None = None

    @classmethod
    def create(
        cls, request_id: UUID, evidence: AuthorizationEvidence, requested_at: datetime
    ) -> ApprovalRequest:
        reject_deny(evidence)
        evaluation = evidence.policy_evaluation
        if evaluation.decision is not PolicyDecision.REQUIRE_APPROVAL:
            raise AuthorizationError("only REQUIRE_APPROVAL evidence creates an approval request")
        if requested_at >= evidence.expires_at:
            raise AuthorizationError("expired evidence cannot create an approval request")
        return cls(
            request_id,
            evidence.authorization_evidence_id,
            evidence.workspace_id,
            evaluation.context.planning_request_id,
            evaluation.context.plan_id,
            evaluation.action.step_id,
            evidence.action_digest,
            evaluation.subject.actor,
            ApprovalStatus.PENDING,
            requested_at,
            evidence.expires_at,
            evaluation.context.correlation_id,
            evaluation.context.causation_id,
        )

    def transition(self, status: ApprovalStatus, at: datetime) -> ApprovalRequest:
        if self.status is not ApprovalStatus.PENDING or status is ApprovalStatus.PENDING:
            raise AuthorizationError("invalid approval request transition")
        if at >= self.expires_at and status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
            raise AuthorizationError("expired approval request cannot be decided")
        return replace(self, status=status, resolved_at=at, version=self.version + 1)


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    approval_decision_id: UUID
    approval_request_id: UUID
    workspace_id: UUID
    action_digest: str
    outcome: ApprovalOutcome
    approver: Actor
    membership: MembershipFacts
    decided_at: datetime
    correlation_id: UUID
    causation_id: UUID | None
    authority_rule_key: str = "synthetic.owner_admin"
    authority_rule_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if self.approver.type is not ActorType.USER:
            raise AuthorizationError("approver must be a human USER")
        if self.membership.workspace_id != self.workspace_id:
            raise AuthorizationError("approver must belong to request Workspace")
        if self.membership.user_id.hex != self.approver.id.replace("-", ""):
            raise AuthorizationError("approver identity does not match membership")
        if not self.membership.active or not set(self.membership.roles) & {"owner", "admin"}:
            raise AuthorizationError("active OWNER or ADMIN membership is required")
        if self.correlation_id.int == 0:
            raise AuthorizationError("correlation ID must not be nil")


def decide_request(
    request: ApprovalRequest,
    decision: ApprovalDecision,
    existing: ApprovalDecision | None = None,
) -> ApprovalRequest:
    if existing is not None:
        if existing == decision:
            status = (
                ApprovalStatus.APPROVED
                if existing.outcome is ApprovalOutcome.APPROVED
                else ApprovalStatus.REJECTED
            )
            return request.transition(status, existing.decided_at)
        raise AuthorizationError("conflicting duplicate approval decision")
    if (
        decision.approval_request_id != request.approval_request_id
        or decision.workspace_id != request.workspace_id
    ):
        raise AuthorizationError("approval decision does not match request")
    if decision.action_digest != request.action_digest:
        raise AuthorizationError("approval decision action digest does not match")
    status = (
        ApprovalStatus.APPROVED
        if decision.outcome is ApprovalOutcome.APPROVED
        else ApprovalStatus.REJECTED
    )
    return request.transition(status, decision.decided_at)
