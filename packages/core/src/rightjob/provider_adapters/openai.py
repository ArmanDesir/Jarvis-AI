"""OpenAI Responses API adapter; all SDK types remain inside infrastructure."""

from __future__ import annotations

import json
from typing import Any, Protocol, cast

import httpx
import openai as sdk

from rightjob.contracts.ai import (
    AIFinishStatus,
    AIProviderError,
    AIProviderFailure,
    AIRequest,
    AIResponse,
    AIUsage,
)


class _Responses(Protocol):
    def create(self, **kwargs: object) -> object: ...


class _Client(Protocol):
    @property
    def responses(self) -> _Responses: ...


class OpenAIProviderAdapter:
    def __init__(self, api_key: str | None, *, client: _Client | None = None) -> None:
        if client is None:
            if not api_key:
                raise AIProviderError(AIProviderFailure.CONFIGURATION)
            client = cast(
                _Client,
                sdk.OpenAI(
                    api_key=api_key,
                    max_retries=0,
                    timeout=httpx.Timeout(30.0, connect=5.0, read=30.0, write=10.0, pool=5.0),
                ),
            )
        self._client = client

    def generate(self, request: AIRequest) -> AIResponse:
        instructions = "\n".join(
            message.content for message in request.messages if message.role.value == "system"
        )
        user_input = "\n".join(
            message.content for message in request.messages if message.role.value == "user"
        )
        diagnostic: AIProviderError | None = None
        try:
            schema = json.loads(request.schema_json)
            raw = self._client.responses.create(
                background=False,
                input=user_input,
                instructions=instructions,
                max_output_tokens=request.maximum_output_tokens,
                model=request.model.model_key,
                store=False,
                stream=False,
                text={
                    "format": {
                        "name": request.structured_output.schema_key.replace(".", "_"),
                        "schema": schema,
                        "strict": True,
                        "type": "json_schema",
                    }
                },
                tools=[],
                truncation="disabled",
                timeout=request.timeout_seconds,
            )
        except Exception as error:
            diagnostic = _normalize(error)
        if diagnostic is not None:
            raise diagnostic
        status = getattr(raw, "status", None)
        if _refusal(raw):
            raise AIProviderError(AIProviderFailure.REFUSAL)
        if status == "incomplete":
            raise AIProviderError(AIProviderFailure.TRUNCATED)
        if status != "completed":
            raise AIProviderError(AIProviderFailure.UNEXPECTED_RESPONSE)
        content = getattr(raw, "output_text", None)
        if not isinstance(content, str) or not content:
            raise AIProviderError(AIProviderFailure.MALFORMED_RESPONSE)
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as error:
            raise AIProviderError(AIProviderFailure.MALFORMED_RESPONSE) from error
        if not isinstance(decoded, dict):
            raise AIProviderError(AIProviderFailure.MALFORMED_RESPONSE)
        return AIResponse(
            request.invocation_id,
            request.correlation_id,
            request.model,
            AIFinishStatus.COMPLETED,
            content,
            _usage(getattr(raw, "usage", None)),
        )


def _normalize(error: Exception) -> AIProviderError:
    if isinstance(error, sdk.APITimeoutError):
        return AIProviderError(AIProviderFailure.TIMEOUT)
    if isinstance(error, sdk.APIConnectionError):
        return AIProviderError(AIProviderFailure.CONNECTION)
    if isinstance(error, sdk.RateLimitError):
        return AIProviderError(AIProviderFailure.RATE_LIMIT, error.status_code)
    if isinstance(error, sdk.AuthenticationError):
        return AIProviderError(AIProviderFailure.AUTHENTICATION, error.status_code)
    if isinstance(error, sdk.PermissionDeniedError):
        return AIProviderError(AIProviderFailure.PERMISSION, error.status_code)
    if isinstance(error, sdk.BadRequestError):
        return AIProviderError(AIProviderFailure.BAD_REQUEST, error.status_code)
    if isinstance(error, sdk.NotFoundError):
        return AIProviderError(AIProviderFailure.UNSUPPORTED_MODEL, error.status_code)
    if isinstance(error, sdk.APIStatusError) and error.status_code in {502, 503, 504}:
        return AIProviderError(AIProviderFailure.UNAVAILABLE, error.status_code)
    if isinstance(error, sdk.InternalServerError):
        return AIProviderError(AIProviderFailure.INTERNAL, error.status_code)
    if isinstance(error, sdk.APIError):
        return AIProviderError(AIProviderFailure.UNEXPECTED_RESPONSE)
    return AIProviderError(AIProviderFailure.UNEXPECTED_RESPONSE)


def _refusal(response: object) -> bool:
    for output in _items(getattr(response, "output", ())):
        for content in _items(getattr(output, "content", ())):
            if getattr(content, "type", None) == "refusal":
                return True
    return False


def _usage(value: object) -> AIUsage | None:
    if value is None:
        return None
    input_tokens = _integer(value, "input_tokens")
    output_tokens = _integer(value, "output_tokens")
    total_tokens = _integer(value, "total_tokens")
    details = getattr(value, "input_tokens_details", None)
    cached = 0 if details is None else _integer(details, "cached_tokens")
    try:
        return AIUsage(input_tokens, output_tokens, total_tokens, cached)
    except ValueError as error:
        raise AIProviderError(AIProviderFailure.UNEXPECTED_RESPONSE) from error


def _integer(value: object, name: str) -> int:
    item = getattr(value, name, None)
    if not isinstance(item, int) or isinstance(item, bool):
        raise AIProviderError(AIProviderFailure.UNEXPECTED_RESPONSE)
    return item


def _items(value: object) -> tuple[Any, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return ()
