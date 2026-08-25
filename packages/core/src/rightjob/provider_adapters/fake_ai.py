"""Deterministic fake implementation of the published AI provider contract."""

from __future__ import annotations

from dataclasses import dataclass

from rightjob.contracts.ai import (
    AIFinishStatus,
    AIProviderError,
    AIProviderFailure,
    AIRequest,
    AIResponse,
    AIUsage,
)


@dataclass(frozen=True, slots=True)
class FakeAIProvider:
    content: str = ""
    finish_status: AIFinishStatus = AIFinishStatus.COMPLETED
    usage: AIUsage | None = None
    failure: AIProviderFailure | None = None

    def generate(self, request: AIRequest) -> AIResponse:
        if self.failure is not None:
            raise AIProviderError(self.failure)
        return AIResponse(
            invocation_id=request.invocation_id,
            correlation_id=request.correlation_id,
            model=request.model,
            finish_status=self.finish_status,
            content=self.content,
            usage=self.usage,
        )
