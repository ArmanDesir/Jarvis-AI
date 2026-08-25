"""Published presentation-only Executive planning contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from rightjob.contracts.capabilities import CapabilityReference, EffectClassification
from rightjob.contracts.departments import DepartmentReference
from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.planning import (
    PlannerIdentity,
    PlanningConstraints,
    StructuredInput,
    SyntheticPlanningGoal,
    SyntheticStepObjective,
)


class ExecutivePlanningOutcome(StrEnum):
    PLANNED = "planned"
    NOT_PLANNABLE = "not_plannable"
    FAILED = "failed"


class ExecutivePlanningFailure(StrEnum):
    PLANNING_REJECTED = "planning_rejected"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_CONFIGURATION = "provider_configuration"
    INVALID_PROVIDER_OUTPUT = "invalid_provider_output"
    INTERNAL_FAILURE = "internal_failure"


@dataclass(frozen=True, slots=True)
class ExecutivePlanningRequest:
    workspace_id: UUID
    actor: Actor
    correlation_id: UUID
    causation_id: UUID | None
    goal: SyntheticPlanningGoal
    constraints: PlanningConstraints
    input: StructuredInput

    def __post_init__(self) -> None:
        _require_ids(self.workspace_id, self.correlation_id)
        if self.causation_id is not None:
            _require_ids(self.causation_id)
        if self.actor.type not in {ActorType.USER, ActorType.SYSTEM}:
            raise ValueError("Executive planning actor must be user or system")
        if self.input.encoded_bytes > self.constraints.maximum_input_bytes:
            raise ValueError("Executive planning input exceeds the configured bound")


@dataclass(frozen=True, slots=True)
class ExecutivePlanStep:
    step_id: UUID
    sequence: int
    objective: SyntheticStepObjective
    department: DepartmentReference
    capability: CapabilityReference
    dependency_step_ids: tuple[UUID, ...]
    effect_classification: EffectClassification
    input: StructuredInput


@dataclass(frozen=True, slots=True)
class ExecutivePlanPresentation:
    plan_id: UUID
    planning_request_id: UUID
    workspace_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    actor: Actor
    planner: PlannerIdentity
    steps: tuple[ExecutivePlanStep, ...]

    def __post_init__(self) -> None:
        _require_ids(
            self.plan_id,
            self.planning_request_id,
            self.workspace_id,
            self.correlation_id,
        )
        if self.causation_id is not None:
            _require_ids(self.causation_id)
        if self.actor.type not in {ActorType.USER, ActorType.SYSTEM}:
            raise ValueError("Executive plan actor must be user or system")
        if not self.steps:
            raise ValueError("Executive plan presentation must contain steps")


@dataclass(frozen=True, slots=True)
class ExecutivePlanningResult:
    outcome: ExecutivePlanningOutcome
    plan: ExecutivePlanPresentation | None = None
    failure: ExecutivePlanningFailure | None = None

    def __post_init__(self) -> None:
        if self.outcome is ExecutivePlanningOutcome.PLANNED:
            if self.plan is None or self.failure is not None:
                raise ValueError("planned result requires only a plan")
        elif self.plan is not None or self.failure is None:
            raise ValueError("non-planned result requires only a failure")


def _require_ids(*values: UUID) -> None:
    if any(value.int == 0 for value in values):
        raise ValueError("Executive planning identifiers must not be nil")
