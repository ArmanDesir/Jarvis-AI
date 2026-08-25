"""Published durable authorization contracts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from rightjob.contracts.capabilities import CapabilityReference
from rightjob.contracts.departments import DepartmentReference
from rightjob.contracts.events import JsonValue
from rightjob.contracts.planning import ExecutionPlan, PlanStep
from rightjob.contracts.policy import PolicyDecision, PolicyEvaluation

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class AuthorizationError(ValueError):
    """Authorization is missing, stale, malformed, or insufficient."""


def canonical_json(value: dict[str, JsonValue]) -> bytes:
    """Canonical UTF-8 JSON used only for deterministic equality binding."""
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise AuthorizationError("action snapshot must be bounded JSON") from error


def action_digest(value: dict[str, JsonValue]) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def action_snapshot(
    plan: ExecutionPlan, step: PlanStep, evaluation: PolicyEvaluation
) -> dict[str, JsonValue]:
    if evaluation.context.plan_id != plan.plan_id or evaluation.action.step_id != step.step_id:
        raise AuthorizationError("Policy evaluation does not match plan step")
    return {
        "schema_version": 1,
        "workspace_id": str(plan.workspace_id),
        "planning_request_id": str(plan.planning_request_id),
        "plan_id": str(plan.plan_id),
        "step_id": str(step.step_id),
        "sequence": step.sequence,
        "operation": evaluation.action.operation.value,
        "department": {
            "id": str(step.department.department_definition_id),
            "key": step.department.department_key,
            "version": str(step.department.semantic_version),
        },
        "capability": {
            "id": str(step.capability.capability_definition_id),
            "key": step.capability.capability_key,
            "version": str(step.capability.semantic_version),
        },
        "work_category": step.work_category.value,
        "effect_classification": step.effect_classification.value,
        "input": step.input.as_dict(),
        "dependencies": [str(item) for item in step.dependency_step_ids],
        "expected_output": {
            "key": step.expected_output.contract_key,
            "version": str(step.expected_output.semantic_version),
            "maximum_payload_bytes": step.expected_output.maximum_payload_bytes,
        },
        "policy_set": {
            "id": str(evaluation.policy_set.policy_set_id),
            "key": evaluation.policy_set.policy_set_key,
            "version": str(evaluation.policy_set.semantic_version),
        },
    }


@dataclass(frozen=True, slots=True)
class AuthorizationEvidence:
    authorization_evidence_id: UUID
    policy_evaluation: PolicyEvaluation
    action_snapshot: dict[str, JsonValue]
    action_digest: str

    def __post_init__(self) -> None:
        if self.authorization_evidence_id.int == 0:
            raise AuthorizationError("authorization evidence ID must not be nil")
        if not _DIGEST.fullmatch(self.action_digest):
            raise AuthorizationError("action digest must be lowercase SHA-256")
        if action_digest(self.action_snapshot) != self.action_digest:
            raise AuthorizationError("action snapshot digest does not match")

    @property
    def workspace_id(self) -> UUID:
        return self.policy_evaluation.context.workspace_id

    @property
    def expires_at(self) -> datetime:
        return self.policy_evaluation.expires_at


@dataclass(frozen=True, slots=True)
class ExecutionAuthorizationStep:
    execution_authorization_step_id: UUID
    step_id: UUID
    sequence: int
    action_digest: str
    authorization_evidence_id: UUID
    approval_request_id: UUID | None = None
    approval_decision_id: UUID | None = None

    def __post_init__(self) -> None:
        if any(
            item.int == 0
            for item in (
                self.execution_authorization_step_id,
                self.step_id,
                self.authorization_evidence_id,
            )
        ):
            raise AuthorizationError("authorization step IDs must not be nil")
        if self.sequence < 0 or not _DIGEST.fullmatch(self.action_digest):
            raise AuthorizationError("invalid authorization step binding")
        if (self.approval_request_id is None) != (self.approval_decision_id is None):
            raise AuthorizationError("approval request and decision must be supplied together")


@dataclass(frozen=True, slots=True)
class ExecutionAuthorization:
    execution_authorization_id: UUID
    workspace_id: UUID
    planning_request_id: UUID
    plan_id: UUID
    workflow_definition_id: UUID
    workflow_type: str
    workflow_version: str
    plan_digest: str
    steps: tuple[ExecutionAuthorizationStep, ...]
    issued_at: datetime
    expires_at: datetime
    correlation_id: UUID
    causation_id: UUID | None
    authorization_version: int = 1

    def __post_init__(self) -> None:
        ids = (
            self.execution_authorization_id,
            self.workspace_id,
            self.planning_request_id,
            self.plan_id,
            self.workflow_definition_id,
            self.correlation_id,
        )
        if any(item.int == 0 for item in ids):
            raise AuthorizationError("execution authorization IDs must not be nil")
        if not self.workflow_type.strip() or not self.workflow_version.strip():
            raise AuthorizationError("workflow identity must be nonblank")
        if not _DIGEST.fullmatch(self.plan_digest):
            raise AuthorizationError("plan digest must be lowercase SHA-256")
        if not self.steps or tuple(item.sequence for item in self.steps) != tuple(
            range(len(self.steps))
        ):
            raise AuthorizationError("authorization steps must be complete and ordered")
        if len({item.step_id for item in self.steps}) != len(self.steps):
            raise AuthorizationError("authorization step IDs must be unique")
        if self.expires_at <= self.issued_at or self.authorization_version != 1:
            raise AuthorizationError("invalid authorization lifetime or version")


@dataclass(frozen=True, slots=True)
class ExecutionAuthorizationReference:
    execution_authorization_id: UUID
    workspace_id: UUID
    plan_id: UUID
    plan_digest: str

    def __post_init__(self) -> None:
        if any(
            item.int == 0
            for item in (self.execution_authorization_id, self.workspace_id, self.plan_id)
        ):
            raise AuthorizationError("authorization reference IDs must not be nil")
        if not _DIGEST.fullmatch(self.plan_digest):
            raise AuthorizationError("invalid plan digest")


class ExecutionAuthorizationConsumer(Protocol):
    def consume(
        self,
        reference: ExecutionAuthorizationReference,
        execution_id: UUID,
        workflow_definition_id: UUID,
        workflow_type: str,
        workflow_version: str,
        ordered_step_ids: tuple[UUID, ...],
        at: datetime,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class AuthorizedWorkflowStep:
    department: DepartmentReference
    capability: CapabilityReference


@dataclass(frozen=True, slots=True)
class AuthorizedWorkflow:
    workflow_definition_id: UUID
    workflow_type: str
    workflow_version: str
    enabled: bool
    steps: tuple[AuthorizedWorkflowStep, ...]


def require_evidence_current(evidence: AuthorizationEvidence, at: datetime) -> None:
    if at.tzinfo is None or at.utcoffset() is None:
        raise AuthorizationError("authorization time must be timezone-aware")
    if at >= evidence.expires_at:
        raise AuthorizationError("Policy evidence has expired")
    membership = evidence.policy_evaluation.subject.membership
    if membership is None or not membership.active:
        raise AuthorizationError("current active membership is required")
    if membership.version < 1:
        raise AuthorizationError("membership facts are stale")


def reject_deny(evidence: AuthorizationEvidence) -> None:
    if evidence.policy_evaluation.decision is PolicyDecision.DENY:
        raise AuthorizationError("Policy DENY cannot authorize work")
