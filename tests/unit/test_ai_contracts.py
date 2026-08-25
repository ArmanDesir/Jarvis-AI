import json
from uuid import UUID

import pytest
from rightjob.contracts.ai import (
    AIFinishStatus,
    AIMessage,
    AIMessageRole,
    AIModelPurpose,
    AIModelReference,
    AIProviderDiagnosticReason,
    AIProviderDiagnosticStage,
    AIProviderError,
    AIProviderFailure,
    AIProviderFailureKind,
    AIRequest,
    AIResponse,
    AIUsage,
    PromptReference,
    StructuredOutputReference,
)
from rightjob.contracts.capabilities import SemanticVersion

VERSION = SemanticVersion.parse("1.0.0")
ID = UUID("21300000-0000-4000-8000-000000000001")


def request(**changes: object) -> AIRequest:
    values: dict[str, object] = {
        "invocation_id": ID,
        "correlation_id": UUID("21300000-0000-4000-8000-000000000002"),
        "purpose": AIModelPurpose.EXECUTIVE_PLANNING,
        "model": AIModelReference("openai", "configured-model"),
        "prompt": PromptReference("planning.structured-proposal", VERSION),
        "structured_output": StructuredOutputReference("planning.ai-plan-proposal", VERSION),
        "schema_json": json.dumps({"type": "object"}),
        "messages": (AIMessage(AIMessageRole.USER, "bounded input"),),
        "maximum_output_tokens": 2_048,
        "timeout_seconds": 30,
    }
    values.update(changes)
    return AIRequest(**values)  # type: ignore[arg-type]


def test_provider_contracts_are_bounded_and_immutable() -> None:
    value = request()

    assert value.encoded_bytes <= 65_536
    with pytest.raises(AttributeError):
        value.timeout_seconds = 1  # type: ignore[misc]
    with pytest.raises(ValueError, match="encoded byte bound"):
        request(messages=(AIMessage(AIMessageRole.USER, "x" * 65_536),))
    with pytest.raises(ValueError, match="between 1 and 30"):
        request(timeout_seconds=31)


def test_usage_is_coherent_and_response_is_bounded() -> None:
    usage = AIUsage(10, 4, 14, 2)
    assert usage.total_tokens == 14
    with pytest.raises(ValueError, match="cannot be less"):
        AIUsage(10, 4, 13)
    with pytest.raises(AIProviderError) as caught:
        AIResponse(
            ID,
            UUID("21300000-0000-4000-8000-000000000002"),
            AIModelReference("openai", "configured-model"),
            AIFinishStatus.COMPLETED,
            "x" * 65_537,
        )
    assert caught.value.failure is AIProviderFailure.OVERSIZED_RESPONSE


def test_failure_retryability_is_explicit() -> None:
    assert AIProviderFailure.TIMEOUT.retryable is True
    assert AIProviderFailure.RATE_LIMIT.retryable is True
    assert AIProviderFailure.AUTHENTICATION.retryable is False
    assert AIProviderFailure.TIMEOUT.kind is AIProviderFailureKind.TRANSIENT
    assert AIProviderFailure.AUTHENTICATION.kind is AIProviderFailureKind.CONFIGURATION
    assert AIProviderFailure.PERMISSION.kind is AIProviderFailureKind.CONFIGURATION
    assert AIProviderFailure.BAD_REQUEST.kind is AIProviderFailureKind.INVALID_OUTPUT
    assert AIProviderFailure.REFUSAL.kind is AIProviderFailureKind.REJECTED_OUTPUT
    assert AIProviderFailure.SCHEMA_VIOLATION.kind is AIProviderFailureKind.INVALID_OUTPUT
    assert AIProviderError(AIProviderFailure.CONNECTION).retryable is True


def test_provider_error_retains_only_bounded_diagnostics() -> None:
    error = AIProviderError(
        AIProviderFailure.RATE_LIMIT,
        429,
        diagnostic_stage=AIProviderDiagnosticStage.HTTP,
        diagnostic_reason=AIProviderDiagnosticReason.HTTP_STATUS,
    )

    assert error.http_status == 429
    assert error.diagnostic_stage is AIProviderDiagnosticStage.HTTP
    assert error.diagnostic_reason is AIProviderDiagnosticReason.HTTP_STATUS
    assert error.finish_status is None
    assert error.provider_error_type is None
    assert str(error) == "rate_limit"
    assert "secret" not in repr(error)
    with pytest.raises(ValueError, match="between 100 and 599"):
        AIProviderError(AIProviderFailure.BAD_REQUEST, 99)
    with pytest.raises(ValueError, match="between 100 and 599"):
        AIProviderError(AIProviderFailure.BAD_REQUEST, 600)


def test_provider_error_type_is_identifier_bounded() -> None:
    allowed = AIProviderError(
        AIProviderFailure.BAD_REQUEST,
        400,
        provider_error_type="invalid_request_error",
    )
    assert allowed.provider_error_type == "invalid_request_error"

    for invalid in ("contains space", "../path", "x" * 65, "", "érror"):
        assert (
            AIProviderError(
                AIProviderFailure.BAD_REQUEST,
                400,
                provider_error_type=invalid,
            ).provider_error_type
            is None
        )
