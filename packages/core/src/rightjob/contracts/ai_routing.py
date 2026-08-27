"""Published provider-neutral contracts for deterministic AI capability routing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from rightjob.contracts.ai import AIModelReference
from rightjob.contracts.capabilities import SemanticVersion
from rightjob.contracts.events import DataSensitivity

_REGION = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ROUTING_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_ROUTING_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,199}$")
_UNSAFE_IDENTITY_COMPONENT = re.compile(
    r"(?:^|[/._:+-])(?:api[_-]?key|access[_-]?token|authorization|bearer|credential|"
    r"password|prompt|provider[_-]?response|raw[_-]?content|secret|sk|system[_-]?message|"
    r"token|instruction|instructions)(?:$|[/._:+-])",
    re.IGNORECASE,
)
_UNSAFE_CREDENTIAL_FRAGMENT = re.compile(
    r"api[_-]?key|access[_-]?token|authorization|bearer|credential|password|secret",
    re.IGNORECASE,
)
MAX_CONTEXT_TOKENS = 10_000_000
MAX_COST_MICRO_UNITS = 1_000_000_000_000
MAX_LATENCY_MILLISECONDS = 300_000
MAX_ROUTE_CANDIDATES = 128


class AIStructuredOutputGuarantee(StrEnum):
    NONE = "none"
    STRICT_SUBSET = "strict_subset"
    CANONICAL_CONTRACT = "canonical_contract"


class AIProviderQualification(StrEnum):
    QUALIFIED = "qualified"
    LIMITED = "limited"
    UNVERIFIED = "unverified"


class AIProviderAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class AIModality(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"


class AIRouteOutcome(StrEnum):
    SELECTED = "selected"
    UNAVAILABLE = "unavailable"


class AIRouteRejectionReason(StrEnum):
    STALE_EVIDENCE = "stale_evidence"
    UNAVAILABLE = "unavailable"
    QUALIFICATION_INSUFFICIENT = "qualification_insufficient"
    STRUCTURED_OUTPUT_INSUFFICIENT = "structured_output_insufficient"
    TOOLS_UNSUPPORTED = "tools_unsupported"
    CONTEXT_TOO_SMALL = "context_too_small"
    MODALITY_UNSUPPORTED = "modality_unsupported"
    PRIVACY_UNSUPPORTED = "privacy_unsupported"
    RETENTION_EXCEEDED = "retention_exceeded"
    REGION_UNSUPPORTED = "region_unsupported"
    COST_EXCEEDED = "cost_exceeded"
    LATENCY_EXCEEDED = "latency_exceeded"
    QUALITY_INSUFFICIENT = "quality_insufficient"
    FALLBACK_NOT_ALLOWED = "fallback_not_allowed"


class AIRoutingContractError(ValueError):
    """Raised when the trusted routing snapshot itself is malformed."""


@dataclass(frozen=True, slots=True)
class AIRouteRequirements:
    route_request_id: UUID
    workspace_id: UUID
    evaluated_at: datetime
    minimum_structured_output: AIStructuredOutputGuarantee
    tools_required: bool
    minimum_context_tokens: int
    required_modalities: frozenset[AIModality]
    data_sensitivity: DataSensitivity
    maximum_retention_days: int
    allowed_regions: frozenset[str]
    maximum_cost_micro_units: int
    maximum_latency_milliseconds: int
    minimum_quality_score: int
    minimum_qualification: AIProviderQualification
    fallback_allowed: bool

    def __post_init__(self) -> None:
        _require_uuid("route_request_id", self.route_request_id)
        _require_uuid("workspace_id", self.workspace_id)
        _require_aware("evaluated_at", self.evaluated_at)
        _require_exact_enum(
            "minimum_structured_output", self.minimum_structured_output, AIStructuredOutputGuarantee
        )
        _require_bool("tools_required", self.tools_required)
        _require_int("minimum_context_tokens", self.minimum_context_tokens, 1, MAX_CONTEXT_TOKENS)
        _require_frozenset("required_modalities", self.required_modalities, AIModality)
        if not self.required_modalities:
            raise AIRoutingContractError("required_modalities must not be empty")
        _require_exact_enum("data_sensitivity", self.data_sensitivity, DataSensitivity)
        _require_int("maximum_retention_days", self.maximum_retention_days, 0, 3_650)
        _require_regions(self.allowed_regions)
        _require_int(
            "maximum_cost_micro_units", self.maximum_cost_micro_units, 0, MAX_COST_MICRO_UNITS
        )
        _require_int(
            "maximum_latency_milliseconds",
            self.maximum_latency_milliseconds,
            1,
            MAX_LATENCY_MILLISECONDS,
        )
        _require_int("minimum_quality_score", self.minimum_quality_score, 0, 100)
        _require_exact_enum(
            "minimum_qualification", self.minimum_qualification, AIProviderQualification
        )
        _require_bool("fallback_allowed", self.fallback_allowed)


@dataclass(frozen=True, slots=True)
class AIProviderCandidate:
    model: AIModelReference
    profile_version: SemanticVersion
    evidence_observed_at: datetime
    evidence_expires_at: datetime
    qualification: AIProviderQualification
    availability: AIProviderAvailability
    structured_output: AIStructuredOutputGuarantee
    supports_tools: bool
    maximum_context_tokens: int
    modalities: frozenset[AIModality]
    maximum_data_sensitivity: DataSensitivity
    retention_days: int
    region: str
    estimated_cost_micro_units: int
    estimated_latency_milliseconds: int
    quality_score: int
    fallback_only: bool = False

    def __post_init__(self) -> None:
        _require_model(self.model)
        _require_semantic_version(self.profile_version)
        _require_aware("evidence_observed_at", self.evidence_observed_at)
        _require_aware("evidence_expires_at", self.evidence_expires_at)
        if self.evidence_expires_at <= self.evidence_observed_at:
            raise AIRoutingContractError("candidate evidence expiry must follow observation")
        _require_exact_enum("qualification", self.qualification, AIProviderQualification)
        _require_exact_enum("availability", self.availability, AIProviderAvailability)
        _require_exact_enum(
            "structured_output", self.structured_output, AIStructuredOutputGuarantee
        )
        _require_bool("supports_tools", self.supports_tools)
        _require_int("maximum_context_tokens", self.maximum_context_tokens, 1, MAX_CONTEXT_TOKENS)
        _require_frozenset("modalities", self.modalities, AIModality)
        if not self.modalities:
            raise AIRoutingContractError("modalities must not be empty")
        _require_exact_enum(
            "maximum_data_sensitivity", self.maximum_data_sensitivity, DataSensitivity
        )
        _require_int("retention_days", self.retention_days, 0, 3_650)
        _require_region(self.region)
        _require_int(
            "estimated_cost_micro_units", self.estimated_cost_micro_units, 0, MAX_COST_MICRO_UNITS
        )
        _require_int(
            "estimated_latency_milliseconds",
            self.estimated_latency_milliseconds,
            1,
            MAX_LATENCY_MILLISECONDS,
        )
        _require_int("quality_score", self.quality_score, 0, 100)
        _require_bool("fallback_only", self.fallback_only)


@dataclass(frozen=True, slots=True)
class AIProviderCandidateRejection:
    model: AIModelReference
    reasons: tuple[AIRouteRejectionReason, ...]

    def __post_init__(self) -> None:
        _require_model(self.model)
        _require_tuple("reasons", self.reasons, AIRouteRejectionReason)
        if not self.reasons:
            raise AIRoutingContractError("candidate rejection reasons must not be empty")
        if len(set(self.reasons)) != len(self.reasons):
            raise AIRoutingContractError("candidate rejection reasons must be unique")


@dataclass(frozen=True, slots=True)
class AIRouteDecision:
    route_request_id: UUID
    outcome: AIRouteOutcome
    selected_model: AIModelReference | None
    rejections: tuple[AIProviderCandidateRejection, ...] = ()

    def __post_init__(self) -> None:
        _require_uuid("route_request_id", self.route_request_id)
        _require_exact_enum("outcome", self.outcome, AIRouteOutcome)
        if self.selected_model is not None:
            _require_model(self.selected_model)
        _require_tuple("rejections", self.rejections, AIProviderCandidateRejection)
        if (self.outcome is AIRouteOutcome.SELECTED) != (self.selected_model is not None):
            raise AIRoutingContractError("route outcome and selected model must agree")
        rejected_models = [rejection.model for rejection in self.rejections]
        if len(rejected_models) > MAX_ROUTE_CANDIDATES:
            raise AIRoutingContractError("route decision has too many candidate rejections")
        if len(rejected_models) != len(set(rejected_models)):
            raise AIRoutingContractError("rejected candidate models must be unique")
        if self.selected_model in rejected_models:
            raise AIRoutingContractError("selected model cannot also be rejected")


class AICapabilityRouter(Protocol):
    def route(
        self,
        requirements: AIRouteRequirements,
        candidates: tuple[AIProviderCandidate, ...],
    ) -> AIRouteDecision: ...


def _require_uuid(field: str, value: UUID) -> None:
    if type(value) is not UUID:
        raise AIRoutingContractError(f"{field} must be a UUID")
    if value.int == 0:
        raise AIRoutingContractError(f"{field} must not be nil")


def _require_aware(field: str, value: datetime) -> None:
    if type(value) is not datetime:
        raise AIRoutingContractError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise AIRoutingContractError(f"{field} must be timezone-aware")


def _require_semantic_version(value: SemanticVersion) -> None:
    if type(value) is not SemanticVersion:
        raise AIRoutingContractError("profile_version must be a SemanticVersion")
    _require_tuple("profile_version.prerelease", value.prerelease, str)
    _require_tuple("profile_version.build", value.build, str)
    try:
        SemanticVersion.parse(str(value))
    except (TypeError, ValueError) as error:
        raise AIRoutingContractError("profile_version must be a semantic version") from error


def _require_regions(regions: frozenset[str]) -> None:
    _require_frozenset("allowed_regions", regions, str)
    if not regions or len(regions) > 32:
        raise AIRoutingContractError("allowed_regions must contain between 1 and 32 regions")
    for region in regions:
        _require_region(region)


def _require_region(region: str) -> None:
    if type(region) is not str or len(region) > 32 or _REGION.fullmatch(region) is None:
        raise AIRoutingContractError("region must be a bounded lowercase key")


def _require_model(value: AIModelReference) -> None:
    if type(value) is not AIModelReference:
        raise AIRoutingContractError("model must be an AIModelReference")
    if (
        _ROUTING_PROVIDER_ID.fullmatch(value.provider_key) is None
        or _ROUTING_MODEL_ID.fullmatch(value.model_key) is None
        or _UNSAFE_IDENTITY_COMPONENT.search(value.provider_key) is not None
        or _UNSAFE_IDENTITY_COMPONENT.search(value.model_key) is not None
        or _UNSAFE_CREDENTIAL_FRAGMENT.search(value.provider_key) is not None
        or _UNSAFE_CREDENTIAL_FRAGMENT.search(value.model_key) is not None
    ):
        raise AIRoutingContractError("model must use a safe routing identity")


def _require_bool(field: str, value: bool) -> None:
    if type(value) is not bool:
        raise AIRoutingContractError(f"{field} must be a bool")


def _require_int(field: str, value: int, minimum: int, maximum: int) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise AIRoutingContractError(f"{field} is out of bounds")


def _require_exact_enum(field: str, value: object, expected: type[StrEnum]) -> None:
    if type(value) is not expected:
        raise AIRoutingContractError(f"{field} must be a {expected.__name__}")


def _require_frozenset(field: str, value: object, member_type: type[object]) -> None:
    if type(value) is not frozenset:
        raise AIRoutingContractError(f"{field} must be a frozenset")
    if any(type(member) is not member_type for member in value):
        raise AIRoutingContractError(f"{field} contains an invalid member")


def _require_tuple(field: str, value: object, member_type: type[object]) -> None:
    if type(value) is not tuple:
        raise AIRoutingContractError(f"{field} must be a tuple")
    if any(type(member) is not member_type for member in value):
        raise AIRoutingContractError(f"{field} contains an invalid member")
