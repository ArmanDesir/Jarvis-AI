"""Published immutable result-validation and non-authoritative review contracts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from rightjob.contracts.capabilities import (
    CapabilityReference,
    ContractReference,
    SemanticVersion,
)
from rightjob.contracts.events import JsonValue

MAX_RESULT_BYTES = 65_536
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_KEY = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_SECRET_KEYS = {"authorization", "credential", "password", "secret", "token"}


class ResultContractError(ValueError):
    """A result, validation, review, or presentation contract is invalid."""


def canonical_result_payload(value: JsonValue) -> bytes:
    """Encode bounded JSON deterministically for artifact identity."""
    if _contains_secret(value):
        raise ResultContractError("secret-bearing result payload is not permitted")
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ResultContractError("result payload must be JSON") from error
    if not encoded or len(encoded) > MAX_RESULT_BYTES:
        raise ResultContractError("result payload exceeds the maximum size")
    return encoded


def result_digest(payload_json: bytes) -> str:
    return hashlib.sha256(payload_json).hexdigest()


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    artifact_id: UUID
    version: int
    sha256: str

    def __post_init__(self) -> None:
        _ids(self.artifact_id)
        if self.version < 1:
            raise ResultContractError("artifact version must be positive")
        if _DIGEST.fullmatch(self.sha256) is None:
            raise ResultContractError("artifact SHA-256 must be lowercase hexadecimal")


@dataclass(frozen=True, slots=True)
class ResultProvenance:
    workspace_id: UUID
    run_id: UUID
    step_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    capability: CapabilityReference
    output_contract: ContractReference
    artifact: ArtifactReference
    produced_at: datetime

    def __post_init__(self) -> None:
        _ids(self.workspace_id, self.run_id, self.step_id, self.correlation_id)
        if self.causation_id is not None:
            _ids(self.causation_id)
        _aware("produced_at", self.produced_at)


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    provenance: ResultProvenance
    payload_json: bytes

    def __post_init__(self) -> None:
        try:
            decoded: JsonValue = json.loads(self.payload_json)
        except (TypeError, ValueError, UnicodeDecodeError) as error:
            raise ResultContractError("result payload must be UTF-8 JSON") from error
        if canonical_result_payload(decoded) != self.payload_json:
            raise ResultContractError("result payload must use canonical JSON encoding")
        if result_digest(self.payload_json) != self.provenance.artifact.sha256:
            raise ResultContractError("result payload does not match artifact SHA-256")


@dataclass(frozen=True, slots=True)
class ResultValidationContext:
    workspace_id: UUID
    run_id: UUID
    step_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    capability: CapabilityReference
    output_contract: ContractReference
    artifact: ArtifactReference

    def __post_init__(self) -> None:
        _ids(self.workspace_id, self.run_id, self.step_id, self.correlation_id)
        if self.causation_id is not None:
            _ids(self.causation_id)


class ResultValidationOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class ResultValidationReason(StrEnum):
    ACCEPTED = "accepted"
    PROVENANCE_MISMATCH = "provenance_mismatch"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    CAPABILITY_MISMATCH = "capability_mismatch"
    OUTPUT_CONTRACT_MISMATCH = "output_contract_mismatch"
    ARTIFACT_MISMATCH = "artifact_mismatch"
    INVALID_TIMESTAMP = "invalid_timestamp"
    PAYLOAD_TOO_LARGE = "payload_too_large"


@dataclass(frozen=True, slots=True)
class ValidationCriteriaReference:
    criteria_key: str
    semantic_version: SemanticVersion

    def __post_init__(self) -> None:
        _key("criteria_key", self.criteria_key)


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    evidence_key: str
    reference: str

    def __post_init__(self) -> None:
        _key("evidence_key", self.evidence_key)
        if not 1 <= len(self.reference) <= 500 or not self.reference.strip():
            raise ResultContractError("evidence reference must be bounded and nonblank")


@dataclass(frozen=True, slots=True)
class ResultValidationEvidence:
    validation_id: UUID
    result: CapabilityResult
    criteria: ValidationCriteriaReference
    outcome: ResultValidationOutcome
    reasons: tuple[ResultValidationReason, ...]
    evidence: tuple[EvidenceReference, ...]
    validated_at: datetime

    def __post_init__(self) -> None:
        _ids(self.validation_id)
        _aware("validated_at", self.validated_at)
        if not self.reasons or len(set(self.reasons)) != len(self.reasons):
            raise ResultContractError("validation reasons must be nonempty and unique")
        if len(set(self.evidence)) != len(self.evidence):
            raise ResultContractError("validation evidence references must be unique")
        if self.outcome is ResultValidationOutcome.PASSED:
            if self.reasons != (ResultValidationReason.ACCEPTED,) or not self.evidence:
                raise ResultContractError("passed validation requires accepted evidence")
        elif ResultValidationReason.ACCEPTED in self.reasons:
            raise ResultContractError("failed validation cannot be accepted")

    @property
    def provenance(self) -> ResultProvenance:
        return self.result.provenance


class ReviewRecommendation(StrEnum):
    ACCEPT = "accept"
    REVISE = "revise"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


@dataclass(frozen=True, slots=True)
class ReviewCriteria:
    criteria_key: str
    semantic_version: SemanticVersion
    minimum_score: int

    def __post_init__(self) -> None:
        _key("criteria_key", self.criteria_key)
        if not 0 <= self.minimum_score <= 100:
            raise ResultContractError("minimum review score must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class ReviewScore:
    criteria_key: str
    score: int

    def __post_init__(self) -> None:
        _key("criteria_key", self.criteria_key)
        if not 0 <= self.score <= 100:
            raise ResultContractError("review score must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class ReviewAssessment:
    assessment_id: UUID
    validation_id: UUID
    workspace_id: UUID
    run_id: UUID
    step_id: UUID
    criteria: ReviewCriteria
    scores: tuple[ReviewScore, ...]
    reasons: tuple[str, ...]
    evidence: tuple[EvidenceReference, ...]
    recommendation: ReviewRecommendation
    assessed_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.assessment_id,
            self.validation_id,
            self.workspace_id,
            self.run_id,
            self.step_id,
        )
        _aware("assessed_at", self.assessed_at)
        if not self.scores or len({item.criteria_key for item in self.scores}) != len(self.scores):
            raise ResultContractError("review scores must be nonempty and uniquely keyed")
        if not self.reasons or len(set(self.reasons)) != len(self.reasons):
            raise ResultContractError("review reasons must be nonempty and unique")
        if any(not reason.strip() or len(reason) > 500 for reason in self.reasons):
            raise ResultContractError("review reasons must be bounded and nonblank")
        if not self.evidence or len(set(self.evidence)) != len(self.evidence):
            raise ResultContractError("review evidence must be nonempty and unique")


@dataclass(frozen=True, slots=True)
class ExecutiveReviewSummary:
    criteria_key: str
    criteria_version: SemanticVersion
    scores: tuple[ReviewScore, ...]
    recommendation: ReviewRecommendation

    def __post_init__(self) -> None:
        _key("criteria_key", self.criteria_key)
        if not self.scores or len({item.criteria_key for item in self.scores}) != len(self.scores):
            raise ResultContractError("review summary scores must be nonempty and uniquely keyed")


class Reviewer(Protocol):
    def review(
        self, evidence: ResultValidationEvidence, criteria: ReviewCriteria
    ) -> ReviewAssessment: ...


@dataclass(frozen=True, slots=True)
class ExecutiveResultPresentation:
    workspace_id: UUID
    run_id: UUID
    step_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    capability: CapabilityReference
    output_contract: ContractReference
    artifact: ArtifactReference
    validation_id: UUID
    validation_evidence: tuple[EvidenceReference, ...]
    review: ExecutiveReviewSummary | None
    presented_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.workspace_id,
            self.run_id,
            self.step_id,
            self.correlation_id,
            self.validation_id,
        )
        if self.causation_id is not None:
            _ids(self.causation_id)
        _aware("presented_at", self.presented_at)
        if not self.validation_evidence:
            raise ResultContractError("presentation requires validation evidence")


def _contains_secret(value: JsonValue) -> bool:
    if isinstance(value, dict):
        return any(
            key.lower() in _SECRET_KEYS or _contains_secret(item) for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_secret(item) for item in value)
    return False


def _ids(*values: UUID) -> None:
    if any(value.int == 0 for value in values):
        raise ResultContractError("result identifiers must not be nil")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ResultContractError(f"{name} must be timezone-aware")


def _key(name: str, value: str) -> None:
    if not 1 <= len(value) <= 100 or _KEY.fullmatch(value) is None:
        raise ResultContractError(f"{name} must be a bounded canonical identifier")
