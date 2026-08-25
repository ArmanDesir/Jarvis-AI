"""Explicitly gated isolated Groq capability compatibility probes."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from time import monotonic
from typing import Any, cast

import httpx
import pytest
from rightjob.contracts.ai import MAX_AI_PAYLOAD_BYTES
from rightjob.executive.intake import INTENT_SCHEMA, INTENT_SCHEMA_JSON, SYSTEM_INSTRUCTION
from rightjob.provider_adapters.groq import _wire_schema

LIVE_OPT_IN = "RIGHTJOB_LIVE_AI_TESTS"
LIVE_KEY = "RIGHTJOB_GROQ_API_KEY"
MODEL = "openai/gpt-oss-20b"
ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MAX_CALLS = 2
_ERROR_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$", re.ASCII)


@dataclass(frozen=True, slots=True)
class Probe:
    label: str
    body: dict[str, object]


@dataclass(frozen=True, slots=True)
class ProbeEvidence:
    probe: str
    provider: str
    model: str
    http_status: int | None
    success: bool
    provider_error_type: str | None
    finish_status: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    elapsed_seconds: float
    content_present: bool
    valid_json: bool
    schema_match: bool


def _live_enabled() -> bool:
    return (
        os.environ.get(LIVE_OPT_IN) == "true"
        and os.environ.get("RIGHTJOB_AI_ADAPTER") == "groq"
        and os.environ.get("RIGHTJOB_AI_MODEL") == MODEL
        and bool(os.environ.get(LIVE_KEY))
    )


live_only = pytest.mark.skipif(
    not _live_enabled(),
    reason="explicit isolated Groq compatibility opt-in, model, adapter, and credential required",
)


def _minimal_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }


def _probes() -> tuple[Probe, ...]:
    baseline = _g1_body()
    messages = cast(list[dict[str, object]], baseline["messages"])
    action, result = _classification_phrases()
    return (
        Probe(
            "J1-classification-action",
            _with_messages(baseline, action, messages[1]["content"]),
        ),
        Probe(
            "J2-structured-intent-result",
            _with_messages(baseline, result, messages[1]["content"]),
        ),
    )


def _classification_phrases() -> tuple[str, str]:
    sentence = SYSTEM_INSTRUCTION.split(". ", maxsplit=1)[0]
    action, result = sentence.split(" into ", maxsplit=1)
    assert f"{action} into {result}" == sentence
    return f"{action}.", f"Return {result}."


def _g1_body() -> dict[str, object]:
    return _with_schema(
        _d2_body(),
        INTENT_SCHEMA.schema_key.replace(".", "_"),
        _wire_schema(json.loads(INTENT_SCHEMA_JSON)),
    )


def _d2_body() -> dict[str, object]:
    json_system = "Return only the requested synthetic JSON object."
    json_user = 'Return only this JSON object: {"ok":true}'
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": json_system},
            {"role": "user", "content": json_user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "probe",
                "strict": True,
                "schema": _minimal_schema(),
            },
        },
        "max_completion_tokens": 512,
        "n": 1,
        "temperature": 0,
        "stream": False,
    }


def _with_schema(body: dict[str, object], name: str, schema: dict[str, Any]) -> dict[str, object]:
    return {
        **body,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": name, "strict": True, "schema": schema},
        },
    }


def _with_messages(body: dict[str, object], system: object, user: object) -> dict[str, object]:
    return {
        **body,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }


def _request_body(probe: Probe) -> dict[str, object]:
    return probe.body


def _run(client: httpx.Client, api_key: str) -> list[ProbeEvidence]:
    evidence: list[ProbeEvidence] = []
    for probe in _probes():
        item = _invoke(client, api_key, probe, len(evidence))
        evidence.append(item)
        if not item.success:
            break
    assert 0 <= len(evidence) <= MAX_CALLS
    return evidence


def _invoke(client: httpx.Client, api_key: str, probe: Probe, call_count: int) -> ProbeEvidence:
    if call_count >= MAX_CALLS:
        raise RuntimeError("Groq compatibility probe call limit reached")
    started = monotonic()
    try:
        response = client.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=_request_body(probe),
            timeout=30,
        )
    except httpx.RequestError:
        return _evidence(probe.label, None, False, None, None, None, monotonic() - started)
    elapsed = monotonic() - started
    if response.status_code != 200:
        error_type = (
            _provider_error_type(response)
            if len(response.content) <= MAX_AI_PAYLOAD_BYTES
            else None
        )
        return _evidence(probe.label, response.status_code, False, error_type, None, None, elapsed)
    if len(response.content) > MAX_AI_PAYLOAD_BYTES:
        return _evidence(probe.label, 200, False, None, None, None, elapsed)
    envelope = _json_object(response.content)
    choice = _choice(envelope)
    finish = choice.get("finish_reason") if choice else None
    message = choice.get("message") if choice else None
    content = message.get("content") if isinstance(message, dict) else None
    content_present = isinstance(content, str) and bool(content.strip())
    decoded = _json_object(content.encode()) if content_present else None
    valid_json = decoded is not None
    schema_match = valid_json
    usage = envelope.get("usage") if envelope else None
    tokens = _usage(usage)
    success = finish == "stop" and content_present
    success = success and valid_json and schema_match
    return _evidence(
        probe.label,
        200,
        success,
        None,
        finish if isinstance(finish, str) else None,
        tokens,
        elapsed,
        content_present,
        valid_json,
        schema_match,
    )


def _evidence(
    probe: str,
    status: int | None,
    success: bool,
    error_type: str | None,
    finish: str | None,
    usage: tuple[int, int, int] | None,
    elapsed: float,
    content_present: bool = False,
    valid_json: bool = False,
    schema_match: bool = False,
) -> ProbeEvidence:
    return ProbeEvidence(
        probe,
        "groq",
        MODEL,
        status,
        success,
        error_type,
        finish,
        usage[0] if usage else None,
        usage[1] if usage else None,
        usage[2] if usage else None,
        elapsed,
        content_present,
        valid_json,
        schema_match,
    )


def _json_object(content: bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _choice(envelope: dict[str, Any] | None) -> dict[str, Any] | None:
    choices = envelope.get("choices") if envelope else None
    return (
        choices[0]
        if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict)
        else None
    )


def _usage(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, dict):
        return None
    prompt = value.get("prompt_tokens")
    completion = value.get("completion_tokens")
    total = value.get("total_tokens")
    if any(
        not isinstance(item, int) or isinstance(item, bool) for item in (prompt, completion, total)
    ):
        return None
    return cast(int, prompt), cast(int, completion), cast(int, total)


def _provider_error_type(response: httpx.Response) -> str | None:
    envelope = _json_object(response.content)
    error = envelope.get("error") if envelope else None
    value = error.get("type") if isinstance(error, dict) else None
    return value if isinstance(value, str) and _ERROR_TYPE.fullmatch(value) else None


@pytest.mark.skip(reason="closed compatibility diagnostic; use the full runtime smoke")
@live_only
def test_live_groq_structured_output_compatibility() -> None:
    with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
        evidence = _run(client, os.environ[LIVE_KEY])
    assert all(item.success for item in evidence), evidence
    assert [item.probe for item in evidence] == [
        "J1-classification-action",
        "J2-structured-intent-result",
    ], evidence


def test_classification_phrases_change_only_g1_system_message_and_gate_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (LIVE_OPT_IN, LIVE_KEY, "RIGHTJOB_AI_ADAPTER", "RIGHTJOB_AI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert _live_enabled() is False
    baseline = _g1_body()
    i1, i2 = (_request_body(probe) for probe in _probes())
    i1_shared = {key: value for key, value in i1.items() if key != "messages"}
    i2_shared = {key: value for key, value in i2.items() if key != "messages"}
    baseline_shared = {key: value for key, value in baseline.items() if key != "messages"}
    assert i1_shared == i2_shared == baseline_shared
    action, result = _classification_phrases()
    assert i1["messages"][0]["content"] == action
    assert i2["messages"][0]["content"] == result
    assert i1["messages"][1] == i2["messages"][1] == baseline["messages"][1]
    original_first = SYSTEM_INSTRUCTION.split(". ", maxsplit=1)[0]
    assert (
        original_first
        == f"{action.removesuffix('.')} into {result.removeprefix('Return ').removesuffix('.')}"
    )
    for body in (i1, i2):
        assert body["response_format"] == baseline["response_format"]
        assert body["max_completion_tokens"] == 512
        assert body["n"] == 1
        assert body["temperature"] == 0
        assert body["stream"] is False
        assert not ({"tools", "functions", "tool_choice"} & body.keys())


def test_success_uses_exactly_two_calls_with_safe_evidence() -> None:
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _completed(json.dumps({"ok": True}))

    evidence = _run(httpx.Client(transport=httpx.MockTransport(handle)), "test-key")
    assert calls == MAX_CALLS
    assert len(evidence) == MAX_CALLS
    assert all(item.success for item in evidence)
    assert all(not hasattr(item, field) for item in evidence for field in ("prompt", "body", "key"))


def test_first_section_failure_stops_before_second_without_retry() -> None:
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            400,
            json={"error": {"message": "discarded", "type": "invalid_request_error"}},
        )

    evidence = _run(httpx.Client(transport=httpx.MockTransport(handle)), "test-key")
    assert calls == 1
    assert len(evidence) == 1
    assert not evidence[0].success
    assert evidence[0].provider_error_type == "invalid_request_error"
    assert all(not hasattr(item, "message") for item in evidence)


def test_second_section_failure_uses_exactly_two_calls_without_retry() -> None:
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _completed(json.dumps({"ok": True}))
        return httpx.Response(400, json={"error": {"type": "invalid_request_error"}})

    evidence = _run(httpx.Client(transport=httpx.MockTransport(handle)), "test-key")
    assert calls == MAX_CALLS
    assert len(evidence) == MAX_CALLS
    assert evidence[0].success
    assert not evidence[1].success


def _completed(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )
