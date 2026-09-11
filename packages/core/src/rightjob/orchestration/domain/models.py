"""Provider-neutral canonical execution values and state machines."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Mapping
from uuid import UUID

from rightjob.contracts.authorization import ExecutionAuthorizationReference
from rightjob.contracts.events import Actor, JsonValue
from rightjob.contracts.revision_execution import RevisionExecutionAuthorizationReference


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class InitiatorType(StrEnum):
    USER = "user"
    SYSTEM = "system"


class ReconciliationState(StrEnum):
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    RESOLVED = "resolved"


class FailureClassification(StrEnum):
    VALIDATION = "validation"
    BUSINESS = "business"
    INFRASTRUCTURE_TRANSIENT = "infrastructure_transient"
    INFRASTRUCTURE_EXHAUSTED = "infrastructure_exhausted"
    CANCELLED = "cancelled"
    UNKNOWN_OUTCOME = "unknown_outcome"
    INTERNAL_DEFECT = "internal_defect"


class InvalidExecutionTransition(ValueError):
    """A canonical execution state transition is not allowed."""


_RUN_TRANSITIONS: Mapping[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset(
        {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.RECONCILIATION_REQUIRED}
    ),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.WAITING,
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.RECONCILIATION_REQUIRED,
        }
    ),
    RunStatus.WAITING: frozenset(
        {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.RECONCILIATION_REQUIRED}
    ),
    RunStatus.RECONCILIATION_REQUIRED: frozenset(
        {RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELLED}
    ),
    RunStatus.SUCCEEDED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}

_STEP_TRANSITIONS: Mapping[StepStatus, frozenset[StepStatus]] = {
    StepStatus.PENDING: frozenset({StepStatus.RUNNING, StepStatus.CANCELLED}),
    StepStatus.RUNNING: frozenset(
        {
            StepStatus.WAITING,
            StepStatus.SUCCEEDED,
            StepStatus.FAILED,
            StepStatus.CANCELLED,
            StepStatus.RECONCILIATION_REQUIRED,
        }
    ),
    StepStatus.WAITING: frozenset(
        {StepStatus.RUNNING, StepStatus.CANCELLED, StepStatus.RECONCILIATION_REQUIRED}
    ),
    StepStatus.RECONCILIATION_REQUIRED: frozenset(
        {StepStatus.RUNNING, StepStatus.FAILED, StepStatus.CANCELLED}
    ),
    StepStatus.SUCCEEDED: frozenset(),
    StepStatus.FAILED: frozenset(),
    StepStatus.CANCELLED: frozenset(),
}


def _aware(name: str, value: datetime | None) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{name} must be timezone-aware")


def _text(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _contains_secret(value: JsonValue) -> bool:
    if isinstance(value, dict):
        return any(
            key.lower() in {"authorization", "credential", "password", "secret", "token"}
            or _contains_secret(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_secret(item) for item in value)
    return False


@dataclass(frozen=True, slots=True)
class RequestedStep:
    id: UUID
    step_type: str
    sequence: int
    input_ref: str
    max_attempts: int = 1

    def __post_init__(self) -> None:
        _text("step_type", self.step_type)
        _text("input_ref", self.input_ref)
        if self.sequence < 0:
            raise ValueError("sequence must not be negative")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    execution_id: UUID
    workspace_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    actor: Actor
    initiator_type: InitiatorType
    authorization: ExecutionAuthorizationReference | RevisionExecutionAuthorizationReference
    workflow_definition_id: UUID
    workflow_type: str
    workflow_version: str
    steps: tuple[RequestedStep, ...]
    input: dict[str, JsonValue]
    created_at: datetime

    def __post_init__(self) -> None:
        if self.authorization.workspace_id != self.workspace_id:
            raise ValueError("execution authorization Workspace must match request")
        _text("workflow_type", self.workflow_type)
        _text("workflow_version", self.workflow_version)
        _aware("created_at", self.created_at)
        if not self.steps:
            raise ValueError("execution must contain at least one step")
        if len({step.id for step in self.steps}) != len(self.steps):
            raise ValueError("step IDs must be unique")
        if tuple(step.sequence for step in self.steps) != tuple(range(len(self.steps))):
            raise ValueError("steps must have contiguous ordered sequence values")
        encoded = json.dumps(self.input, separators=(",", ":"))
        if len(encoded.encode()) > 65_536:
            raise ValueError("execution input exceeds 64 KiB")
        if _contains_secret(self.input):
            raise ValueError("secret-bearing execution input is not permitted")


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    execution_id: UUID
    workspace_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    actor: Actor
    initiator_type: InitiatorType


@dataclass(frozen=True, slots=True)
class ExecutionRun:
    id: UUID
    execution_request_id: UUID
    workspace_id: UUID
    workflow_definition_id: UUID
    workflow_type: str
    workflow_version: str
    status: RunStatus
    correlation_id: UUID
    causation_id: UUID | None
    actor: Actor
    initiator_type: InitiatorType
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancellation_requested_at: datetime | None = None
    cancelled_at: datetime | None = None
    reconciliation_state: ReconciliationState = ReconciliationState.NOT_REQUIRED
    version: int = 1

    def __post_init__(self) -> None:
        _text("workflow_type", self.workflow_type)
        _text("workflow_version", self.workflow_version)
        for name in (
            "created_at",
            "started_at",
            "completed_at",
            "cancellation_requested_at",
            "cancelled_at",
        ):
            _aware(name, getattr(self, name))
        if self.version < 1:
            raise ValueError("version must be positive")

    def transition(self, status: RunStatus, at: datetime) -> ExecutionRun:
        _aware("transition time", at)
        if status not in _RUN_TRANSITIONS[self.status]:
            raise InvalidExecutionTransition(f"run cannot transition {self.status} -> {status}")
        started_at = (
            at if status is RunStatus.RUNNING and self.started_at is None else self.started_at
        )
        completed_at = (
            at if status in {RunStatus.SUCCEEDED, RunStatus.FAILED} else self.completed_at
        )
        cancelled_at = at if status is RunStatus.CANCELLED else self.cancelled_at
        reconciliation_state = self.reconciliation_state
        if status is RunStatus.RECONCILIATION_REQUIRED:
            reconciliation_state = ReconciliationState.REQUIRED
        elif self.status is RunStatus.RECONCILIATION_REQUIRED:
            reconciliation_state = ReconciliationState.RESOLVED
        return replace(
            self,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            cancelled_at=cancelled_at,
            reconciliation_state=reconciliation_state,
            version=self.version + 1,
        )

    def request_cancellation(self, at: datetime) -> ExecutionRun:
        _aware("cancellation request time", at)
        if self.status in {RunStatus.SUCCEEDED, RunStatus.FAILED}:
            raise InvalidExecutionTransition("terminal run cannot be cancelled")
        if self.cancellation_requested_at is not None or self.status is RunStatus.CANCELLED:
            return self
        return replace(self, cancellation_requested_at=at, version=self.version + 1)


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    id: UUID
    run_id: UUID
    workspace_id: UUID
    step_type: str
    sequence: int
    status: StepStatus
    attempt_count: int
    max_attempts: int
    input_ref: str
    output_evidence_ref: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failure_classification: FailureClassification | None = None
    version: int = 1

    def __post_init__(self) -> None:
        _text("step_type", self.step_type)
        _text("input_ref", self.input_ref)
        _aware("started_at", self.started_at)
        _aware("completed_at", self.completed_at)
        if self.sequence < 0 or self.attempt_count < 0 or self.max_attempts < 1:
            raise ValueError("invalid step position or attempt information")
        if self.attempt_count > self.max_attempts:
            raise ValueError("attempt_count cannot exceed max_attempts")
        if self.version < 1:
            raise ValueError("version must be positive")

    def transition(
        self,
        status: StepStatus,
        at: datetime,
        *,
        failure: FailureClassification | None = None,
        evidence_ref: str | None = None,
    ) -> ExecutionStep:
        _aware("transition time", at)
        if status not in _STEP_TRANSITIONS[self.status]:
            raise InvalidExecutionTransition(f"step cannot transition {self.status} -> {status}")
        if status is StepStatus.RECONCILIATION_REQUIRED:
            failure = FailureClassification.UNKNOWN_OUTCOME
        if status is StepStatus.FAILED and failure is None:
            raise ValueError("failed step requires failure classification")
        started_at = (self.started_at or at) if status is StepStatus.RUNNING else self.started_at
        attempt_count = (
            self.attempt_count + 1 if status is StepStatus.RUNNING else self.attempt_count
        )
        completed_at = (
            at
            if status in {StepStatus.SUCCEEDED, StepStatus.FAILED, StepStatus.CANCELLED}
            else self.completed_at
        )
        return replace(
            self,
            status=status,
            attempt_count=attempt_count,
            output_evidence_ref=evidence_ref,
            started_at=started_at,
            completed_at=completed_at,
            failure_classification=failure,
            version=self.version + 1,
        )


@dataclass(frozen=True, slots=True)
class CompiledExecution:
    context: ExecutionContext
    workflow_definition_id: UUID
    workflow_type: str
    workflow_version: str
    steps: tuple[RequestedStep, ...]
    input: dict[str, JsonValue]
