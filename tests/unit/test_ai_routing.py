from __future__ import annotations

from collections.abc import Sequence
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta
from itertools import permutations
from uuid import UUID

import pytest
from rightjob.ai_router import DeterministicAICapabilityRouter
from rightjob.contracts.ai import AIModelReference
from rightjob.contracts.ai_routing import (
    AIModality,
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
from rightjob.contracts.capabilities import SemanticVersion
from rightjob.contracts.events import DataSensitivity

NOW = datetime(2026, 8, 27, 12, tzinfo=UTC)
ROUTE_ID = UUID("00000000-0000-4000-8000-000000000181")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000182")


def requirements(**changes: object) -> AIRouteRequirements:
    values: dict[str, object] = {
        "route_request_id": ROUTE_ID,
        "workspace_id": WORKSPACE_ID,
        "evaluated_at": NOW,
        "minimum_structured_output": AIStructuredOutputGuarantee.STRICT_SUBSET,
        "tools_required": True,
        "minimum_context_tokens": 8_000,
        "required_modalities": frozenset({AIModality.TEXT}),
        "data_sensitivity": DataSensitivity.CONFIDENTIAL,
        "maximum_retention_days": 30,
        "allowed_regions": frozenset({"us-east", "eu-west"}),
        "maximum_cost_micro_units": 10_000,
        "maximum_latency_milliseconds": 2_000,
        "minimum_quality_score": 70,
        "minimum_qualification": AIProviderQualification.LIMITED,
        "fallback_allowed": True,
    }
    values.update(changes)
    return AIRouteRequirements(**values)  # type: ignore[arg-type]


def candidate(
    provider: str = "alpha", model: str = "model-a", **changes: object
) -> AIProviderCandidate:
    values: dict[str, object] = {
        "model": AIModelReference(provider, model),
        "profile_version": SemanticVersion.parse("1.0.0"),
        "evidence_observed_at": NOW - timedelta(hours=1),
        "evidence_expires_at": NOW + timedelta(hours=1),
        "qualification": AIProviderQualification.QUALIFIED,
        "availability": AIProviderAvailability.AVAILABLE,
        "structured_output": AIStructuredOutputGuarantee.CANONICAL_CONTRACT,
        "supports_tools": True,
        "maximum_context_tokens": 16_000,
        "modalities": frozenset({AIModality.TEXT, AIModality.IMAGE}),
        "maximum_data_sensitivity": DataSensitivity.RESTRICTED,
        "retention_days": 0,
        "region": "us-east",
        "estimated_cost_micro_units": 5_000,
        "estimated_latency_milliseconds": 1_000,
        "quality_score": 90,
        "fallback_only": False,
    }
    values.update(changes)
    return AIProviderCandidate(**values)  # type: ignore[arg-type]


def rejection_reasons(
    item: AIProviderCandidate, request: AIRouteRequirements | None = None
) -> tuple[AIRouteRejectionReason, ...]:
    decision = DeterministicAICapabilityRouter().route(request or requirements(), (item,))
    assert decision.outcome is AIRouteOutcome.UNAVAILABLE
    return decision.rejections[0].reasons


def test_contracts_are_immutable_and_collections_are_immutable() -> None:
    request = requirements()
    item = candidate()
    with pytest.raises(FrozenInstanceError):
        request.fallback_allowed = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        item.quality_score = 1  # type: ignore[misc]
    assert isinstance(request.allowed_regions, frozenset)
    assert isinstance(item.modalities, frozenset)


@pytest.mark.parametrize(
    "change",
    [
        {"required_modalities": {AIModality.TEXT}},
        {"allowed_regions": {"us-east"}},
        {"required_modalities": frozenset({"text"})},
        {"allowed_regions": frozenset({1})},
    ],
)
def test_requirements_reject_mutable_or_wrong_collection_members(
    change: dict[str, object],
) -> None:
    with pytest.raises(AIRoutingContractError):
        requirements(**change)


@pytest.mark.parametrize(
    "change",
    [
        {"modalities": {AIModality.TEXT}},
        {"modalities": [AIModality.TEXT]},
        {"modalities": frozenset({"text"})},
    ],
)
def test_candidate_rejects_mutable_or_wrong_collection_members(
    change: dict[str, object],
) -> None:
    with pytest.raises(AIRoutingContractError):
        candidate(**change)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"route_request_id": UUID(int=0)}, "route_request_id"),
        ({"evaluated_at": NOW.replace(tzinfo=None)}, "timezone-aware"),
        ({"minimum_context_tokens": 0}, "minimum_context_tokens"),
        ({"required_modalities": frozenset()}, "required_modalities"),
        ({"allowed_regions": frozenset({"US EAST"})}, "region"),
        ({"maximum_cost_micro_units": -1}, "maximum_cost"),
        ({"maximum_latency_milliseconds": 0}, "maximum_latency"),
        ({"minimum_quality_score": 101}, "minimum_quality"),
        ({"minimum_structured_output": "strict_subset"}, "minimum_structured_output"),
        ({"tools_required": 1}, "tools_required"),
        ({"minimum_context_tokens": 1.0}, "minimum_context_tokens"),
        ({"minimum_context_tokens": True}, "minimum_context_tokens"),
        ({"data_sensitivity": "confidential"}, "data_sensitivity"),
        ({"minimum_qualification": "limited"}, "minimum_qualification"),
        ({"fallback_allowed": 1}, "fallback_allowed"),
    ],
)
def test_requirement_identifiers_timestamps_and_bounds_fail_closed(
    change: dict[str, object], message: str
) -> None:
    with pytest.raises(AIRoutingContractError, match=message):
        requirements(**change)


@pytest.mark.parametrize(
    "change",
    [
        {"profile_version": SemanticVersion(-1, 0, 0)},
        {"profile_version": SemanticVersion(1, 0, 0, ["rc"])},  # type: ignore[arg-type]
        {"evidence_expires_at": NOW - timedelta(hours=2)},
        {"maximum_context_tokens": 0},
        {"modalities": frozenset()},
        {"retention_days": -1},
        {"region": "US EAST"},
        {"estimated_cost_micro_units": -1},
        {"estimated_latency_milliseconds": 0},
        {"quality_score": 101},
        {"qualification": "qualified"},
        {"availability": "available"},
        {"structured_output": "canonical_contract"},
        {"maximum_data_sensitivity": "restricted"},
        {"supports_tools": 1},
        {"fallback_only": 0},
        {"estimated_cost_micro_units": 1.5},
        {"estimated_latency_milliseconds": True},
        {"quality_score": float("nan")},
        {"quality_score": float("inf")},
        {"quality_score": float("-inf")},
    ],
)
def test_candidate_versions_timestamps_and_bounds_fail_closed(change: dict[str, object]) -> None:
    with pytest.raises(AIRoutingContractError):
        candidate(**change)  # type: ignore[arg-type]


def test_candidate_models_must_be_unique() -> None:
    with pytest.raises(AIRoutingContractError, match="unique"):
        DeterministicAICapabilityRouter().route(requirements(), (candidate(), candidate()))


def test_candidate_snapshot_size_is_bounded() -> None:
    candidates = tuple(candidate("provider", f"model-{index}") for index in range(129))
    with pytest.raises(AIRoutingContractError, match="maximum size"):
        DeterministicAICapabilityRouter().route(requirements(), candidates)


class MutableCandidateSequence(Sequence[AIProviderCandidate]):
    def __init__(self, value: AIProviderCandidate) -> None:
        self.values = [value]

    def __getitem__(self, index: int) -> AIProviderCandidate:
        return self.values[index]

    def __len__(self) -> int:
        return len(self.values)


@pytest.mark.parametrize(
    "snapshot",
    [
        [candidate()],
        {candidate()},
        (item for item in (candidate(),)),
        MutableCandidateSequence(candidate()),
    ],
)
def test_candidate_snapshot_must_be_an_exact_tuple(snapshot: object) -> None:
    with pytest.raises(AIRoutingContractError, match="must be a tuple"):
        DeterministicAICapabilityRouter().route(
            requirements(),
            snapshot,  # type: ignore[arg-type]
        )


def test_candidate_snapshot_rejects_wrong_tuple_members() -> None:
    with pytest.raises(AIRoutingContractError, match="invalid member"):
        DeterministicAICapabilityRouter().route(
            requirements(),
            (object(),),  # type: ignore[arg-type]
        )


def test_rejection_and_decision_collections_require_exact_tuples_and_members() -> None:
    model = candidate().model
    with pytest.raises(AIRoutingContractError, match="reasons must be a tuple"):
        AIProviderCandidateRejection(
            model,
            [AIRouteRejectionReason.UNAVAILABLE],  # type: ignore[arg-type]
        )
    with pytest.raises(AIRoutingContractError, match="invalid member"):
        AIProviderCandidateRejection(model, ("unavailable",))  # type: ignore[arg-type]
    with pytest.raises(AIRoutingContractError, match="rejections must be a tuple"):
        AIRouteDecision(ROUTE_ID, AIRouteOutcome.UNAVAILABLE, None, [])  # type: ignore[arg-type]
    with pytest.raises(AIRoutingContractError, match="invalid member"):
        AIRouteDecision(ROUTE_ID, AIRouteOutcome.UNAVAILABLE, None, (object(),))  # type: ignore[arg-type]


def test_nested_contract_and_decision_types_are_checked_at_runtime() -> None:
    with pytest.raises(AIRoutingContractError, match="AIModelReference"):
        replace(candidate(), model="alpha/model")  # type: ignore[arg-type]
    with pytest.raises(AIRoutingContractError, match="SemanticVersion"):
        replace(candidate(), profile_version="1.0.0")  # type: ignore[arg-type]
    with pytest.raises(AIRoutingContractError, match="datetime"):
        replace(candidate(), evidence_observed_at="2026-08-27T12:00:00Z")  # type: ignore[arg-type]
    with pytest.raises(AIRoutingContractError, match="outcome"):
        AIRouteDecision(ROUTE_ID, "unavailable", None)  # type: ignore[arg-type]


def test_unsafe_models_are_rejected_in_rejection_and_selected_decision_contracts() -> None:
    unsafe = AIModelReference("alpha", "system-message/prompt")
    with pytest.raises(AIRoutingContractError, match="safe routing identity"):
        AIProviderCandidateRejection(unsafe, (AIRouteRejectionReason.UNAVAILABLE,))
    with pytest.raises(AIRoutingContractError, match="safe routing identity"):
        AIRouteDecision(ROUTE_ID, AIRouteOutcome.SELECTED, unsafe)


@pytest.mark.parametrize(
    ("change", "request_change", "reason"),
    [
        ({"evidence_expires_at": NOW}, {}, AIRouteRejectionReason.STALE_EVIDENCE),
        (
            {"availability": AIProviderAvailability.UNAVAILABLE},
            {},
            AIRouteRejectionReason.UNAVAILABLE,
        ),
        (
            {"qualification": AIProviderQualification.UNVERIFIED},
            {},
            AIRouteRejectionReason.QUALIFICATION_INSUFFICIENT,
        ),
        (
            {"structured_output": AIStructuredOutputGuarantee.NONE},
            {},
            AIRouteRejectionReason.STRUCTURED_OUTPUT_INSUFFICIENT,
        ),
        ({"supports_tools": False}, {}, AIRouteRejectionReason.TOOLS_UNSUPPORTED),
        ({"maximum_context_tokens": 7_999}, {}, AIRouteRejectionReason.CONTEXT_TOO_SMALL),
        (
            {"modalities": frozenset({AIModality.IMAGE})},
            {},
            AIRouteRejectionReason.MODALITY_UNSUPPORTED,
        ),
        (
            {"maximum_data_sensitivity": DataSensitivity.INTERNAL},
            {},
            AIRouteRejectionReason.PRIVACY_UNSUPPORTED,
        ),
        ({"retention_days": 31}, {}, AIRouteRejectionReason.RETENTION_EXCEEDED),
        ({"region": "ap-south"}, {}, AIRouteRejectionReason.REGION_UNSUPPORTED),
        ({"estimated_cost_micro_units": 10_001}, {}, AIRouteRejectionReason.COST_EXCEEDED),
        (
            {"estimated_latency_milliseconds": 2_001},
            {},
            AIRouteRejectionReason.LATENCY_EXCEEDED,
        ),
        ({"quality_score": 69}, {}, AIRouteRejectionReason.QUALITY_INSUFFICIENT),
        (
            {"fallback_only": True},
            {"fallback_allowed": False},
            AIRouteRejectionReason.FALLBACK_NOT_ALLOWED,
        ),
    ],
)
def test_each_mandatory_constraint_rejects_independently(
    change: dict[str, object],
    request_change: dict[str, object],
    reason: AIRouteRejectionReason,
) -> None:
    assert rejection_reasons(
        candidate(**change),  # type: ignore[arg-type]
        requirements(**request_change),
    ) == (reason,)


def test_future_dated_evidence_fails_closed() -> None:
    future = candidate(
        evidence_observed_at=NOW + timedelta(microseconds=1),
        evidence_expires_at=NOW + timedelta(hours=1),
    )
    assert rejection_reasons(future) == (AIRouteRejectionReason.STALE_EVIDENCE,)


def test_evidence_expiry_is_exclusive_and_stays_stale_beyond_boundary() -> None:
    at_expiry = candidate(evidence_expires_at=NOW)
    beyond_expiry = candidate(evidence_expires_at=NOW - timedelta(microseconds=1))
    assert rejection_reasons(at_expiry) == (AIRouteRejectionReason.STALE_EVIDENCE,)
    assert rejection_reasons(beyond_expiry) == (AIRouteRejectionReason.STALE_EVIDENCE,)


def test_zero_and_maximum_numeric_boundaries_are_accepted() -> None:
    request = requirements(
        minimum_context_tokens=10_000_000,
        maximum_retention_days=0,
        maximum_cost_micro_units=1_000_000_000_000,
        maximum_latency_milliseconds=300_000,
        minimum_quality_score=0,
    )
    item = candidate(
        maximum_context_tokens=10_000_000,
        retention_days=0,
        estimated_cost_micro_units=1_000_000_000_000,
        estimated_latency_milliseconds=300_000,
        quality_score=0,
    )
    assert DeterministicAICapabilityRouter().route(request, (item,)).selected_model == item.model


def test_multiple_rejection_reasons_have_fixed_order() -> None:
    item = candidate(
        availability=AIProviderAvailability.UNKNOWN,
        supports_tools=False,
        quality_score=1,
        fallback_only=True,
    )
    assert rejection_reasons(item, requirements(fallback_allowed=False)) == (
        AIRouteRejectionReason.UNAVAILABLE,
        AIRouteRejectionReason.TOOLS_UNSUPPORTED,
        AIRouteRejectionReason.QUALITY_INSUFFICIENT,
        AIRouteRejectionReason.FALLBACK_NOT_ALLOWED,
    )


def test_rejected_candidates_and_reasons_are_stable_across_permutations() -> None:
    items = (
        candidate("zeta", "unavailable", availability=AIProviderAvailability.UNAVAILABLE),
        candidate("alpha", "low-quality", quality_score=1),
        candidate("beta", "multiple", supports_tools=False, retention_days=31),
    )
    outputs = {
        DeterministicAICapabilityRouter().route(requirements(), order).rejections
        for order in permutations(items)
    }
    assert len(outputs) == 1
    rejections = next(iter(outputs))
    assert tuple(item.model.provider_key for item in rejections) == ("alpha", "beta", "zeta")
    assert rejections[1].reasons == (
        AIRouteRejectionReason.TOOLS_UNSUPPORTED,
        AIRouteRejectionReason.RETENTION_EXCEEDED,
    )


def test_ranking_is_stable_and_independent_of_input_order() -> None:
    candidates = (
        candidate("zeta", "cheap", quality_score=90, estimated_cost_micro_units=1),
        candidate("alpha", "best", quality_score=95, estimated_cost_micro_units=9_000),
        candidate(
            "beta",
            "limited",
            qualification=AIProviderQualification.LIMITED,
            quality_score=100,
        ),
    )
    selected = {
        DeterministicAICapabilityRouter().route(requirements(), order).selected_model
        for order in permutations(candidates)
    }
    assert selected == {AIModelReference("alpha", "best")}


def test_tie_breaks_by_provider_then_model_key() -> None:
    choices = (candidate("beta", "a"), candidate("alpha", "z"), candidate("alpha", "a"))
    decision = DeterministicAICapabilityRouter().route(requirements(), choices)
    assert decision.selected_model == AIModelReference("alpha", "a")


def test_no_eligible_candidate_returns_typed_unavailable() -> None:
    decision = DeterministicAICapabilityRouter().route(requirements(), ())
    assert decision.outcome is AIRouteOutcome.UNAVAILABLE
    assert decision.selected_model is None
    assert decision.rejections == ()


def test_limited_groq_snapshot_cannot_satisfy_canonical_contract() -> None:
    groq = candidate(
        "groq",
        "openai/gpt-oss-20b",
        qualification=AIProviderQualification.LIMITED,
        structured_output=AIStructuredOutputGuarantee.STRICT_SUBSET,
    )
    reasons = rejection_reasons(
        groq,
        requirements(minimum_structured_output=AIStructuredOutputGuarantee.CANONICAL_CONTRACT),
    )
    assert reasons == (AIRouteRejectionReason.STRUCTURED_OUTPUT_INSUFFICIENT,)


def test_limited_groq_snapshot_can_satisfy_compatible_subset_requirements() -> None:
    groq = candidate(
        "groq",
        "openai/gpt-oss-20b",
        qualification=AIProviderQualification.LIMITED,
        structured_output=AIStructuredOutputGuarantee.STRICT_SUBSET,
    )
    decision = DeterministicAICapabilityRouter().route(requirements(), (groq,))
    assert decision.outcome is AIRouteOutcome.SELECTED
    assert decision.selected_model == groq.model


@pytest.mark.parametrize(
    "unsafe_model_key",
    [
        "api" + "_key=" + "synthetic-value",
        "sk-supersecretvalue",
        "model-supersecretcredentialvalue",
        '{"choices":[{"message":"raw provider content"}]}',
        "ignore previous instructions",
        "system-message/prompt",
        "model;rm-rf",
        "model\nraw-content",
    ],
)
def test_routing_model_identity_rejects_sensitive_or_payload_content(
    unsafe_model_key: str,
) -> None:
    with pytest.raises(AIRoutingContractError, match="safe routing identity"):
        candidate(model=unsafe_model_key)


def test_routing_model_identity_accepts_established_and_normal_model_keys() -> None:
    for model_key in ("openai/gpt-oss-20b", "gpt-4.1-mini", "model_v2:latest"):
        assert candidate(model=model_key).model.model_key == model_key


def test_fallback_eligibility_never_weakens_other_constraints() -> None:
    fallback = candidate(fallback_only=True, supports_tools=False)
    assert rejection_reasons(fallback) == (AIRouteRejectionReason.TOOLS_UNSUPPORTED,)


def test_route_decision_contains_no_authority_or_sensitive_fields() -> None:
    names = {
        field.name
        for field in fields(type(DeterministicAICapabilityRouter().route(requirements(), ())))
    }
    forbidden = {
        "approval",
        "authorization",
        "policy",
        "credential",
        "api_key",
        "prompt",
        "provider_response",
        "retry",
        "executable",
        "workflow_state",
    }
    assert names.isdisjoint(forbidden)


def test_replacing_candidate_snapshot_changes_only_routing_decision() -> None:
    router = DeterministicAICapabilityRouter()
    first = candidate("alpha", "one")
    second = replace(first, model=AIModelReference("beta", "two"))
    first_decision = router.route(requirements(), (first,))
    second_decision = router.route(requirements(), (second,))
    assert first_decision.route_request_id == second_decision.route_request_id
    assert first_decision.selected_model == first.model
    assert second_decision.selected_model == second.model
