"""Groq Chat Completions adapter; HTTP details remain inside infrastructure."""

from __future__ import annotations

import json
import re
from contextlib import suppress
from typing import Any, Protocol

import httpx

from rightjob.contracts.ai import (
    MAX_AI_PAYLOAD_BYTES,
    AIFinishStatus,
    AIProviderDiagnosticReason,
    AIProviderDiagnosticStage,
    AIProviderError,
    AIProviderFailure,
    AIRequest,
    AIResponse,
    AIUsage,
)

_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "openai/gpt-oss-20b"
_STRUCTURED_SYSTEM_INSTRUCTION = "Return only the requested synthetic JSON object."
_STRUCTURED_PROMPTS = frozenset({"executive.intent-classification", "planning.structured-proposal"})
_PROVIDER_ERROR_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$", re.ASCII)


class _Client(Protocol):
    def post(self, url: str, **kwargs: object) -> httpx.Response: ...


class GroqProviderAdapter:
    def __init__(self, api_key: str | None, *, client: _Client | None = None) -> None:
        if not api_key:
            raise AIProviderError(AIProviderFailure.CONFIGURATION)
        self._api_key = api_key
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, connect=5.0, read=30.0, write=10.0, pool=5.0)
        )

    def generate(self, request: AIRequest) -> AIResponse:
        if request.model.provider_key != "groq" or request.model.model_key != _MODEL:
            raise AIProviderError(
                AIProviderFailure.UNSUPPORTED_MODEL,
                diagnostic_stage=AIProviderDiagnosticStage.HTTP,
                diagnostic_reason=AIProviderDiagnosticReason.HTTP_STATUS,
            )
        body = {
            "messages": [
                {
                    "role": message.role.value,
                    "content": (
                        _STRUCTURED_SYSTEM_INSTRUCTION
                        if message.role.value == "system"
                        and request.prompt.prompt_key in _STRUCTURED_PROMPTS
                        else message.content
                    ),
                }
                for message in request.messages
            ],
            "model": request.model.model_key,
            "max_completion_tokens": request.maximum_output_tokens,
            "n": 1,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.structured_output.schema_key.replace(".", "_"),
                    "strict": True,
                    "schema": _structured_schema(request),
                },
            },
            "stream": False,
            "temperature": 0,
        }
        if len(json.dumps(body, separators=(",", ":")).encode()) > MAX_AI_PAYLOAD_BYTES:
            raise AIProviderError(
                AIProviderFailure.BAD_REQUEST,
                diagnostic_stage=AIProviderDiagnosticStage.CONTENT,
                diagnostic_reason=AIProviderDiagnosticReason.OVERSIZED_RESPONSE,
            )

        diagnostic: AIProviderError | None = None
        response: httpx.Response | None = None
        try:
            response = self._client.post(
                _ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=request.timeout_seconds,
            )
        except Exception as error:
            diagnostic = _normalize_exception(error)
        if diagnostic is not None:
            raise diagnostic from None
        if response is None:
            raise _error(
                AIProviderFailure.UNEXPECTED_RESPONSE,
                AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
                AIProviderDiagnosticReason.INVALID_MESSAGE,
            )
        if response.status_code != 200:
            provider_error_type = (
                _provider_error_type(response)
                if len(response.content) <= MAX_AI_PAYLOAD_BYTES
                else None
            )
            raise _normalize_status(
                response.status_code, provider_error_type=provider_error_type
            ) from None
        if len(response.content) > MAX_AI_PAYLOAD_BYTES:
            raise _error(
                AIProviderFailure.OVERSIZED_RESPONSE,
                AIProviderDiagnosticStage.CONTENT,
                AIProviderDiagnosticReason.OVERSIZED_RESPONSE,
            )

        raw: object = None
        envelope_parse_failed = False
        try:
            raw = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            envelope_parse_failed = True
        if envelope_parse_failed:
            raise _error(
                AIProviderFailure.MALFORMED_RESPONSE,
                AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
                AIProviderDiagnosticReason.INVALID_MESSAGE,
            )
        if not isinstance(raw, dict):
            raise _error(
                AIProviderFailure.MALFORMED_RESPONSE,
                AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
                AIProviderDiagnosticReason.INVALID_MESSAGE,
            )
        choice = _only_choice(raw)
        if "message" not in choice:
            raise _error(
                AIProviderFailure.UNEXPECTED_RESPONSE,
                AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
                AIProviderDiagnosticReason.MISSING_MESSAGE,
            )
        message = choice["message"]
        if not isinstance(message, dict):
            raise _error(
                AIProviderFailure.UNEXPECTED_RESPONSE,
                AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
                AIProviderDiagnosticReason.INVALID_MESSAGE,
            )
        refusal = message.get("refusal")
        if isinstance(refusal, str) and refusal:
            raise _error(
                AIProviderFailure.REFUSAL,
                AIProviderDiagnosticStage.FINISH_STATUS,
                AIProviderDiagnosticReason.REFUSAL,
                finish_status=AIFinishStatus.REFUSED,
            )
        finish_reason = choice.get("finish_reason")
        if finish_reason == "length":
            raise _error(
                AIProviderFailure.TRUNCATED,
                AIProviderDiagnosticStage.FINISH_STATUS,
                AIProviderDiagnosticReason.TRUNCATION,
                finish_status=AIFinishStatus.TRUNCATED,
            )
        if finish_reason != "stop":
            raise _error(
                AIProviderFailure.UNEXPECTED_RESPONSE,
                AIProviderDiagnosticStage.FINISH_STATUS,
                AIProviderDiagnosticReason.UNEXPECTED_FINISH,
            )
        if "content" not in message:
            raise _error(
                AIProviderFailure.MALFORMED_RESPONSE,
                AIProviderDiagnosticStage.CONTENT,
                AIProviderDiagnosticReason.MISSING_CONTENT,
            )
        content = message["content"]
        if not isinstance(content, str) or not content:
            raise _error(
                AIProviderFailure.MALFORMED_RESPONSE,
                AIProviderDiagnosticStage.CONTENT,
                AIProviderDiagnosticReason.INVALID_CONTENT,
            )
        structured: object = None
        content_parse_failed = False
        try:
            structured = json.loads(content)
        except json.JSONDecodeError:
            content_parse_failed = True
        if content_parse_failed:
            raise _error(
                AIProviderFailure.MALFORMED_RESPONSE,
                AIProviderDiagnosticStage.JSON_PARSE,
                AIProviderDiagnosticReason.JSON_PARSE_FAILED,
            )
        if not isinstance(structured, dict):
            raise _error(
                AIProviderFailure.MALFORMED_RESPONSE,
                AIProviderDiagnosticStage.JSON_SHAPE,
                AIProviderDiagnosticReason.JSON_NOT_OBJECT,
            )
        return AIResponse(
            request.invocation_id,
            request.correlation_id,
            request.model,
            AIFinishStatus.COMPLETED,
            content,
            _usage(raw.get("usage")),
        )


def _wire_schema(value: Any) -> Any:
    """Translate canonical JSON Schema into Groq-compatible equivalent forms."""

    if isinstance(value, list):
        return [_wire_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "const" in value and "enum" in value:
        raise _error(
            AIProviderFailure.SCHEMA_VIOLATION,
            AIProviderDiagnosticStage.CONTENT,
            AIProviderDiagnosticReason.SCHEMA_TRANSLATION,
        )
    translated = {key: _wire_schema(item) for key, item in value.items() if key != "const"}
    if "const" in value:
        translated["enum"] = [_wire_schema(value["const"])]
    if set(translated) == {"anyOf"} and isinstance(translated["anyOf"], list):
        branches = translated["anyOf"]
        bare_integer = {"type": "integer"}
        bare_number = {"type": "number"}
        if bare_integer in branches and bare_number in branches:
            return {"anyOf": [branch for branch in branches if branch != bare_integer]}
    return translated


def _structured_schema(request: AIRequest) -> dict[str, Any]:
    schema = _wire_schema(json.loads(request.schema_json))
    if not isinstance(schema, dict):
        raise _error(
            AIProviderFailure.SCHEMA_VIOLATION,
            AIProviderDiagnosticStage.CONTENT,
            AIProviderDiagnosticReason.SCHEMA_TRANSLATION,
        )
    if request.prompt.prompt_key == "executive.intent-classification":
        _add_intent_guidance(schema)
    return schema


def _add_intent_guidance(schema: dict[str, Any]) -> None:
    properties = schema.get("properties")
    names = {
        "outcome",
        "reason",
        "goal",
        "planning_input",
        "clarification_question",
        "missing_fields",
    }
    if not isinstance(properties, dict) or any(
        not isinstance(properties.get(name), dict) for name in names
    ):
        raise _error(
            AIProviderFailure.SCHEMA_VIOLATION,
            AIProviderDiagnosticStage.CONTENT,
            AIProviderDiagnosticReason.SCHEMA_TRANSLATION,
        )
    schema["description"] = (
        "Return one canonical intent. planning_ready uses reason ready, non-null goal and "
        "planning_input, null clarification_question, and empty missing_fields. "
        "clarification_required uses reason missing_information, null goal and planning_input, "
        "a non-empty clarification_question of at most 500 characters, and 1 to 8 unique "
        "lowercase missing_fields. unsupported uses reason unsupported_request, null goal, "
        "planning_input, and clarification_question, and empty missing_fields."
    )


def _only_choice(value: dict[str, Any]) -> dict[str, Any]:
    if "choices" not in value:
        raise _error(
            AIProviderFailure.UNEXPECTED_RESPONSE,
            AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
            AIProviderDiagnosticReason.MISSING_CHOICES,
        )
    choices = value["choices"]
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise _error(
            AIProviderFailure.UNEXPECTED_RESPONSE,
            AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
            AIProviderDiagnosticReason.INVALID_CHOICES,
        )
    return choices[0]


def _usage(value: object) -> AIUsage | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise _invalid_usage()
    input_tokens = _integer(value, "prompt_tokens")
    output_tokens = _integer(value, "completion_tokens")
    total_tokens = _integer(value, "total_tokens")
    details = value.get("prompt_tokens_details")
    cached = 0
    if details is not None:
        if not isinstance(details, dict):
            raise _invalid_usage()
        cached = _integer(details, "cached_tokens")
    try:
        return AIUsage(input_tokens, output_tokens, total_tokens, cached)
    except ValueError:
        raise _invalid_usage() from None


def _integer(value: dict[str, Any], name: str) -> int:
    item = value.get(name)
    if not isinstance(item, int) or isinstance(item, bool):
        raise _invalid_usage()
    return item


def _invalid_usage() -> AIProviderError:
    return _error(
        AIProviderFailure.UNEXPECTED_RESPONSE,
        AIProviderDiagnosticStage.RESPONSE_ENVELOPE,
        AIProviderDiagnosticReason.INVALID_USAGE,
    )


def _normalize_exception(error: Exception) -> AIProviderError:
    if isinstance(error, httpx.TimeoutException):
        return _error(
            AIProviderFailure.TIMEOUT,
            AIProviderDiagnosticStage.HTTP,
            AIProviderDiagnosticReason.TIMEOUT,
        )
    if isinstance(error, httpx.RequestError):
        return _error(
            AIProviderFailure.CONNECTION,
            AIProviderDiagnosticStage.HTTP,
            AIProviderDiagnosticReason.CONNECTION,
        )
    return _error(
        AIProviderFailure.UNEXPECTED_RESPONSE,
        AIProviderDiagnosticStage.HTTP,
        AIProviderDiagnosticReason.CONNECTION,
    )


def _provider_error_type(response: httpx.Response) -> str | None:
    raw: object = None
    with suppress(json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raw = response.json()
    if not isinstance(raw, dict):
        return None
    error = raw.get("error")
    if not isinstance(error, dict):
        return None
    value = error.get("type")
    if not isinstance(value, str) or _PROVIDER_ERROR_TYPE.fullmatch(value) is None:
        return None
    return value


def _normalize_status(status: int, *, provider_error_type: str | None = None) -> AIProviderError:
    if status == 401:
        return _http_error(AIProviderFailure.AUTHENTICATION, status, provider_error_type)
    if status == 403:
        return _http_error(AIProviderFailure.PERMISSION, status, provider_error_type)
    if status == 404:
        return _http_error(AIProviderFailure.UNSUPPORTED_MODEL, status, provider_error_type)
    if status == 429:
        return _http_error(AIProviderFailure.RATE_LIMIT, status, provider_error_type)
    if status in {502, 503, 504}:
        return _http_error(AIProviderFailure.UNAVAILABLE, status, provider_error_type)
    if 500 <= status <= 599:
        return _http_error(AIProviderFailure.INTERNAL, status, provider_error_type)
    if status in {400, 413, 422} or 400 <= status <= 499:
        return _http_error(AIProviderFailure.BAD_REQUEST, status, provider_error_type)
    return _http_error(AIProviderFailure.UNEXPECTED_RESPONSE, status, provider_error_type)


def _http_error(
    failure: AIProviderFailure, status: int, provider_error_type: str | None
) -> AIProviderError:
    return _error(
        failure,
        AIProviderDiagnosticStage.HTTP,
        AIProviderDiagnosticReason.HTTP_STATUS,
        http_status=status,
        provider_error_type=provider_error_type,
    )


def _error(
    failure: AIProviderFailure,
    stage: AIProviderDiagnosticStage,
    reason: AIProviderDiagnosticReason,
    *,
    http_status: int | None = None,
    finish_status: AIFinishStatus | None = None,
    provider_error_type: str | None = None,
) -> AIProviderError:
    return AIProviderError(
        failure,
        http_status,
        diagnostic_stage=stage,
        diagnostic_reason=reason,
        finish_status=finish_status,
        provider_error_type=provider_error_type,
    )
