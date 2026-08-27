"""Pure deterministic eligibility and ranking for trusted AI candidate snapshots."""

from __future__ import annotations

from rightjob.contracts.ai_routing import (
    MAX_ROUTE_CANDIDATES,
    AICapabilityRouter,
    AIProviderAvailability,
    AIProviderCandidate,
    AIProviderCandidateRejection,
    AIProviderQualification,
    AIRouteDecision,
    AIRouteOutcome,
    AIRouteRejectionReason,
    AIRouteRequirements,
    AIRoutingContractError,
    AIStructuredOutputGuarantee,
)
from rightjob.contracts.events import DataSensitivity

_GUARANTEE_RANK = {
    AIStructuredOutputGuarantee.NONE: 0,
    AIStructuredOutputGuarantee.STRICT_SUBSET: 1,
    AIStructuredOutputGuarantee.CANONICAL_CONTRACT: 2,
}
_QUALIFICATION_RANK = {
    AIProviderQualification.UNVERIFIED: 0,
    AIProviderQualification.LIMITED: 1,
    AIProviderQualification.QUALIFIED: 2,
}
_SENSITIVITY_RANK = {
    DataSensitivity.PUBLIC: 0,
    DataSensitivity.INTERNAL: 1,
    DataSensitivity.CONFIDENTIAL: 2,
    DataSensitivity.RESTRICTED: 3,
}


class DeterministicAICapabilityRouter(AICapabilityRouter):
    """Filter all requirements, then rank without input-order dependence.

    Eligible candidates rank by qualification (descending), quality (descending),
    cost (ascending), latency (ascending), then provider and model key.
    """

    def route(
        self,
        requirements: AIRouteRequirements,
        candidates: tuple[AIProviderCandidate, ...],
    ) -> AIRouteDecision:
        if type(requirements) is not AIRouteRequirements:
            raise AIRoutingContractError("requirements must be AIRouteRequirements")
        if type(candidates) is not tuple:
            raise AIRoutingContractError("candidate snapshot must be a tuple")
        if len(candidates) > MAX_ROUTE_CANDIDATES:
            raise AIRoutingContractError("candidate snapshot exceeds maximum size")
        if any(type(candidate) is not AIProviderCandidate for candidate in candidates):
            raise AIRoutingContractError("candidate snapshot contains an invalid member")
        models = [candidate.model for candidate in candidates]
        if len(models) != len(set(models)):
            raise AIRoutingContractError("candidate models must be unique")

        eligible: list[AIProviderCandidate] = []
        rejected: list[AIProviderCandidateRejection] = []
        for candidate in candidates:
            reasons = _rejection_reasons(requirements, candidate)
            if reasons:
                rejected.append(AIProviderCandidateRejection(candidate.model, reasons))
            else:
                eligible.append(candidate)

        rejected.sort(key=lambda item: (item.model.provider_key, item.model.model_key))
        selected = min(eligible, key=_ranking_key) if eligible else None
        return AIRouteDecision(
            route_request_id=requirements.route_request_id,
            outcome=AIRouteOutcome.SELECTED if selected else AIRouteOutcome.UNAVAILABLE,
            selected_model=selected.model if selected else None,
            rejections=tuple(rejected),
        )


def _rejection_reasons(
    requirements: AIRouteRequirements,
    candidate: AIProviderCandidate,
) -> tuple[AIRouteRejectionReason, ...]:
    reasons: list[AIRouteRejectionReason] = []
    current_evidence = (
        candidate.evidence_observed_at <= requirements.evaluated_at < candidate.evidence_expires_at
    )
    checks = (
        (not current_evidence, AIRouteRejectionReason.STALE_EVIDENCE),
        (
            candidate.availability is not AIProviderAvailability.AVAILABLE,
            AIRouteRejectionReason.UNAVAILABLE,
        ),
        (
            _QUALIFICATION_RANK[candidate.qualification]
            < _QUALIFICATION_RANK[requirements.minimum_qualification],
            AIRouteRejectionReason.QUALIFICATION_INSUFFICIENT,
        ),
        (
            _GUARANTEE_RANK[candidate.structured_output]
            < _GUARANTEE_RANK[requirements.minimum_structured_output],
            AIRouteRejectionReason.STRUCTURED_OUTPUT_INSUFFICIENT,
        ),
        (
            requirements.tools_required and not candidate.supports_tools,
            AIRouteRejectionReason.TOOLS_UNSUPPORTED,
        ),
        (
            candidate.maximum_context_tokens < requirements.minimum_context_tokens,
            AIRouteRejectionReason.CONTEXT_TOO_SMALL,
        ),
        (
            not requirements.required_modalities.issubset(candidate.modalities),
            AIRouteRejectionReason.MODALITY_UNSUPPORTED,
        ),
        (
            _SENSITIVITY_RANK[candidate.maximum_data_sensitivity]
            < _SENSITIVITY_RANK[requirements.data_sensitivity],
            AIRouteRejectionReason.PRIVACY_UNSUPPORTED,
        ),
        (
            candidate.retention_days > requirements.maximum_retention_days,
            AIRouteRejectionReason.RETENTION_EXCEEDED,
        ),
        (
            candidate.region not in requirements.allowed_regions,
            AIRouteRejectionReason.REGION_UNSUPPORTED,
        ),
        (
            candidate.estimated_cost_micro_units > requirements.maximum_cost_micro_units,
            AIRouteRejectionReason.COST_EXCEEDED,
        ),
        (
            candidate.estimated_latency_milliseconds > requirements.maximum_latency_milliseconds,
            AIRouteRejectionReason.LATENCY_EXCEEDED,
        ),
        (
            candidate.quality_score < requirements.minimum_quality_score,
            AIRouteRejectionReason.QUALITY_INSUFFICIENT,
        ),
        (
            candidate.fallback_only and not requirements.fallback_allowed,
            AIRouteRejectionReason.FALLBACK_NOT_ALLOWED,
        ),
    )
    reasons.extend(reason for failed, reason in checks if failed)
    return tuple(reasons)


def _ranking_key(candidate: AIProviderCandidate) -> tuple[int, int, int, int, str, str]:
    return (
        -_QUALIFICATION_RANK[candidate.qualification],
        -candidate.quality_score,
        candidate.estimated_cost_micro_units,
        candidate.estimated_latency_milliseconds,
        candidate.model.provider_key,
        candidate.model.model_key,
    )
