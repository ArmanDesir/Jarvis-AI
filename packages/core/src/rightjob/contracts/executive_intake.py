"""Published contracts for bounded natural-language Executive intake."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.executive import (
    ExecutivePlanningRequest,
    ExecutivePlanningResult,
    ExecutivePlanPresentation,
)
from rightjob.contracts.planning import StructuredInput, SyntheticPlanningGoal

MAX_EXECUTIVE_MESSAGE_BYTES = 16_384
MAX_CLARIFICATION_CHARACTERS = 500
MAX_MISSING_FIELDS = 8
_FIELD = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class ExecutiveIntentOutcome(StrEnum):
    PLANNING_READY = "planning_ready"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED = "unsupported"


class ExecutiveIntentReason(StrEnum):
    READY = "ready"
    MISSING_INFORMATION = "missing_information"
    UNSUPPORTED_REQUEST = "unsupported_request"


class ExecutiveIntakeOutcome(StrEnum):
    PLANNED = "planned"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class ExecutiveIntakeFailure(StrEnum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_CONFIGURATION = "provider_configuration"
    INVALID_PROVIDER_OUTPUT = "invalid_provider_output"
    INTERNAL_FAILURE = "internal_failure"


@dataclass(frozen=True, slots=True)
class ExecutiveIntakeRequest:
    workspace_id: UUID
    actor: Actor
    correlation_id: UUID
    causation_id: UUID | None
    message: str

    def __post_init__(self) -> None:
        _require_ids(self.workspace_id, self.correlation_id)
        if self.causation_id is not None:
            _require_ids(self.causation_id)
        if self.actor.type not in {ActorType.USER, ActorType.SYSTEM}:
            raise ValueError("Executive intake actor must be user or system")
        normalized = " ".join(self.message.split())
        if not normalized:
            raise ValueError("Executive intake message must not be empty")
        if len(normalized.encode()) > MAX_EXECUTIVE_MESSAGE_BYTES:
            raise ValueError("Executive intake message exceeds the encoded byte bound")
        object.__setattr__(self, "message", normalized)


@dataclass(frozen=True, slots=True)
class ExecutiveIntent:
    schema_version: int
    outcome: ExecutiveIntentOutcome
    reason: ExecutiveIntentReason
    goal: SyntheticPlanningGoal | None = None
    planning_input: StructuredInput | None = None
    clarification_question: str | None = None
    missing_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported Executive intent schema version")
        if self.outcome is ExecutiveIntentOutcome.PLANNING_READY:
            if (
                self.reason is not ExecutiveIntentReason.READY
                or self.goal is None
                or self.planning_input is None
                or self.clarification_question is not None
                or self.missing_fields
            ):
                raise ValueError("planning-ready intent has an invalid shape")
            return
        if self.goal is not None or self.planning_input is not None:
            raise ValueError("non-planning intent cannot contain planning data")
        if self.outcome is ExecutiveIntentOutcome.CLARIFICATION_REQUIRED:
            if (
                self.reason is not ExecutiveIntentReason.MISSING_INFORMATION
                or self.clarification_question is None
                or not self.clarification_question.strip()
                or len(self.clarification_question) > MAX_CLARIFICATION_CHARACTERS
                or not 1 <= len(self.missing_fields) <= MAX_MISSING_FIELDS
                or any(_FIELD.fullmatch(item) is None for item in self.missing_fields)
                or len(set(self.missing_fields)) != len(self.missing_fields)
            ):
                raise ValueError("clarification intent has an invalid shape")
            return
        if (
            self.reason is not ExecutiveIntentReason.UNSUPPORTED_REQUEST
            or self.clarification_question is not None
            or self.missing_fields
        ):
            raise ValueError("unsupported intent has an invalid shape")


@dataclass(frozen=True, slots=True)
class ClarificationRequest:
    question: str
    missing_fields: tuple[str, ...]
    reason: ExecutiveIntentReason

    def __post_init__(self) -> None:
        ExecutiveIntent(
            1,
            ExecutiveIntentOutcome.CLARIFICATION_REQUIRED,
            self.reason,
            clarification_question=self.question,
            missing_fields=self.missing_fields,
        )


@dataclass(frozen=True, slots=True)
class ExecutiveIntakeResult:
    intake_request_id: UUID
    received_at: datetime
    workspace_id: UUID
    actor: Actor
    correlation_id: UUID
    causation_id: UUID | None
    outcome: ExecutiveIntakeOutcome
    plan: ExecutivePlanPresentation | None = None
    clarification: ClarificationRequest | None = None
    reason: ExecutiveIntentReason | None = None
    failure: ExecutiveIntakeFailure | None = None

    def __post_init__(self) -> None:
        _require_ids(self.intake_request_id, self.workspace_id, self.correlation_id)
        if self.received_at.tzinfo is None or self.received_at.utcoffset() is None:
            raise ValueError("Executive intake timestamp must be timezone-aware")
        if self.causation_id is not None:
            _require_ids(self.causation_id)
        populated = sum(
            value is not None
            for value in (self.plan, self.clarification, self.reason, self.failure)
        )
        if populated != 1:
            raise ValueError("Executive intake result requires exactly one outcome value")
        expected = {
            ExecutiveIntakeOutcome.PLANNED: self.plan,
            ExecutiveIntakeOutcome.CLARIFICATION_REQUIRED: self.clarification,
            ExecutiveIntakeOutcome.UNSUPPORTED: self.reason,
            ExecutiveIntakeOutcome.FAILED: self.failure,
        }[self.outcome]
        if expected is None:
            raise ValueError("Executive intake result does not match its outcome")


class ExecutivePlanningFacade(Protocol):
    def plan(self, request: ExecutivePlanningRequest) -> ExecutivePlanningResult: ...


def _require_ids(*values: UUID) -> None:
    if any(value.int == 0 for value in values):
        raise ValueError("Executive intake identifiers must not be nil")
