"""Explicitly opted-in live Groq smoke; never active in ordinary pytest."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from rightjob.ai_runtime import build_ai_planning_stack
from rightjob.contracts.ai import (
    AIFinishStatus,
    AIMessage,
    AIMessageRole,
    AIModelPurpose,
    AIModelReference,
    AIProvider,
    AIProviderDiagnosticReason,
    AIProviderDiagnosticStage,
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
from rightjob.executive import decode_executive_intent
from rightjob.planner import decode_ai_plan_proposal
from rightjob.provider_adapters import GroqProviderAdapter
from rightjob.registry import BuiltInCapabilityRegistry, BuiltInDepartmentRegistry
from rightjob.shared.config import Settings

LIVE_OPT_IN = "RIGHTJOB_LIVE_AI_TESTS"
LIVE_KEY = "RIGHTJOB_GROQ_API_KEY"
MODEL = "openai/gpt-oss-20b"
SYNTHETIC_REQUEST = "Prepare, transform, and verify this synthetic content."


def _live_enabled() -> bool:
    return (
        os.environ.get(LIVE_OPT_IN) == "true"
        and os.environ.get("RIGHTJOB_AI_ENABLED") == "true"
        and os.environ.get("RIGHTJOB_AI_ADAPTER") == "groq"
        and os.environ.get("RIGHTJOB_AI_MODEL") == MODEL
        and bool(os.environ.get(LIVE_KEY))
    )


live_only = pytest.mark.skipif(
    not _live_enabled(),
    reason="explicit live Groq opt-in, exact free model, and credential required",
)


@dataclass(frozen=True, slots=True)
class SafeInvocationEvidence:
    provider: str
    model: str
    stage: str
    invocation_count: int
    finish_status: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


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
    finish_status: str | None
    diagnostic_stage: str | None
    diagnostic_reason: str | None
    provider_error_type: str | None


class ObservedProvider:
    def __init__(self, delegate: AIProvider) -> None:
        self._delegate = delegate
        self.evidence: list[SafeInvocationEvidence] = []
        self.failures: list[SafeFailureEvidence] = []
        self.invocation_count = 0

    def generate(self, request: AIRequest) -> AIResponse:
        self.invocation_count += 1
        stage = "INTENT" if self.invocation_count == 1 else "PLANNING"
        try:
            response = self._delegate.generate(request)
        except AIProviderError as error:
            self._record_failure(request, stage, error)
            raise
        usage = response.usage
        self.evidence.append(
            SafeInvocationEvidence(
                request.model.provider_key,
                request.model.model_key,
                stage,
                self.invocation_count,
                response.finish_status.value,
                usage.input_tokens if usage else None,
                usage.output_tokens if usage else None,
                usage.total_tokens if usage else None,
            )
        )
        try:
            if stage == "INTENT":
                decode_executive_intent(response.content)
            else:
                decode_ai_plan_proposal(response.content)
        except AIProviderError as error:
            self._record_failure(request, stage, error)
        return response

    def _record_failure(self, request: AIRequest, stage: str, error: AIProviderError) -> None:
        self.failures.append(
            SafeFailureEvidence(
                request.model.provider_key,
                request.model.model_key,
                stage,
                self.invocation_count,
                error.failure.value,
                error.kind.value,
                error.retryable,
                error.http_status,
                error.finish_status.value if error.finish_status else None,
                error.diagnostic_stage.value if error.diagnostic_stage else None,
                error.diagnostic_reason.value if error.diagnostic_reason else None,
                error.provider_error_type,
            )
        )


@live_only
def test_live_groq_intent_and_planning_smoke() -> None:
    settings = Settings.load()
    assert settings.ai.enabled is True
    assert settings.ai.adapter == "groq"
    assert settings.ai.model == MODEL
    assert settings.ai.api_key

    capabilities = BuiltInCapabilityRegistry()
    departments = BuiltInDepartmentRegistry(capabilities)
    observed: ObservedProvider | None = None

    def provider_factory(api_key: str) -> AIProvider:
        nonlocal observed
        observed = ObservedProvider(GroqProviderAdapter(api_key))
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
            Actor(ActorType.USER, "phase-2.16-groq-live-smoke"),
            correlation_id,
            uuid4(),
            SYNTHETIC_REQUEST,
        )
    )

    assert observed is not None
    assert observed.invocation_count <= 2
    assert all(item.provider == "groq" for item in observed.evidence)
    if result.outcome is ExecutiveIntakeOutcome.PLANNED:
        assert observed.invocation_count == 2
        assert result.plan is not None
        assert result.plan.workspace_id == result.workspace_id
        assert result.plan.actor == result.actor
        assert result.plan.correlation_id == correlation_id
    else:
        if (
            result.outcome is ExecutiveIntakeOutcome.FAILED
            and observed.invocation_count == 2
            and not observed.failures
        ):
            observed.failures.append(
                SafeFailureEvidence(
                    "groq",
                    MODEL,
                    "PLANNING",
                    2,
                    AIProviderFailure.SCHEMA_VIOLATION.value,
                    AIProviderFailure.SCHEMA_VIOLATION.kind.value,
                    False,
                    None,
                    None,
                    AIProviderDiagnosticStage.CANONICAL_DECODE.value,
                    AIProviderDiagnosticReason.INVALID_PLANNING_PROPOSAL.value,
                    None,
                )
            )
        assert result.outcome in {
            ExecutiveIntakeOutcome.CLARIFICATION_REQUIRED,
            ExecutiveIntakeOutcome.UNSUPPORTED,
        }, observed.failures
        assert observed.invocation_count == 1


def test_observer_records_bounded_provider_failure() -> None:
    class FailingProvider:
        def generate(self, request: AIRequest) -> AIResponse:
            raise AIProviderError(
                AIProviderFailure.BAD_REQUEST,
                400,
                diagnostic_stage=AIProviderDiagnosticStage.HTTP,
                diagnostic_reason=AIProviderDiagnosticReason.HTTP_STATUS,
                provider_error_type="invalid_request_error",
            )

    observed = ObservedProvider(FailingProvider())
    with pytest.raises(AIProviderError):
        observed.generate(_safe_test_request())

    assert observed.failures == [
        SafeFailureEvidence(
            "groq",
            MODEL,
            "INTENT",
            1,
            "bad_request",
            "invalid_output",
            False,
            400,
            None,
            "http",
            "http_status",
            "invalid_request_error",
        )
    ]


def test_observer_records_canonical_decode_without_content() -> None:
    class InvalidIntentProvider:
        def generate(self, request: AIRequest) -> AIResponse:
            return AIResponse(
                request.invocation_id,
                request.correlation_id,
                request.model,
                AIFinishStatus.COMPLETED,
                '{"schema_version":2}',
            )

    observed = ObservedProvider(InvalidIntentProvider())
    observed.generate(_safe_test_request())

    assert observed.failures[0].diagnostic_stage == "json_shape"
    assert observed.failures[0].diagnostic_reason == "exact_fields_mismatch"
    assert not hasattr(observed.failures[0], "content")


def _safe_test_request() -> AIRequest:
    version = SemanticVersion.parse("1.0.0")
    return AIRequest(
        uuid4(),
        uuid4(),
        AIModelPurpose.EXECUTIVE_PLANNING,
        AIModelReference("groq", MODEL),
        PromptReference("executive.intent-classification", version),
        StructuredOutputReference("executive.intent-result", version),
        '{"type":"object"}',
        (AIMessage(AIMessageRole.USER, "bounded"),),
        128,
        30,
    )
