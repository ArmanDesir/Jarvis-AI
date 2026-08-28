"""Published provider-neutral Capability Registry contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Sequence
from uuid import UUID

_SEMANTIC_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_KEY = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class SemanticVersion:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: str) -> SemanticVersion:
        match = _SEMANTIC_VERSION.fullmatch(value)
        if match is None:
            raise ValueError("invalid semantic version")
        prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
        build = tuple(match.group(5).split(".")) if match.group(5) else ()
        return cls(int(match.group(1)), int(match.group(2)), int(match.group(3)), prerelease, build)

    def precedence(self) -> tuple[int, int, int, int, tuple[tuple[int, int | str], ...]]:
        identifiers = tuple(
            (0, int(identifier)) if identifier.isdigit() else (1, identifier)
            for identifier in self.prerelease
        )
        return self.major, self.minor, self.patch, 1 if not self.prerelease else 0, identifiers

    def __str__(self) -> str:
        value = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            value += f"-{'.'.join(self.prerelease)}"
        if self.build:
            value += f"+{'.'.join(self.build)}"
        return value


@dataclass(frozen=True, slots=True)
class ContractReference:
    contract_key: str
    semantic_version: SemanticVersion
    maximum_payload_bytes: int

    def __post_init__(self) -> None:
        _require_key("contract_key", self.contract_key)
        if not 1 <= self.maximum_payload_bytes <= 65_536:
            raise ValueError("maximum_payload_bytes must be between 1 and 65536")


class EffectClassification(StrEnum):
    READ_ONLY = "read_only"
    REVERSIBLE = "reversible"
    CONSEQUENTIAL = "consequential"
    EXTERNAL_EFFECT = "external_effect"


class IdempotencyClassification(StrEnum):
    NATURALLY_IDEMPOTENT = "naturally_idempotent"
    REQUIRES_IDEMPOTENCY_KEY = "requires_idempotency_key"
    NON_IDEMPOTENT = "non_idempotent"


class RetryableFailure(StrEnum):
    TRANSIENT_DEPENDENCY = "transient_dependency"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class RetryMetadata:
    maximum_attempts: int
    retryable_failures: frozenset[RetryableFailure] = frozenset()

    def __post_init__(self) -> None:
        if not 1 <= self.maximum_attempts <= 10:
            raise ValueError("maximum_attempts must be between 1 and 10")


@dataclass(frozen=True, slots=True)
class TimeoutMetadata:
    timeout_seconds: int

    def __post_init__(self) -> None:
        if not 1 <= self.timeout_seconds <= 3_600:
            raise ValueError("timeout_seconds must be between 1 and 3600")


@dataclass(frozen=True, slots=True)
class CapabilityReference:
    capability_definition_id: UUID
    capability_key: str
    semantic_version: SemanticVersion

    def __post_init__(self) -> None:
        if self.capability_definition_id.int == 0:
            raise ValueError("capability_definition_id must not be nil")
        _require_key("capability_key", self.capability_key)


class QualityScoreImprovementRule(StrEnum):
    STRICTLY_GREATER = "strictly_greater"


@dataclass(frozen=True, slots=True)
class CapabilityQualityGatePolicy:
    policy_key: str
    semantic_version: SemanticVersion
    capability: CapabilityReference
    review_criteria_key: str
    review_criteria_version: SemanticVersion
    score_key: str
    minimum_score: int
    maximum_automated_revisions: int
    improvement_rule: QualityScoreImprovementRule

    def __post_init__(self) -> None:
        for name, value in (
            ("policy_key", self.policy_key),
            ("review_criteria_key", self.review_criteria_key),
            ("score_key", self.score_key),
        ):
            if type(value) is not str:
                raise ValueError(f"{name} must be a string")
            _require_key(name, value)
        if type(self.semantic_version) is not SemanticVersion:
            raise ValueError("semantic_version must be a SemanticVersion")
        if type(self.review_criteria_version) is not SemanticVersion:
            raise ValueError("review_criteria_version must be a SemanticVersion")
        _require_semantic_version(self.semantic_version)
        _require_semantic_version(self.review_criteria_version)
        if type(self.capability) is not CapabilityReference:
            raise ValueError("quality policy capability must be a CapabilityReference")
        if type(self.capability.capability_definition_id) is not UUID:
            raise ValueError("quality policy Capability identity must be a UUID")
        if type(self.capability.semantic_version) is not SemanticVersion:
            raise ValueError("quality policy Capability version must be a SemanticVersion")
        _require_semantic_version(self.capability.semantic_version)
        if type(self.minimum_score) is not int or not 0 <= self.minimum_score <= 100:
            raise ValueError("minimum_score must be an integer between 0 and 100")
        if (
            type(self.maximum_automated_revisions) is not int
            or not 0 <= self.maximum_automated_revisions <= 2
        ):
            raise ValueError("maximum_automated_revisions must be an integer between 0 and 2")
        if type(self.improvement_rule) is not QualityScoreImprovementRule:
            raise ValueError("improvement_rule must be a QualityScoreImprovementRule")


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    capability_definition_id: UUID
    capability_key: str
    semantic_version: SemanticVersion
    owner_key: str
    display_name: str
    description: str
    enabled: bool
    input_contract: ContractReference
    output_contract: ContractReference
    handler_key: str
    effect_classification: EffectClassification
    idempotency: IdempotencyClassification
    timeout: TimeoutMetadata
    retry: RetryMetadata
    quality_gate_policy: CapabilityQualityGatePolicy | None = None

    def __post_init__(self) -> None:
        if self.capability_definition_id.int == 0:
            raise ValueError("capability_definition_id must not be nil")
        for name, value in (
            ("capability_key", self.capability_key),
            ("owner_key", self.owner_key),
            ("handler_key", self.handler_key),
        ):
            _require_key(name, value)
        _require_text("display_name", self.display_name, 100)
        _require_text("description", self.description, 1_000)
        if self.quality_gate_policy is not None:
            if type(self.quality_gate_policy) is not CapabilityQualityGatePolicy:
                raise ValueError("quality_gate_policy must be a CapabilityQualityGatePolicy")
            if self.quality_gate_policy.capability != self.reference:
                raise ValueError("quality_gate_policy must bind the exact Capability definition")

    @property
    def reference(self) -> CapabilityReference:
        return CapabilityReference(
            self.capability_definition_id, self.capability_key, self.semantic_version
        )


class CapabilityCatalog(Protocol):
    def get(self, capability_key: str, version: SemanticVersion) -> CapabilityDefinition: ...

    def get_enabled(
        self, capability_key: str, version: SemanticVersion
    ) -> CapabilityDefinition: ...

    def latest_enabled(self, capability_key: str) -> CapabilityDefinition: ...

    def list_enabled(self) -> Sequence[CapabilityDefinition]: ...

    def list_by_owner(
        self, owner_key: str, *, enabled_only: bool = True
    ) -> Sequence[CapabilityDefinition]: ...


def _require_key(name: str, value: str) -> None:
    if _KEY.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical")


def _require_text(name: str, value: str, maximum: int) -> None:
    if not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be nonblank and at most {maximum} characters")


def _require_semantic_version(value: SemanticVersion) -> None:
    if type(value.prerelease) is not tuple or type(value.build) is not tuple:
        raise ValueError("semantic version identifiers must be immutable tuples")
    if any(type(item) is not str for item in (*value.prerelease, *value.build)):
        raise ValueError("semantic version identifiers must be strings")
    SemanticVersion.parse(str(value))
