import json
from copy import deepcopy
from uuid import UUID

import httpx
import pytest
from rightjob.contracts.ai import (
    MAX_AI_PAYLOAD_BYTES,
    AIMessage,
    AIMessageRole,
    AIModelPurpose,
    AIModelReference,
    AIProviderDiagnosticReason,
    AIProviderDiagnosticStage,
    AIProviderError,
    AIProviderFailure,
    AIRequest,
    PromptReference,
    StructuredOutputReference,
)
from rightjob.contracts.capabilities import SemanticVersion
from rightjob.executive.intake import INTENT_SCHEMA_JSON
from rightjob.provider_adapters.groq import GroqProviderAdapter
from rightjob.provider_adapters.groq import _wire_schema as wire_schema

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
VERSION = SemanticVersion.parse("1.0.0")
KEY = "test-key"


def request(
    schema: dict[str, object] | None = None,
    *,
    prompt_key: str = "planning.structured-proposal",
) -> AIRequest:
    value = schema or {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"const": 1, "type": "integer"},
            "nested": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "value": {
                            "anyOf": [
                                {"type": "string"},
                                {"const": None, "type": "null"},
                            ]
                        }
                    },
                    "required": ["value"],
                },
            },
        },
        "required": ["schema_version", "nested"],
    }
    return AIRequest(
        UUID("21700000-0000-4000-8000-000000000001"),
        UUID("21700000-0000-4000-8000-000000000002"),
        AIModelPurpose.EXECUTIVE_PLANNING,
        AIModelReference("groq", "openai/gpt-oss-20b"),
        PromptReference(prompt_key, VERSION),
        StructuredOutputReference("planning.ai-plan-proposal", VERSION),
        json.dumps(value, separators=(",", ":"), sort_keys=True),
        (
            AIMessage(AIMessageRole.SYSTEM, "system"),
            AIMessage(AIMessageRole.USER, "untrusted data"),
        ),
        2_048,
        30,
    )


def completed(content: str = '{"schema_version":1,"nested":[]}') -> dict[str, object]:
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": content, "role": "assistant"},
            }
        ],
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
            "prompt_tokens_details": {"cached_tokens": 3},
        },
    }


def adapter(handler: httpx.MockTransport) -> GroqProviderAdapter:
    return GroqProviderAdapter(KEY, client=httpx.Client(transport=handler))


def test_request_is_exact_bounded_non_streaming_strict_and_tool_free() -> None:
    calls: list[httpx.Request] = []

    def handle(item: httpx.Request) -> httpx.Response:
        calls.append(item)
        return httpx.Response(200, json=completed())

    canonical = json.loads(request().schema_json)
    original = deepcopy(canonical)
    response = adapter(httpx.MockTransport(handle)).generate(request(canonical))

    assert len(calls) == 1
    sent = calls[0]
    assert str(sent.url) == ENDPOINT
    assert sent.method == "POST"
    assert sent.headers["authorization"] == f"Bearer {KEY}"
    assert sent.extensions["timeout"]["read"] == 30
    body = json.loads(sent.content)
    assert body["model"] == "openai/gpt-oss-20b"
    assert body["messages"] == [
        {"role": "system", "content": "Return only the requested synthetic JSON object."},
        {"role": "user", "content": "untrusted data"},
    ]
    assert request().messages[0].content == "system"
    assert request().messages[1].content == "untrusted data"
    assert body["stream"] is False
    assert body["n"] == 1
    assert body["temperature"] == 0
    assert "tool_choice" not in body
    assert "tools" not in body
    assert "functions" not in body
    assert body["max_completion_tokens"] == 2_048
    output = body["response_format"]
    assert output["type"] == "json_schema"
    assert output["json_schema"]["strict"] is True
    wire = output["json_schema"]["schema"]
    assert wire["properties"]["schema_version"] == {"enum": [1], "type": "integer"}
    assert wire["properties"]["nested"]["items"]["properties"]["value"]["anyOf"][1] == {
        "enum": [None],
        "type": "null",
    }
    assert wire["required"] == ["schema_version", "nested"]
    assert wire["additionalProperties"] is False
    assert canonical == original
    assert request(canonical).schema_json == request(original).schema_json
    assert response.model.provider_key == "groq"
    assert response.model.model_key == "openai/gpt-oss-20b"
    assert response.invocation_id == request().invocation_id
    assert response.correlation_id == request().correlation_id
    assert response.usage is not None
    assert response.usage.cached_input_tokens == 3


def test_wire_schema_rewrites_only_bare_primitive_anyof_without_mutation() -> None:
    canonical = json.loads(INTENT_SCHEMA_JSON)
    original = deepcopy(canonical)

    wire = wire_schema(canonical)

    value = wire["properties"]["planning_input"]["items"]["properties"]["value"]
    assert value == {
        "anyOf": [
            {"type": "string"},
            {"type": "number"},
            {"type": "boolean"},
            {"type": "null"},
        ]
    }
    assert wire["required"] == canonical["required"]
    assert wire["additionalProperties"] is False
    assert wire["properties"]["planning_input"]["items"]["required"] == ["key", "value"]
    assert wire["properties"]["planning_input"]["items"]["additionalProperties"] is False
    assert canonical == original
    assert json.dumps(canonical, separators=(",", ":"), sort_keys=True) == INTENT_SCHEMA_JSON


def test_groq_system_instruction_substitution_is_limited_to_runtime_prompts() -> None:
    sent: list[httpx.Request] = []

    def handle(item: httpx.Request) -> httpx.Response:
        sent.append(item)
        return httpx.Response(200, json=completed())

    adapter(httpx.MockTransport(handle)).generate(request(prompt_key="unrelated.prompt"))
    body = json.loads(sent[0].content)
    assert body["messages"][0] == {"role": "system", "content": "system"}


def test_intent_wire_schema_guides_canonical_invariants_without_mutation() -> None:
    sent: list[httpx.Request] = []
    canonical = json.loads(INTENT_SCHEMA_JSON)
    original = deepcopy(canonical)

    def handle(item: httpx.Request) -> httpx.Response:
        sent.append(item)
        return httpx.Response(200, json=completed())

    adapter(httpx.MockTransport(handle)).generate(
        request(canonical, prompt_key="executive.intent-classification")
    )
    wire = json.loads(sent[0].content)["response_format"]["json_schema"]["schema"]
    guidance = wire["description"]
    assert "planning_ready uses reason ready" in guidance
    assert "clarification_required uses reason missing_information" in guidance
    assert "unsupported uses reason unsupported_request" in guidance
    assert wire["required"] == canonical["required"]
    assert wire["additionalProperties"] is False
    assert canonical == original
    assert json.dumps(canonical, separators=(",", ":"), sort_keys=True) == INTENT_SCHEMA_JSON


def test_wire_schema_preserves_constrained_or_mixed_anyof() -> None:
    schema = {
        "anyOf": [
            {"type": "string", "enum": ["bounded"]},
            {"type": "object", "properties": {}, "additionalProperties": False},
        ]
    }
    assert wire_schema(schema) == schema


@pytest.mark.parametrize("value", ["text", 1, 1.5, True, None])
def test_wire_schema_redundant_integer_removal_preserves_json_values(value: object) -> None:
    canonical = {
        "anyOf": [
            {"type": "string"},
            {"type": "integer"},
            {"type": "number"},
            {"type": "boolean"},
            {"type": "null"},
        ]
    }
    assert _matches_primitive_union(value, canonical)
    assert _matches_primitive_union(value, wire_schema(canonical))


@pytest.mark.parametrize(
    "schema",
    [
        {"anyOf": [{"type": "integer", "minimum": 0}, {"type": "number"}]},
        {"anyOf": [{"type": "integer"}, {"type": "number", "maximum": 1}]},
    ],
)
def test_wire_schema_does_not_collapse_constrained_numeric_branches(
    schema: dict[str, object],
) -> None:
    assert wire_schema(schema) == schema


def _matches_primitive_union(value: object, schema: dict[str, object]) -> bool:
    branches = schema["anyOf"]
    assert isinstance(branches, list)
    json_types = {
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    return any(
        isinstance(branch, dict)
        and isinstance(branch.get("type"), str)
        and json_types.get(branch["type"], False)
        for branch in branches
    )


def test_generate_makes_one_request_and_httpx_transport_has_no_retry() -> None:
    count = 0

    def handle(item: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(500, content=b"must-not-escape")

    with pytest.raises(AIProviderError):
        adapter(httpx.MockTransport(handle)).generate(request())
    assert count == 1


@pytest.mark.parametrize(
    ("status", "failure"),
    [
        (400, AIProviderFailure.BAD_REQUEST),
        (401, AIProviderFailure.AUTHENTICATION),
        (403, AIProviderFailure.PERMISSION),
        (404, AIProviderFailure.UNSUPPORTED_MODEL),
        (413, AIProviderFailure.BAD_REQUEST),
        (422, AIProviderFailure.BAD_REQUEST),
        (429, AIProviderFailure.RATE_LIMIT),
        (500, AIProviderFailure.INTERNAL),
        (502, AIProviderFailure.UNAVAILABLE),
        (503, AIProviderFailure.UNAVAILABLE),
        (504, AIProviderFailure.UNAVAILABLE),
    ],
)
def test_http_errors_are_safe_and_bounded(status: int, failure: AIProviderFailure) -> None:
    body_marker = "provider-body-must-not-escape"
    transport = httpx.MockTransport(
        lambda item: httpx.Response(status, content=body_marker.encode(), request=item)
    )
    with pytest.raises(AIProviderError) as caught:
        adapter(transport).generate(request())
    assert caught.value.failure is failure
    assert caught.value.http_status == status
    assert caught.value.diagnostic_stage is AIProviderDiagnosticStage.HTTP
    assert caught.value.diagnostic_reason is AIProviderDiagnosticReason.HTTP_STATUS
    assert caught.value.provider_error_type is None
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert body_marker not in str(caught.value)
    assert body_marker not in repr(caught.value)
    assert KEY not in str(caught.value)
    assert KEY not in repr(caught.value)


def test_http_error_extracts_only_documented_bounded_type() -> None:
    body_marker = "provider-message-body-must-not-escape"
    response = httpx.Response(
        400,
        json={
            "error": {
                "message": body_marker,
                "type": "invalid_request_error",
                "code": "undocumented_code",
                "param": "response_format.schema",
            }
        },
    )

    with pytest.raises(AIProviderError) as caught:
        adapter(httpx.MockTransport(lambda item: response)).generate(request())

    error = caught.value
    assert error.failure is AIProviderFailure.BAD_REQUEST
    assert error.http_status == 400
    assert error.provider_error_type == "invalid_request_error"
    assert not hasattr(error, "provider_error_code")
    assert not hasattr(error, "provider_error_param")
    assert not hasattr(error, "response")
    assert body_marker not in str(error)
    assert body_marker not in repr(error)
    assert KEY not in str(error)
    assert KEY not in repr(error)
    assert error.__cause__ is None
    assert error.__context__ is None


@pytest.mark.parametrize(
    ("code", "param"),
    [
        ("invalid code!", "bad param!"),
        ("x" * 65, "x" * 129),
    ],
)
def test_undocumented_code_and_param_are_always_discarded(code: str, param: str) -> None:
    response = httpx.Response(
        400,
        json={
            "error": {
                "message": "discarded",
                "type": "invalid_request_error",
                "code": code,
                "param": param,
            }
        },
    )
    with pytest.raises(AIProviderError) as caught:
        adapter(httpx.MockTransport(lambda item: response)).generate(request())
    assert caught.value.provider_error_type == "invalid_request_error"
    assert not hasattr(caught.value, "provider_error_code")
    assert not hasattr(caught.value, "provider_error_param")


@pytest.mark.parametrize(
    "content",
    [
        b"not-json",
        b"[]",
        b"{}",
        b'{"error":null}',
        b'{"error":{"message":"discarded"}}',
    ],
)
def test_http_error_without_documented_type_keeps_none(content: bytes) -> None:
    response = httpx.Response(400, content=content)
    with pytest.raises(AIProviderError) as caught:
        adapter(httpx.MockTransport(lambda item: response)).generate(request())
    assert caught.value.failure is AIProviderFailure.BAD_REQUEST
    assert caught.value.provider_error_type is None
    assert content.decode(errors="ignore") not in str(caught.value)
    assert content.decode(errors="ignore") not in repr(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "value",
    [
        "invalid type",
        "../invalid",
        "x" * 65,
        "",
        123,
    ],
)
def test_http_error_discards_invalid_or_oversized_type(value: object) -> None:
    response = httpx.Response(400, json={"error": {"message": "discarded", "type": value}})
    with pytest.raises(AIProviderError) as caught:
        adapter(httpx.MockTransport(lambda item: response)).generate(request())
    assert caught.value.provider_error_type is None


def test_oversized_http_error_body_is_not_parsed_or_retained() -> None:
    marker = "oversized-provider-body-must-not-escape"
    response = httpx.Response(
        400,
        json={
            "error": {
                "type": "invalid_request_error",
                "message": marker + "x" * MAX_AI_PAYLOAD_BYTES,
            }
        },
    )
    with pytest.raises(AIProviderError) as caught:
        adapter(httpx.MockTransport(lambda item: response)).generate(request())
    assert caught.value.failure is AIProviderFailure.BAD_REQUEST
    assert caught.value.provider_error_type is None
    assert marker not in str(caught.value)
    assert marker not in repr(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    ("error", "failure"),
    [
        (
            httpx.ReadTimeout("raw-timeout-secret", request=httpx.Request("POST", ENDPOINT)),
            AIProviderFailure.TIMEOUT,
        ),
        (
            httpx.ConnectError("raw-connection-secret", request=httpx.Request("POST", ENDPOINT)),
            AIProviderFailure.CONNECTION,
        ),
    ],
)
def test_transport_errors_are_normalized_without_raw_exception(
    error: Exception, failure: AIProviderFailure
) -> None:
    def handle(item: httpx.Request) -> httpx.Response:
        raise error

    with pytest.raises(AIProviderError) as caught:
        adapter(httpx.MockTransport(handle)).generate(request())
    assert caught.value.failure is failure
    assert caught.value.diagnostic_stage is AIProviderDiagnosticStage.HTTP
    assert caught.value.diagnostic_reason in {
        AIProviderDiagnosticReason.TIMEOUT,
        AIProviderDiagnosticReason.CONNECTION,
    }
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "raw-" not in str(caught.value)
    assert "raw-" not in repr(caught.value)


@pytest.mark.parametrize(
    ("response", "failure", "stage", "reason"),
    [
        (
            httpx.Response(200, content=b"not-json"),
            AIProviderFailure.MALFORMED_RESPONSE,
            AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
            AIProviderDiagnosticReason.INVALID_MESSAGE,
        ),
        (
            httpx.Response(200, json=[]),
            AIProviderFailure.MALFORMED_RESPONSE,
            AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
            AIProviderDiagnosticReason.INVALID_MESSAGE,
        ),
        (
            httpx.Response(200, json={}),
            AIProviderFailure.UNEXPECTED_RESPONSE,
            AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
            AIProviderDiagnosticReason.MISSING_CHOICES,
        ),
        (
            httpx.Response(200, json={"choices": []}),
            AIProviderFailure.UNEXPECTED_RESPONSE,
            AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
            AIProviderDiagnosticReason.INVALID_CHOICES,
        ),
        (
            httpx.Response(200, json={"choices": [{"finish_reason": "stop"}]}),
            AIProviderFailure.UNEXPECTED_RESPONSE,
            AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
            AIProviderDiagnosticReason.MISSING_MESSAGE,
        ),
        (
            httpx.Response(
                200,
                json={"choices": [{"finish_reason": "stop", "message": []}]},
            ),
            AIProviderFailure.UNEXPECTED_RESPONSE,
            AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
            AIProviderDiagnosticReason.INVALID_MESSAGE,
        ),
        (
            httpx.Response(
                200,
                json={"choices": [{"finish_reason": "stop", "message": {}}]},
            ),
            AIProviderFailure.MALFORMED_RESPONSE,
            AIProviderDiagnosticStage.CONTENT,
            AIProviderDiagnosticReason.MISSING_CONTENT,
        ),
        (
            httpx.Response(
                200,
                json={"choices": [{"finish_reason": "stop", "message": {"content": ""}}]},
            ),
            AIProviderFailure.MALFORMED_RESPONSE,
            AIProviderDiagnosticStage.CONTENT,
            AIProviderDiagnosticReason.INVALID_CONTENT,
        ),
        (
            httpx.Response(
                200,
                json={"choices": [{"finish_reason": "stop", "message": {"content": {}}}]},
            ),
            AIProviderFailure.MALFORMED_RESPONSE,
            AIProviderDiagnosticStage.CONTENT,
            AIProviderDiagnosticReason.INVALID_CONTENT,
        ),
        (
            httpx.Response(
                200,
                json={"choices": [{"finish_reason": "stop", "message": {"content": "{"}}]},
            ),
            AIProviderFailure.MALFORMED_RESPONSE,
            AIProviderDiagnosticStage.JSON_PARSE,
            AIProviderDiagnosticReason.JSON_PARSE_FAILED,
        ),
        (
            httpx.Response(
                200,
                json={"choices": [{"finish_reason": "stop", "message": {"content": "[]"}}]},
            ),
            AIProviderFailure.MALFORMED_RESPONSE,
            AIProviderDiagnosticStage.JSON_SHAPE,
            AIProviderDiagnosticReason.JSON_NOT_OBJECT,
        ),
        (
            httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": "{}", "refusal": "refused"},
                        }
                    ]
                },
            ),
            AIProviderFailure.REFUSAL,
            AIProviderDiagnosticStage.FINISH_STATUS,
            AIProviderDiagnosticReason.REFUSAL,
        ),
        (
            httpx.Response(
                200,
                json={"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
            ),
            AIProviderFailure.TRUNCATED,
            AIProviderDiagnosticStage.FINISH_STATUS,
            AIProviderDiagnosticReason.TRUNCATION,
        ),
    ],
)
def test_invalid_responses_fail_closed(
    response: httpx.Response,
    failure: AIProviderFailure,
    stage: AIProviderDiagnosticStage,
    reason: AIProviderDiagnosticReason,
) -> None:
    with pytest.raises(AIProviderError) as caught:
        adapter(httpx.MockTransport(lambda item: response)).generate(request())
    assert caught.value.failure is failure
    assert caught.value.diagnostic_stage is stage
    assert caught.value.diagnostic_reason is reason
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_oversized_response_is_rejected() -> None:
    response = httpx.Response(200, content=b"x" * (MAX_AI_PAYLOAD_BYTES + 1))
    with pytest.raises(AIProviderError) as caught:
        adapter(httpx.MockTransport(lambda item: response)).generate(request())
    assert caught.value.failure is AIProviderFailure.OVERSIZED_RESPONSE
    assert caught.value.diagnostic_reason is AIProviderDiagnosticReason.OVERSIZED_RESPONSE


def test_conflicting_const_and_enum_fails_without_request() -> None:
    calls = 0

    def handle(item: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=completed())

    with pytest.raises(AIProviderError) as caught:
        adapter(httpx.MockTransport(handle)).generate(
            request({"type": "object", "const": {}, "enum": [{}]})
        )
    assert caught.value.failure is AIProviderFailure.SCHEMA_VIOLATION
    assert calls == 0


def test_wrong_provider_or_model_and_missing_key_fail_closed() -> None:
    with pytest.raises(AIProviderError) as caught:
        GroqProviderAdapter(None)
    assert caught.value.failure is AIProviderFailure.CONFIGURATION
    assert KEY not in repr(GroqProviderAdapter(KEY, client=httpx.Client()))

    value = request()
    wrong = AIRequest(
        value.invocation_id,
        value.correlation_id,
        value.purpose,
        AIModelReference("openai", "openai/gpt-oss-20b"),
        value.prompt,
        value.structured_output,
        value.schema_json,
        value.messages,
        value.maximum_output_tokens,
        value.timeout_seconds,
    )
    with pytest.raises(AIProviderError) as caught:
        GroqProviderAdapter(KEY, client=httpx.Client()).generate(wrong)
    assert caught.value.failure is AIProviderFailure.UNSUPPORTED_MODEL
