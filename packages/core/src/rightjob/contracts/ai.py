"""Published provider-neutral contracts for untrusted AI planning output."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from rightjob.contracts.capabilities import SemanticVersion
from rightjob.contracts.departments import WorkCategory
from rightjob.contracts.planning import StructuredInput, SyntheticStepObjective

_KEY = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_PROVIDER_ERROR_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$", re.ASCII)
MAX_AI_PAYLOAD_BYTES = 65_536
MAX_AI_OUTPUT_TOKENS = 8_192


class AIMessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"


class AIModelPurpose(StrEnum):
    EXECUTIVE_PLANNING = "executive_planning"


class AIFinishStatus(StrEnum):
    COMPLETED = "completed"
    REFUSED = "refused"
    TRUNCATED = "truncated"


class AIProviderFailureKind(StrEnum):
    TRANSIENT = "transient"
    CONFIGURATION = "configuration"
    REJECTED_OUTPUT = "rejected_output"
    INVALID_OUTPUT = "invalid_output"


class AIProviderFailure(StrEnum):
    TIMEOUT = "timeout"
    CONNECTION = "connection_failure"
    RATE_LIMIT = "rate_limit"
    UNAVAILABLE = "provider_unavailable"
    INTERNAL = "provider_internal_failure"
    AUTHENTICATION = "authentication_failure"
    PERMISSION = "permission_failure"
    BAD_REQUEST = "bad_request"
    CONFIGURATION = "missing_configuration"
    UNSUPPORTED_MODEL = "unsupported_model"
    REFUSAL = "refusal"
    TRUNCATED = "truncated_response"
    MALFORMED_RESPONSE = "malformed_structured_response"
    SCHEMA_VIOLATION = "schema_violation"
    OVERSIZED_RESPONSE = "oversized_response"
    UNEXPECTED_RESPONSE = "unexpected_provider_response"

    @property
    def retryable(self) -> bool:
        return self in {
            AIProviderFailure.TIMEOUT,
            AIProviderFailure.CONNECTION,
            AIProviderFailure.RATE_LIMIT,
            AIProviderFailure.UNAVAILABLE,
            AIProviderFailure.INTERNAL,
        }

    @property
    def kind(self) -> AIProviderFailureKind:
        if self.retryable:
            return AIProviderFailureKind.TRANSIENT
        if self in {
            AIProviderFailure.AUTHENTICATION,
            AIProviderFailure.PERMISSION,
            AIProviderFailure.CONFIGURATION,
            AIProviderFailure.UNSUPPORTED_MODEL,
        }:
            return AIProviderFailureKind.CONFIGURATION
        if self is AIProviderFailure.REFUSAL:
            return AIProviderFailureKind.REJECTED_OUTPUT
        return AIProviderFailureKind.INVALID_OUTPUT


class AIProviderDiagnosticStage(StrEnum):
    HTTP = "http"
    RESPONSE_ENVELOPE = "response_envelope"
    FINISH_STATUS = "finish_status"
    CONTENT = "content"
    JSON_PARSE = "json_parse"
    JSON_SHAPE = "json_shape"
    CANONICAL_DECODE = "canonical_decode"


class AIProviderDiagnosticReason(StrEnum):
    HTTP_STATUS = "http_status"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    MISSING_CHOICES = "missing_choices"
    INVALID_CHOICES = "invalid_choices"
    MISSING_MESSAGE = "missing_message"
    INVALID_MESSAGE = "invalid_message"
    REFUSAL = "refusal"
    TRUNCATION = "truncation"
    UNEXPECTED_FINISH = "unexpected_finish"
    MISSING_CONTENT = "missing_content"
    INVALID_CONTENT = "invalid_content"
    OVERSIZED_RESPONSE = "oversized_response"
    JSON_PARSE_FAILED = "json_parse_failed"
    JSON_NOT_OBJECT = "json_not_object"
    EXACT_FIELDS_MISMATCH = "exact_fields_mismatch"
    INVALID_SCHEMA_VERSION = "invalid_schema_version"
    INVALID_OUTCOME = "invalid_outcome"
    INVALID_REASON = "invalid_reason"
    INVALID_PLANNING_GOAL = "invalid_planning_goal"
    INVALID_PLANNING_INPUT = "invalid_planning_input"
    INVALID_CLARIFICATION = "invalid_clarification"
    INVALID_UNSUPPORTED_REASON = "invalid_unsupported_reason"
    OUTCOME_FIELD_INVARIANT = "outcome_field_invariant"
    INVALID_PLANNING_PROPOSAL = "invalid_planning_proposal"
    INVALID_USAGE = "invalid_usage"
    PROVENANCE_MISMATCH = "provenance_mismatch"
    SCHEMA_TRANSLATION = "schema_translation"


class AIProviderError(RuntimeError):
    """A bounded provider failure with no vendor payload or secret material."""

    def __init__(
        self,
        failure: AIProviderFailure,
        http_status: int | None = None,
        *,
        diagnostic_stage: AIProviderDiagnosticStage | None = None,
        diagnostic_reason: AIProviderDiagnosticReason | None = None,
        finish_status: AIFinishStatus | None = None,
        provider_error_type: str | None = None,
    ) -> None:
        if http_status is not None and not 100 <= http_status <= 599:
            raise ValueError("http_status must be between 100 and 599")
        self.failure = failure
        self.http_status = http_status
        self.diagnostic_stage = diagnostic_stage
        self.diagnostic_reason = diagnostic_reason
        self.finish_status = finish_status
        self.provider_error_type = (
            provider_error_type
            if isinstance(provider_error_type, str)
            and _PROVIDER_ERROR_TYPE.fullmatch(provider_error_type) is not None
            else None
        )
        super().__init__(failure.value)

    @property
    def retryable(self) -> bool:
        return self.failure.retryable

    @property
    def kind(self) -> AIProviderFailureKind:
        return self.failure.kind


@dataclass(frozen=True, slots=True)
class AIModelReference:
    provider_key: str
    model_key: str

    def __post_init__(self) -> None:
        _require_key("provider_key", self.provider_key)
        _require_text("model_key", self.model_key, 200)


@dataclass(frozen=True, slots=True)
class PromptReference:
    prompt_key: str
    semantic_version: SemanticVersion

    def __post_init__(self) -> None:
        _require_key("prompt_key", self.prompt_key)


@dataclass(frozen=True, slots=True)
class StructuredOutputReference:
    schema_key: str
    semantic_version: SemanticVersion

    def __post_init__(self) -> None:
        _require_key("schema_key", self.schema_key)


@dataclass(frozen=True, slots=True)
class AIMessage:
    role: AIMessageRole
    content: str

    def __post_init__(self) -> None:
        _require_text("message content", self.content, MAX_AI_PAYLOAD_BYTES)


@dataclass(frozen=True, slots=True)
class AIUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int = 0

    def __post_init__(self) -> None:
        if (
            min(
                self.input_tokens,
                self.output_tokens,
                self.total_tokens,
                self.cached_input_tokens,
            )
            < 0
        ):
            raise ValueError("AI usage values must not be negative")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached input tokens cannot exceed input tokens")
        if self.total_tokens < self.input_tokens + self.output_tokens:
            raise ValueError("total tokens cannot be less than input and output tokens")


@dataclass(frozen=True, slots=True)
class AIRequest:
    invocation_id: UUID
    correlation_id: UUID
    purpose: AIModelPurpose
    model: AIModelReference
    prompt: PromptReference
    structured_output: StructuredOutputReference
    schema_json: str
    messages: tuple[AIMessage, ...]
    maximum_output_tokens: int
    timeout_seconds: int

    def __post_init__(self) -> None:
        _require_ids(self.invocation_id, self.correlation_id)
        if not self.messages:
            raise ValueError("AI request messages must not be empty")
        if not 1 <= self.maximum_output_tokens <= MAX_AI_OUTPUT_TOKENS:
            raise ValueError("maximum output tokens are outside the accepted bound")
        if not 1 <= self.timeout_seconds <= 30:
            raise ValueError("AI timeout must be between 1 and 30 seconds")
        try:
            schema = json.loads(self.schema_json)
        except json.JSONDecodeError as error:
            raise ValueError("structured output schema must be valid JSON") from error
        if not isinstance(schema, dict):
            raise ValueError("structured output schema must be a JSON object")
        if self.encoded_bytes > MAX_AI_PAYLOAD_BYTES:
            raise ValueError("AI request exceeds the encoded byte bound")

    @property
    def encoded_bytes(self) -> int:
        value = {
            "invocation_id": str(self.invocation_id),
            "correlation_id": str(self.correlation_id),
            "purpose": self.purpose.value,
            "model": [self.model.provider_key, self.model.model_key],
            "prompt": [self.prompt.prompt_key, str(self.prompt.semantic_version)],
            "structured_output": [
                self.structured_output.schema_key,
                str(self.structured_output.semantic_version),
            ],
            "schema": self.schema_json,
            "messages": [[item.role.value, item.content] for item in self.messages],
            "maximum_output_tokens": self.maximum_output_tokens,
            "timeout_seconds": self.timeout_seconds,
        }
        return len(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())


@dataclass(frozen=True, slots=True)
class AIResponse:
    invocation_id: UUID
    correlation_id: UUID
    model: AIModelReference
    finish_status: AIFinishStatus
    content: str
    usage: AIUsage | None = None

    def __post_init__(self) -> None:
        _require_ids(self.invocation_id, self.correlation_id)
        if len(self.content.encode()) > MAX_AI_PAYLOAD_BYTES:
            raise AIProviderError(AIProviderFailure.OVERSIZED_RESPONSE)


@dataclass(frozen=True, slots=True)
class AIPlanProposalStep:
    sequence: int
    objective: SyntheticStepObjective
    work_category: WorkCategory
    department_key: str
    department_semantic_version: SemanticVersion
    capability_key: str
    capability_semantic_version: SemanticVersion
    structured_input: StructuredInput
    dependency_sequences: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("AI proposal sequence must not be negative")
        _require_key("department_key", self.department_key)
        _require_key("capability_key", self.capability_key)
        if len(set(self.dependency_sequences)) != len(self.dependency_sequences):
            raise ValueError("AI proposal dependency sequences must be unique")
        if any(item < 0 for item in self.dependency_sequences):
            raise ValueError("AI proposal dependency sequences must not be negative")


@dataclass(frozen=True, slots=True)
class AIPlanProposal:
    schema_version: int
    steps: tuple[AIPlanProposalStep, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported AI planning schema version")
        if not 1 <= len(self.steps) <= 16:
            raise ValueError("AI proposal must contain between 1 and 16 steps")


class AIProvider(Protocol):
    def generate(self, request: AIRequest) -> AIResponse: ...


def _require_ids(*values: UUID) -> None:
    if any(value.int == 0 for value in values):
        raise ValueError("AI identifiers must not be nil")


def _require_key(name: str, value: str) -> None:
    if _KEY.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical")


def _require_text(name: str, value: str, maximum: int) -> None:
    if not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be nonblank and at most {maximum} characters")
