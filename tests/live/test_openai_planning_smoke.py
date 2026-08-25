"""Explicitly opted-in live OpenAI smoke; never active in ordinary pytest."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID, uuid4

import pytest
from rightjob.ai_runtime import build_ai_planning_stack
from rightjob.contracts.ai import (
    AIFinishStatus,
    AIMessage,
    AIMessageRole,
    AIModelPurpose,
    AIModelReference,
    AIProvider,
    AIProviderError,
    AIProviderFailure,
    AIRequest,
    AIResponse,
    PromptReference,
    StructuredOutputReference,
)
from rightjob.contracts.capabilities import SemanticVersion
from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.executive_intake import ExecutiveIntakeOutcome, ExecutiveIntakeRequest
from rightjob.provider_adapters import OpenAIProviderAdapter
from rightjob.registry import BuiltInCapabilityRegistry, BuiltInDepartmentRegistry
from rightjob.shared.config import Settings

LIVE_OPT_IN = "RIGHTJOB_LIVE_AI_TESTS"
LIVE_KEY = "RIGHTJOB_OPENAI_API_KEY"
SYNTHETIC_REQUEST = "Prepare, transform, and verify this synthetic content."


def _live_enabled() -> bool:
    return os.environ.get(LIVE_OPT_IN) == "true" and bool(os.environ.get(LIVE_KEY))


live_only = pytest.mark.skipif(
    not _live_enabled(),
    reason="explicit live AI opt-in and OpenAI credential required",
)


@dataclass(frozen=True, slots=True)
class SafeInvocationEvidence:
    provider: str
    model: str
    purpose: str
    prompt: str
    schema: str
    finish_status: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    elapsed_seconds: float
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class SafeFailureEvidence:
    provider: str
    model: str
    stage: str
    invocation_count: int
    failure: str
    kind: str
    retryable: bool
    http_status: int | None


class ObservedProvider:
    def __init__(self, delegate: AIProvider) -> None:
        self._delegate = delegate
        self.evidence: list[SafeInvocationEvidence] = []
        self.failures: list[SafeFailureEvidence] = []
        self.invocation_count = 0

    def generate(self, request: AIRequest) -> AIResponse:
        self.invocation_count += 1
        started = monotonic()
        try:
            response = self._delegate.generate(request)
        except AIProviderError as error:
            self.failures.append(
                SafeFailureEvidence(
                    request.model.provider_key,
                    request.model.model_key,
                    "INTENT" if self.invocation_count == 1 else "PLANNING",
                    self.invocation_count,
                    error.failure.value,
                    error.kind.value,
                    error.retryable,
                    error.http_status,
                )
            )
            raise
        elapsed = monotonic() - started
        usage = response.usage
        self.evidence.append(
            SafeInvocationEvidence(
                request.model.provider_key,
                request.model.model_key,
                request.purpose.value,
                f"{request.prompt.prompt_key}@{request.prompt.semantic_version}",
                f"{request.structured_output.schema_key}@{request.structured_output.semantic_version}",
                response.finish_status.value,
                usage.input_tokens if usage else None,
                usage.output_tokens if usage else None,
                usage.total_tokens if usage else None,
                elapsed,
                request.correlation_id,
            )
        )
        return response


@live_only
def test_live_openai_intent_and_planning_smoke() -> None:
    settings = Settings.load()
    assert settings.ai.enabled is True
    assert settings.ai.adapter == "openai"
    assert settings.ai.model
    assert settings.ai.api_key

    capabilities = BuiltInCapabilityRegistry()
    departments = BuiltInDepartmentRegistry(capabilities)
    observed: ObservedProvider | None = None

    def provider_factory(api_key: str) -> AIProvider:
        nonlocal observed
        observed = ObservedProvider(OpenAIProviderAdapter(api_key))
        return observed

    stack = build_ai_planning_stack(
        settings,
        capabilities,
        departments,
        uuid4,
        lambda: datetime.now(UTC),
        provider_factory=provider_factory,
    )
    correlation_id = uuid4()
    result = stack.interpret(
        ExecutiveIntakeRequest(
            uuid4(),
            Actor(ActorType.USER, "phase-2.16-live-smoke"),
            correlation_id,
            uuid4(),
            SYNTHETIC_REQUEST,
        )
    )

    assert result.outcome is ExecutiveIntakeOutcome.PLANNED, (
        observed.failures if observed is not None else []
    )
    assert result.plan is not None
    assert result.plan.workspace_id == result.workspace_id
    assert result.plan.actor == result.actor
    assert result.plan.correlation_id == correlation_id
    assert observed is not None
    assert len(observed.evidence) == 2
    assert [item.prompt.split("@", 1)[0] for item in observed.evidence] == [
        "executive.intent-classification",
        "planning.structured-proposal",
    ]
    assert all(item.provider == "openai" for item in observed.evidence)
    assert all(item.correlation_id == correlation_id for item in observed.evidence)
    assert all(item.elapsed_seconds <= settings.ai.timeout_seconds for item in observed.evidence)
    assert all(item.finish_status == "completed" for item in observed.evidence)


@pytest.mark.parametrize(("successful_calls", "stage"), [(0, "INTENT"), (1, "PLANNING")])
def test_observed_provider_records_safe_failure_stage(successful_calls: int, stage: str) -> None:
    class SequenceProvider:
        calls = 0

        def generate(self, request: AIRequest) -> AIResponse:
            self.calls += 1
            if self.calls > successful_calls:
                raise AIProviderError(AIProviderFailure.CONNECTION)
            return AIResponse(
                request.invocation_id,
                request.correlation_id,
                request.model,
                AIFinishStatus.COMPLETED,
                "{}",
            )

    observed = ObservedProvider(SequenceProvider())
    with pytest.raises(AIProviderError):
        for _ in range(successful_calls + 1):
            observed.generate(_safe_test_request())

    assert observed.failures == [
        SafeFailureEvidence(
            "openai",
            "configured-model",
            stage,
            successful_calls + 1,
            "connection_failure",
            "transient",
            True,
            None,
        )
    ]


def _safe_test_request() -> AIRequest:
    version = SemanticVersion.parse("1.0.0")
    return AIRequest(
        uuid4(),
        uuid4(),
        AIModelPurpose.EXECUTIVE_PLANNING,
        AIModelReference("openai", "configured-model"),
        PromptReference("planning.structured-proposal", version),
        StructuredOutputReference("planning.ai-plan-proposal", version),
        '{"type":"object"}',
        (AIMessage(AIMessageRole.USER, "bounded"),),
        128,
        30,
    )
