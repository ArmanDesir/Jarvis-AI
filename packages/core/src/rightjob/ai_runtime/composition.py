"""Minimal composition root for bounded provider-backed Executive planning."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from rightjob.contracts.ai import AIModelReference, AIProvider
from rightjob.contracts.capabilities import CapabilityCatalog
from rightjob.contracts.departments import DepartmentCatalog
from rightjob.executive import ExecutiveIntakeService, ExecutivePlanningService
from rightjob.planner import PlanningApplicationService, PlanValidator, ProviderBackedPlanner
from rightjob.provider_adapters import GroqProviderAdapter, OpenAIProviderAdapter
from rightjob.shared.config import ConfigurationError, Settings

IdFactory = Callable[[], UUID]
Clock = Callable[[], datetime]
ProviderFactory = Callable[[str], AIProvider]


def build_ai_planning_stack(
    settings: Settings,
    capabilities: CapabilityCatalog,
    departments: DepartmentCatalog,
    id_factory: IdFactory,
    clock: Clock,
    *,
    provider_factory: ProviderFactory | None = None,
) -> ExecutiveIntakeService:
    """Build the pre-authorization AI path; construction performs no provider request."""

    ai = settings.ai
    if not ai.enabled:
        raise ConfigurationError("AI runtime composition requires RIGHTJOB_AI_ENABLED=true")
    if ai.adapter not in {"openai", "groq"}:
        raise ConfigurationError("AI runtime composition supports only openai or groq")
    if not ai.model:
        raise ConfigurationError("AI runtime composition requires RIGHTJOB_AI_MODEL")
    if not ai.api_key:
        raise ConfigurationError("AI runtime composition requires the selected provider credential")
    if not 1 <= ai.timeout_seconds <= 30:
        raise ConfigurationError("AI runtime timeout must be between 1 and 30 seconds")
    if not 1 <= ai.maximum_output_tokens <= 8_192:
        raise ConfigurationError("AI runtime output tokens must be between 1 and 8192")

    factory = (
        provider_factory
        or {
            "openai": OpenAIProviderAdapter,
            "groq": GroqProviderAdapter,
        }[ai.adapter]
    )
    provider = factory(ai.api_key)
    model = AIModelReference(ai.adapter, ai.model)
    planner = ProviderBackedPlanner(
        provider,
        capabilities,
        departments,
        model,
        id_factory,
        clock,
        maximum_output_tokens=ai.maximum_output_tokens,
        timeout_seconds=ai.timeout_seconds,
    )
    planning = PlanningApplicationService(planner, PlanValidator(capabilities, departments))
    executive = ExecutivePlanningService(
        planning,
        capabilities,
        departments,
        id_factory,
        clock,
    )
    return ExecutiveIntakeService(
        provider,
        model,
        executive,
        id_factory,
        clock,
        maximum_output_tokens=min(512, ai.maximum_output_tokens),
        timeout_seconds=ai.timeout_seconds,
    )
