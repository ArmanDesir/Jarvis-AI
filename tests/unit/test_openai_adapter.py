import json
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import httpx
import openai as sdk
import pytest
from rightjob.contracts.ai import (
    AIMessage,
    AIMessageRole,
    AIModelPurpose,
    AIModelReference,
    AIProviderError,
    AIProviderFailure,
    AIRequest,
    PromptReference,
    StructuredOutputReference,
)
from rightjob.contracts.capabilities import SemanticVersion
from rightjob.executive.intake import INTENT_SCHEMA_JSON, SYSTEM_INSTRUCTION
from rightjob.provider_adapters.openai import OpenAIProviderAdapter

VERSION = SemanticVersion.parse("1.0.0")


class FakeResponses:
    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


class FakeClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


def request(schema: dict[str, object] | None = None) -> AIRequest:
    return AIRequest(
        UUID("21300000-0000-4000-8000-000000000001"),
        UUID("21300000-0000-4000-8000-000000000002"),
        AIModelPurpose.EXECUTIVE_PLANNING,
        AIModelReference("openai", "configured-model"),
        PromptReference("planning.structured-proposal", VERSION),
        StructuredOutputReference("planning.ai-plan-proposal", VERSION),
        json.dumps(schema or {"type": "object"}),
        (
            AIMessage(AIMessageRole.SYSTEM, "system"),
            AIMessage(AIMessageRole.USER, "untrusted data"),
        ),
        2_048,
        30,
    )


def completed(content: str = '{"schema_version":1,"steps":[]}') -> object:
    return SimpleNamespace(
        status="completed",
        output_text=content,
        output=[],
        usage=SimpleNamespace(
            input_tokens=11,
            output_tokens=7,
            total_tokens=18,
            input_tokens_details=SimpleNamespace(cached_tokens=3),
        ),
    )


def test_responses_call_is_non_streaming_tool_free_and_bounded() -> None:
    responses = FakeResponses(completed())
    response = OpenAIProviderAdapter(None, client=FakeClient(responses)).generate(request())

    call = responses.calls[0]
    assert call["stream"] is False
    assert call["background"] is False
    assert call["tools"] == []
    assert call["store"] is False
    assert call["truncation"] == "disabled"
    assert call["max_output_tokens"] == 2_048
    assert call["timeout"] == 30
    assert call["instructions"] == "system"
    assert call["input"] == "untrusted data"
    assert response.usage is not None
    assert response.usage.cached_input_tokens == 3


def test_groq_wire_translation_does_not_change_openai_schema() -> None:
    schema = {
        "anyOf": [
            {"type": "string"},
            {"type": "integer"},
            {"type": "number"},
            {"type": "boolean"},
            {"type": "null"},
        ]
    }
    responses = FakeResponses(completed())
    OpenAIProviderAdapter(None, client=FakeClient(responses)).generate(request(schema))
    assert responses.calls[0]["text"]["format"]["schema"] == schema


def test_openai_intent_keeps_canonical_schema_and_system_instruction() -> None:
    canonical = json.loads(INTENT_SCHEMA_JSON)
    responses = FakeResponses(completed())
    intent_request = replace(
        request(canonical),
        messages=(
            AIMessage(AIMessageRole.SYSTEM, SYSTEM_INSTRUCTION),
            AIMessage(AIMessageRole.USER, "untrusted data"),
        ),
    )

    OpenAIProviderAdapter(None, client=FakeClient(responses)).generate(intent_request)

    call = responses.calls[0]
    assert call["instructions"] == SYSTEM_INSTRUCTION
    assert call["text"]["format"]["schema"] == canonical
    value = canonical["properties"]["planning_input"]["items"]["properties"]["value"]
    assert value["anyOf"] == [
        {"type": "string"},
        {"type": "integer"},
        {"type": "number"},
        {"type": "boolean"},
        {"type": "null"},
    ]


def test_client_construction_disables_retries_and_uses_explicit_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def constructor(**kwargs: object) -> FakeClient:
        captured.update(kwargs)
        return FakeClient(FakeResponses(completed()))

    monkeypatch.setattr(sdk, "OpenAI", constructor)
    OpenAIProviderAdapter("test-only-key")

    assert captured["max_retries"] == 0
    timeout = captured["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 5.0
    assert timeout.read == 30.0
    assert timeout.write == 10.0
    assert timeout.pool == 5.0


@pytest.mark.parametrize(
    ("error", "failure", "http_status"),
    [
        (
            sdk.APITimeoutError(httpx.Request("POST", "https://example.invalid")),
            AIProviderFailure.TIMEOUT,
            None,
        ),
        (
            sdk.APIConnectionError(request=httpx.Request("POST", "https://example.invalid")),
            AIProviderFailure.CONNECTION,
            None,
        ),
        (
            sdk.RateLimitError(
                "limited",
                response=httpx.Response(
                    429, request=httpx.Request("POST", "https://example.invalid")
                ),
                body=None,
            ),
            AIProviderFailure.RATE_LIMIT,
            429,
        ),
        (
            sdk.AuthenticationError(
                "bad auth",
                response=httpx.Response(
                    401, request=httpx.Request("POST", "https://example.invalid")
                ),
                body=None,
            ),
            AIProviderFailure.AUTHENTICATION,
            401,
        ),
        (
            sdk.PermissionDeniedError(
                "denied",
                response=httpx.Response(
                    403, request=httpx.Request("POST", "https://example.invalid")
                ),
                body={"secret": "must-not-escape"},
            ),
            AIProviderFailure.PERMISSION,
            403,
        ),
        (
            sdk.BadRequestError(
                "bad request",
                response=httpx.Response(
                    400, request=httpx.Request("POST", "https://example.invalid")
                ),
                body={"secret": "must-not-escape"},
            ),
            AIProviderFailure.BAD_REQUEST,
            400,
        ),
        (
            sdk.NotFoundError(
                "model",
                response=httpx.Response(
                    404, request=httpx.Request("POST", "https://example.invalid")
                ),
                body=None,
            ),
            AIProviderFailure.UNSUPPORTED_MODEL,
            404,
        ),
        (
            sdk.InternalServerError(
                "internal",
                response=httpx.Response(
                    500, request=httpx.Request("POST", "https://example.invalid")
                ),
                body={"secret": "must-not-escape"},
            ),
            AIProviderFailure.INTERNAL,
            500,
        ),
        *[
            (
                sdk.APIStatusError(
                    "unavailable",
                    response=httpx.Response(
                        status, request=httpx.Request("POST", "https://example.invalid")
                    ),
                    body={"secret": "must-not-escape"},
                ),
                AIProviderFailure.UNAVAILABLE,
                status,
            )
            for status in (502, 503, 504)
        ],
    ],
)
def test_sdk_errors_are_normalized(
    error: Exception, failure: AIProviderFailure, http_status: int | None
) -> None:
    with pytest.raises(AIProviderError) as caught:
        OpenAIProviderAdapter(None, client=FakeClient(FakeResponses(error=error))).generate(
            request()
        )
    assert caught.value.failure is failure
    assert caught.value.http_status == http_status
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert not isinstance(caught.value, sdk.APIError)
    assert "must-not-escape" not in str(caught.value)
    assert "must-not-escape" not in repr(caught.value)


def test_refusal_truncation_and_malformed_output_fail_closed() -> None:
    refusal = SimpleNamespace(
        status="completed",
        output_text="{}",
        output=[SimpleNamespace(content=[SimpleNamespace(type="refusal")])],
        usage=None,
    )
    incomplete = SimpleNamespace(status="incomplete", output_text="{}", output=[], usage=None)
    cases = (
        (refusal, AIProviderFailure.REFUSAL),
        (incomplete, AIProviderFailure.TRUNCATED),
        (completed("not-json"), AIProviderFailure.MALFORMED_RESPONSE),
    )
    for value, failure in cases:
        with pytest.raises(AIProviderError) as caught:
            OpenAIProviderAdapter(None, client=FakeClient(FakeResponses(value))).generate(request())
        assert caught.value.failure is failure


def test_no_client_requires_configuration_without_exposing_a_key() -> None:
    with pytest.raises(AIProviderError) as caught:
        OpenAIProviderAdapter(None)
    assert caught.value.failure is AIProviderFailure.CONFIGURATION
