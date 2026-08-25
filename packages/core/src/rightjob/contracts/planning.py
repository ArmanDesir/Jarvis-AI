"""Published provider-neutral planning contracts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, TypeAlias
from uuid import UUID

from rightjob.contracts.capabilities import (
    CapabilityReference,
    ContractReference,
    EffectClassification,
    SemanticVersion,
)
from rightjob.contracts.departments import DepartmentReference, WorkCategory
from rightjob.contracts.events import Actor, ActorType, JsonScalar, JsonValue

_KEY = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
StructuredScalar: TypeAlias = JsonScalar
_SECRET_KEYS = frozenset({"authorization", "credential", "password", "secret", "token"})


class SyntheticPlanningGoal(StrEnum):
    PREPARE = "prepare"
    TRANSFORM = "transform"
    VERIFY = "verify"
    PREPARE_TRANSFORM_VERIFY = "prepare_transform_verify"


class SyntheticStepObjective(StrEnum):
    PREPARE = "prepare"
    TRANSFORM = "transform"
    VERIFY = "verify"


@dataclass(frozen=True, slots=True)
class StructuredInput:
    fields: tuple[tuple[str, StructuredScalar], ...]

    def __post_init__(self) -> None:
        keys = tuple(key for key, _ in self.fields)
        if not keys or len(keys) != len(set(keys)):
            raise ValueError("structured input keys must be nonempty and unique")
        for key in keys:
            if not key.strip():
                raise ValueError("structured input keys must be nonblank")
            if key.lower() in _SECRET_KEYS:
                raise ValueError("secret-bearing structured input is not permitted")

    @property
    def encoded_bytes(self) -> int:
        return len(json.dumps(self.as_dict(), separators=(",", ":")).encode())

    def as_dict(self) -> dict[str, JsonValue]:
        return {key: value for key, value in self.fields}


@dataclass(frozen=True, slots=True)
class PlanningConstraints:
    maximum_steps: int = 16
    maximum_input_bytes: int = 65_536

    def __post_init__(self) -> None:
        if not 1 <= self.maximum_steps <= 16:
            raise ValueError("maximum_steps must be between 1 and 16")
        if not 1 <= self.maximum_input_bytes <= 65_536:
            raise ValueError("maximum_input_bytes must be between 1 and 65536")


@dataclass(frozen=True, slots=True)
class PlanningRequest:
    planning_request_id: UUID
    workspace_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    actor: Actor
    goal: SyntheticPlanningGoal
    constraints: PlanningConstraints
    input: StructuredInput
    created_at: datetime

    def __post_init__(self) -> None:
        _require_ids(self.planning_request_id, self.workspace_id, self.correlation_id)
        if self.causation_id is not None:
            _require_ids(self.causation_id)
        if self.actor.type not in {ActorType.USER, ActorType.SYSTEM}:
            raise ValueError("planning actor must be user or system")
        _require_aware("created_at", self.created_at)
        if self.input.encoded_bytes > self.constraints.maximum_input_bytes:
            raise ValueError("planning input exceeds the configured bound")


@dataclass(frozen=True, slots=True)
class PlanningContext:
    workspace_id: UUID
    actor: Actor
    correlation_id: UUID
    causation_id: UUID | None
    available_departments: tuple[DepartmentReference, ...]
    available_capabilities: tuple[CapabilityReference, ...]
    constraints: PlanningConstraints

    def __post_init__(self) -> None:
        _require_ids(self.workspace_id, self.correlation_id)
        if self.causation_id is not None:
            _require_ids(self.causation_id)
        if len(set(self.available_departments)) != len(self.available_departments):
            raise ValueError("available Departments must be unique")
        if len(set(self.available_capabilities)) != len(self.available_capabilities):
            raise ValueError("available Capabilities must be unique")


@dataclass(frozen=True, slots=True)
class PlannerIdentity:
    planner_key: str
    semantic_version: SemanticVersion

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.planner_key) is None:
            raise ValueError("planner_key must be canonical")


@dataclass(frozen=True, slots=True)
class PlanStep:
    step_id: UUID
    sequence: int
    objective: SyntheticStepObjective
    work_category: WorkCategory
    department: DepartmentReference
    capability: CapabilityReference
    input: StructuredInput
    dependency_step_ids: tuple[UUID, ...]
    expected_output: ContractReference
    effect_classification: EffectClassification

    def __post_init__(self) -> None:
        _require_ids(self.step_id)
        if self.sequence < 0:
            raise ValueError("sequence must not be negative")
        if len(set(self.dependency_step_ids)) != len(self.dependency_step_ids):
            raise ValueError("dependency step IDs must be unique")
        if self.step_id in self.dependency_step_ids:
            raise ValueError("a plan step cannot depend on itself")


@dataclass(frozen=True, slots=True)
class ProposedPlan:
    plan_id: UUID
    workspace_id: UUID
    planning_request_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    planner: PlannerIdentity
    plan_version: SemanticVersion
    steps: tuple[PlanStep, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        _validate_plan_envelope(self)


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """A deterministically validated in-memory plan, never execution authority."""

    plan_id: UUID
    workspace_id: UUID
    planning_request_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    planner: PlannerIdentity
    plan_version: SemanticVersion
    steps: tuple[PlanStep, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        _validate_plan_envelope(self)


class Planner(Protocol):
    def plan(self, request: PlanningRequest, context: PlanningContext) -> ProposedPlan: ...


class PlanningFailure(StrEnum):
    PROPOSAL_REJECTED = "proposal_rejected"
    PROVIDER_TRANSIENT = "provider_transient"
    PROVIDER_CONFIGURATION = "provider_configuration"
    PROVIDER_REJECTED_OUTPUT = "provider_rejected_output"
    PROVIDER_INVALID_OUTPUT = "provider_invalid_output"


class PlanningApplicationError(RuntimeError):
    """Normalized Planning failure exposed across the published boundary."""

    def __init__(self, failure: PlanningFailure) -> None:
        self.failure = failure
        super().__init__(failure.value)


class PlanningApplication(Protocol):
    def plan(self, request: PlanningRequest, context: PlanningContext) -> ExecutionPlan: ...


def _validate_plan_envelope(plan: ProposedPlan | ExecutionPlan) -> None:
    _require_ids(plan.plan_id, plan.workspace_id, plan.planning_request_id, plan.correlation_id)
    if plan.causation_id is not None:
        _require_ids(plan.causation_id)
    _require_aware("created_at", plan.created_at)
    if not plan.steps:
        raise ValueError("plan must contain at least one step")


def _require_ids(*values: UUID) -> None:
    if any(value.int == 0 for value in values):
        raise ValueError("planning identifiers must not be nil")


def _require_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
