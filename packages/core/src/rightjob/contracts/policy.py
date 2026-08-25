"""Published provider-neutral Policy decision contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from rightjob.contracts.capabilities import (
    CapabilityReference,
    EffectClassification,
    SemanticVersion,
)
from rightjob.contracts.departments import DepartmentReference, WorkCategory
from rightjob.contracts.events import Actor

_KEY = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class PolicyEvaluationError(ValueError):
    """Policy input is malformed, unknown, stale, or inconsistent."""


@dataclass(frozen=True, slots=True)
class MembershipFacts:
    membership_id: UUID
    user_id: UUID
    workspace_id: UUID
    active: bool
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    version: int = 1

    def __post_init__(self) -> None:
        _require_ids(self.membership_id, self.user_id, self.workspace_id)
        _require_unique_keys("roles", self.roles)
        _require_unique_keys("permissions", self.permissions)
        if self.version < 1:
            raise ValueError("membership version must be positive")


@dataclass(frozen=True, slots=True)
class PolicySubject:
    actor: Actor
    workspace_id: UUID
    membership: MembershipFacts | None

    def __post_init__(self) -> None:
        _require_ids(self.workspace_id)
        if self.membership is not None and self.membership.workspace_id != self.workspace_id:
            raise PolicyEvaluationError("subject and membership Workspaces do not match")


class PolicyOperation(StrEnum):
    EXECUTE_CAPABILITY = "execute_capability"


@dataclass(frozen=True, slots=True)
class PolicyAction:
    operation: PolicyOperation
    plan_id: UUID
    step_id: UUID
    department: DepartmentReference
    capability: CapabilityReference
    work_category: WorkCategory
    effect_classification: EffectClassification

    def __post_init__(self) -> None:
        _require_ids(self.plan_id, self.step_id)


@dataclass(frozen=True, slots=True)
class PolicyContext:
    workspace_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    planning_request_id: UUID
    plan_id: UUID

    def __post_init__(self) -> None:
        _require_ids(
            self.workspace_id,
            self.correlation_id,
            self.planning_request_id,
            self.plan_id,
        )
        if self.causation_id is not None:
            _require_ids(self.causation_id)


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyReasonCode(StrEnum):
    SYNTHETIC_NONCONSEQUENTIAL_ALLOWED = "synthetic_nonconsequential_allowed"
    SUBJECT_NOT_AUTHORIZED = "subject_not_authorized"
    APPROVAL_REQUIRED_FOR_EFFECT = "approval_required_for_effect"


@dataclass(frozen=True, slots=True)
class PolicySetReference:
    policy_set_id: UUID
    policy_set_key: str
    semantic_version: SemanticVersion

    def __post_init__(self) -> None:
        _require_ids(self.policy_set_id)
        _require_key("policy_set_key", self.policy_set_key)


@dataclass(frozen=True, slots=True)
class PolicyRuleReference:
    policy_set: PolicySetReference
    rule_key: str
    rule_version: SemanticVersion

    def __post_init__(self) -> None:
        _require_key("rule_key", self.rule_key)


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    """An in-memory decision result, never durable authorization evidence."""

    decision_id: UUID
    subject: PolicySubject
    action: PolicyAction
    context: PolicyContext
    decision: PolicyDecision
    reason_codes: tuple[PolicyReasonCode, ...]
    policy_set: PolicySetReference
    matched_rules: tuple[PolicyRuleReference, ...]
    evaluated_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _require_ids(self.decision_id)
        if not self.reason_codes or len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason_codes must be nonempty and unique")
        if not self.matched_rules or len(set(self.matched_rules)) != len(self.matched_rules):
            raise ValueError("matched_rules must be nonempty and unique")
        _require_aware("evaluated_at", self.evaluated_at)
        _require_aware("expires_at", self.expires_at)
        if self.expires_at <= self.evaluated_at:
            raise ValueError("expires_at must be after evaluated_at")


class PolicyEvaluator(Protocol):
    def evaluate(
        self,
        subject: PolicySubject,
        action: PolicyAction,
        context: PolicyContext,
    ) -> PolicyEvaluation: ...


def _require_ids(*values: UUID) -> None:
    if any(value.int == 0 for value in values):
        raise ValueError("Policy identifiers must not be nil")


def _require_key(name: str, value: str) -> None:
    if not 1 <= len(value) <= 100 or _KEY.fullmatch(value) is None:
        raise ValueError(f"{name} must be a bounded canonical identifier")


def _require_unique_keys(name: str, values: tuple[str, ...]) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must be unique")
    for value in values:
        _require_key(name, value)


def _require_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
