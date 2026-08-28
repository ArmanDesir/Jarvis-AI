"""Published contracts for Orchestration-owned result quality governance."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from rightjob.contracts.capabilities import CapabilityReference, SemanticVersion
from rightjob.contracts.events import Actor
from rightjob.contracts.review import ArtifactReference

_KEY = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class QualityGateContractError(ValueError):
    """A quality-governance contract or trusted binding is invalid."""


class QualityGateStatus(StrEnum):
    AWAITING_REVIEW = "awaiting_review"
    REVISION_REQUIRED = "revision_required"
    ACCEPTED = "accepted"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class QualityGateOutcome(StrEnum):
    ACCEPTED = "accepted"
    REVISION_REQUIRED = "revision_required"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class QualityGateReason(StrEnum):
    THRESHOLD_MET = "threshold_met"
    THRESHOLD_NOT_MET = "threshold_not_met"
    NO_PRIOR_COMPARABLE_SCORE = "no_prior_comparable_score"
    SCORE_STRICTLY_IMPROVED = "score_strictly_improved"
    SCORE_NOT_IMPROVED = "score_not_improved"
    REVISION_BUDGET_REMAINING = "revision_budget_remaining"
    REVISION_BUDGET_EXHAUSTED = "revision_budget_exhausted"
    REVIEWER_ESCALATION_REQUESTED = "reviewer_escalation_requested"


@dataclass(frozen=True, slots=True)
class QualityGateCommand:
    command_id: UUID
    quality_gate_id: UUID
    workspace_id: UUID
    run_id: UUID
    step_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    artifact: ArtifactReference
    actor: Actor
    expected_state_version: int | None
    issued_at: datetime

    def __post_init__(self) -> None:
        _require_uuids(
            self.command_id,
            self.quality_gate_id,
            self.workspace_id,
            self.run_id,
            self.step_id,
            self.correlation_id,
        )
        if self.causation_id is not None:
            _require_uuids(self.causation_id)
        _require_artifact(self.artifact)
        if type(self.actor) is not Actor:
            raise QualityGateContractError("actor must be an Actor")
        if self.expected_state_version is not None:
            _require_int("expected_state_version", self.expected_state_version, 1, 2_147_483_647)
        _require_aware("issued_at", self.issued_at)


@dataclass(frozen=True, slots=True)
class QualityGateState:
    quality_gate_id: UUID
    workspace_id: UUID
    run_id: UUID
    step_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    capability: CapabilityReference
    policy_key: str
    policy_version: SemanticVersion
    criteria_key: str
    criteria_version: SemanticVersion
    score_key: str
    status: QualityGateStatus
    automated_revision_count: int
    last_artifact: ArtifactReference
    last_validation_id: UUID
    last_assessment_id: UUID
    last_score: int
    last_decision_id: UUID
    version: int
    updated_at: datetime

    def __post_init__(self) -> None:
        _require_uuids(
            self.quality_gate_id,
            self.workspace_id,
            self.run_id,
            self.step_id,
            self.correlation_id,
            self.last_validation_id,
            self.last_assessment_id,
            self.last_decision_id,
        )
        if self.causation_id is not None:
            _require_uuids(self.causation_id)
        _require_capability(self.capability)
        _require_keys(
            ("policy_key", self.policy_key),
            ("criteria_key", self.criteria_key),
            ("score_key", self.score_key),
        )
        _require_version("policy_version", self.policy_version)
        _require_version("criteria_version", self.criteria_version)
        _require_exact("status", self.status, QualityGateStatus)
        _require_int("automated_revision_count", self.automated_revision_count, 0, 2)
        _require_artifact(self.last_artifact)
        _require_int("last_score", self.last_score, 0, 100)
        _require_int("version", self.version, 1, 2_147_483_647)
        _require_aware("updated_at", self.updated_at)


@dataclass(frozen=True, slots=True)
class QualityGateDecisionEvidence:
    decision_id: UUID
    command_id: UUID
    quality_gate_id: UUID
    workspace_id: UUID
    run_id: UUID
    step_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    capability: CapabilityReference
    policy_key: str
    policy_version: SemanticVersion
    criteria_key: str
    criteria_version: SemanticVersion
    score_key: str
    score: int
    minimum_score: int
    prior_score: int | None
    artifact: ArtifactReference
    validation_id: UUID
    assessment_id: UUID
    revision_count_before: int
    revision_count_after: int
    decided_at: datetime

    def __post_init__(self) -> None:
        _require_uuids(
            self.decision_id,
            self.command_id,
            self.quality_gate_id,
            self.workspace_id,
            self.run_id,
            self.step_id,
            self.correlation_id,
            self.validation_id,
            self.assessment_id,
        )
        if self.causation_id is not None:
            _require_uuids(self.causation_id)
        _require_capability(self.capability)
        _require_keys(
            ("policy_key", self.policy_key),
            ("criteria_key", self.criteria_key),
            ("score_key", self.score_key),
        )
        _require_version("policy_version", self.policy_version)
        _require_version("criteria_version", self.criteria_version)
        _require_int("score", self.score, 0, 100)
        _require_int("minimum_score", self.minimum_score, 0, 100)
        if self.prior_score is not None:
            _require_int("prior_score", self.prior_score, 0, 100)
        _require_artifact(self.artifact)
        _require_int("revision_count_before", self.revision_count_before, 0, 2)
        _require_int("revision_count_after", self.revision_count_after, 0, 2)
        if self.revision_count_after < self.revision_count_before:
            raise QualityGateContractError("revision count cannot decrease")
        _require_aware("decided_at", self.decided_at)


@dataclass(frozen=True, slots=True)
class QualityGateDecision:
    command: QualityGateCommand
    outcome: QualityGateOutcome
    reasons: tuple[QualityGateReason, ...]
    evidence: QualityGateDecisionEvidence
    next_state: QualityGateState

    def __post_init__(self) -> None:
        _require_exact("command", self.command, QualityGateCommand)
        _require_exact("outcome", self.outcome, QualityGateOutcome)
        _require_tuple("reasons", self.reasons, QualityGateReason, maximum=8)
        if not self.reasons or len(set(self.reasons)) != len(self.reasons):
            raise QualityGateContractError("decision reasons must be nonempty and unique")
        _require_exact("evidence", self.evidence, QualityGateDecisionEvidence)
        _require_exact("next_state", self.next_state, QualityGateState)
        if self.evidence.command_id != self.command.command_id:
            raise QualityGateContractError("decision evidence must bind the command")
        expected_status = QualityGateStatus(self.outcome.value)
        if self.next_state.status is not expected_status:
            raise QualityGateContractError("decision outcome must match next state")


def _require_uuids(*values: UUID) -> None:
    if any(type(value) is not UUID or value.int == 0 for value in values):
        raise QualityGateContractError("identifiers must be non-nil UUIDs")


def _require_aware(name: str, value: datetime) -> None:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise QualityGateContractError(f"{name} must be a timezone-aware datetime")


def _require_int(name: str, value: int, minimum: int, maximum: int) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise QualityGateContractError(f"{name} must be an integer in range")


def _require_exact(name: str, value: object, expected: type[object]) -> None:
    if type(value) is not expected:
        raise QualityGateContractError(f"{name} must be a {expected.__name__}")


def _require_keys(*values: tuple[str, str]) -> None:
    for name, value in values:
        if type(value) is not str or _KEY.fullmatch(value) is None:
            raise QualityGateContractError(f"{name} must be a canonical key")


def _require_version(name: str, value: SemanticVersion) -> None:
    _require_exact(name, value, SemanticVersion)
    if type(value.prerelease) is not tuple or type(value.build) is not tuple:
        raise QualityGateContractError(f"{name} identifiers must be immutable tuples")
    try:
        SemanticVersion.parse(str(value))
    except (TypeError, ValueError) as error:
        raise QualityGateContractError(f"{name} must be a semantic version") from error


def _require_capability(value: CapabilityReference) -> None:
    _require_exact("capability", value, CapabilityReference)
    _require_uuids(value.capability_definition_id)
    _require_keys(("capability_key", value.capability_key))
    _require_version("capability_version", value.semantic_version)


def _require_artifact(value: ArtifactReference) -> None:
    _require_exact("artifact", value, ArtifactReference)
    _require_uuids(value.artifact_id)
    _require_int("artifact_version", value.version, 1, 2_147_483_647)
    if type(value.sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", value.sha256) is None:
        raise QualityGateContractError("artifact SHA-256 must be lowercase hexadecimal")


def _require_tuple(
    name: str,
    value: object,
    member_type: type[object],
    *,
    maximum: int,
) -> None:
    if type(value) is not tuple or len(value) > maximum:
        raise QualityGateContractError(f"{name} must be a bounded tuple")
    if any(type(member) is not member_type for member in value):
        raise QualityGateContractError(f"{name} contains an invalid member")
