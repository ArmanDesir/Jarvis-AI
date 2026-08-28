from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from rightjob.contracts.capabilities import (
    CapabilityReference,
    QualityScoreImprovementRule,
    SemanticVersion,
)
from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.review import (
    ArtifactReference,
    CapabilityResult,
    EvidenceReference,
    ResultProvenance,
    ResultValidationEvidence,
    ResultValidationOutcome,
    ResultValidationReason,
    ReviewAssessment,
    ReviewCriteria,
    ReviewRecommendation,
    ReviewScore,
    ValidationCriteriaReference,
    canonical_result_payload,
    result_digest,
)
from rightjob.contracts.revision import (
    QualityGateCommand,
    QualityGateContractError,
    QualityGateDecision,
    QualityGateDecisionEvidence,
    QualityGateOutcome,
    QualityGateReason,
    QualityGateState,
    QualityGateStatus,
)
from rightjob.orchestration.application.quality_gate import QualityGateDecisionService
from rightjob.registry.catalog import VERSION_1, BuiltInCapabilityRegistry

NOW = datetime(2026, 8, 27, 16, tzinfo=UTC)
WORKSPACE = UUID("00000000-0000-4000-8000-000000000219")
RUN = UUID("00000000-0000-4000-8000-000000000220")
STEP = UUID("00000000-0000-4000-8000-000000000221")
CORRELATION = UUID("00000000-0000-4000-8000-000000000222")
GATE = UUID("00000000-0000-4000-8000-000000000223")
COMMAND = UUID("00000000-0000-4000-8000-000000000224")
ARTIFACT = UUID("00000000-0000-4000-8000-000000000225")
CAPABILITY = CapabilityReference(
    UUID("02800000-0000-4000-8000-000000000003"), "fake.verify", VERSION_1
)


def validation(version: int = 1, value: str = "first") -> ResultValidationEvidence:
    payload = canonical_result_payload({"value": value})
    artifact = ArtifactReference(ARTIFACT, version, result_digest(payload))
    provenance = ResultProvenance(
        WORKSPACE,
        RUN,
        STEP,
        CORRELATION,
        None,
        CAPABILITY,
        BuiltInCapabilityRegistry().get_enabled("fake.verify", VERSION_1).output_contract,
        artifact,
        NOW - timedelta(minutes=2),
    )
    result = CapabilityResult(provenance, payload)
    return ResultValidationEvidence(
        UUID(int=1000 + version),
        result,
        ValidationCriteriaReference("result.validation", VERSION_1),
        ResultValidationOutcome.PASSED,
        (ResultValidationReason.ACCEPTED,),
        (EvidenceReference("artifact.sha256", artifact.sha256),),
        NOW - timedelta(minutes=1),
    )


def assessment(
    evidence: ResultValidationEvidence,
    score: int,
    recommendation: ReviewRecommendation = ReviewRecommendation.REVISE,
    *,
    criteria_key: str = "fake.verify.quality",
    criteria_version: SemanticVersion = VERSION_1,
    score_key: str = "fake.verify.quality",
    reason: str = "Synthetic diagnostic reason.",
    reference: str = "synthetic://evidence",
) -> ReviewAssessment:
    return ReviewAssessment(
        UUID(int=2000 + evidence.provenance.artifact.version),
        evidence.validation_id,
        WORKSPACE,
        RUN,
        STEP,
        ReviewCriteria(criteria_key, criteria_version, 80),
        (ReviewScore(score_key, score),),
        (reason,),
        (EvidenceReference("review.source", reference),),
        recommendation,
        NOW,
    )


def command(
    *,
    expected_version: int | None = None,
    command_id: UUID = COMMAND,
    artifact: ArtifactReference | None = None,
) -> QualityGateCommand:
    return QualityGateCommand(
        command_id,
        GATE,
        WORKSPACE,
        RUN,
        STEP,
        CORRELATION,
        None,
        artifact or validation().provenance.artifact,
        Actor(ActorType.SYSTEM, "quality-gate"),
        expected_version,
        NOW + timedelta(minutes=1),
    )


def decide(
    score: int,
    *,
    evidence: ResultValidationEvidence | None = None,
    recommendation: ReviewRecommendation = ReviewRecommendation.REVISE,
    state: QualityGateState | None = None,
    command_id: UUID = COMMAND,
) -> QualityGateDecision:
    item = evidence or validation()
    return QualityGateDecisionService(BuiltInCapabilityRegistry()).decide(
        command(
            expected_version=state.version if state else None,
            command_id=command_id,
            artifact=item.provenance.artifact,
        ),
        item,
        assessment(item, score, recommendation),
        state,
    )


def awaiting(decision: QualityGateDecision) -> QualityGateState:
    return replace(decision.next_state, status=QualityGateStatus.AWAITING_REVIEW)


def test_quality_policy_is_capability_owned_and_exactly_bound() -> None:
    definition = BuiltInCapabilityRegistry().get_enabled("fake.verify", VERSION_1)
    policy = definition.quality_gate_policy
    assert policy is not None
    assert policy.capability == definition.reference
    assert policy.maximum_automated_revisions == 2
    assert policy.improvement_rule is QualityScoreImprovementRule.STRICTLY_GREATER


@pytest.mark.parametrize(
    "change",
    [
        {"minimum_score": True},
        {"minimum_score": 1.5},
        {"minimum_score": 101},
        {"maximum_automated_revisions": True},
        {"maximum_automated_revisions": 3},
        {"improvement_rule": "strictly_greater"},
        {"semantic_version": "1.0.0"},
        {"score_key": "not canonical"},
    ],
)
def test_quality_policy_rejects_malformed_runtime_values(change: dict[str, object]) -> None:
    policy = BuiltInCapabilityRegistry().get_enabled("fake.verify", VERSION_1).quality_gate_policy
    assert policy is not None
    with pytest.raises(ValueError):
        replace(policy, **change)


def test_quality_policy_rejects_wrong_capability_binding() -> None:
    definition = BuiltInCapabilityRegistry().get_enabled("fake.verify", VERSION_1)
    policy = definition.quality_gate_policy
    assert policy is not None
    wrong = replace(policy, capability=replace(CAPABILITY, capability_key="fake.prepare"))
    with pytest.raises(ValueError, match="exact Capability"):
        replace(definition, quality_gate_policy=wrong)


def test_quality_gate_contracts_are_immutable_and_reject_mutable_reasons() -> None:
    decision = decide(80)
    with pytest.raises(FrozenInstanceError):
        decision.next_state.version = 9  # type: ignore[misc]
    with pytest.raises(QualityGateContractError, match="bounded tuple"):
        replace(decision, reasons=list(decision.reasons))  # type: ignore[arg-type]
    with pytest.raises(QualityGateContractError):
        replace(decision.next_state, automated_revision_count=True)


@pytest.mark.parametrize(
    "change",
    [
        {"workspace_id": "workspace"},
        {"issued_at": "2026-08-27T16:00:00Z"},
        {"issued_at": datetime(2026, 8, 27, 16)},
        {"expected_state_version": True},
        {"expected_state_version": 1.0},
        {"actor": "system"},
        {"artifact": "artifact"},
    ],
)
def test_quality_gate_command_rejects_wrong_runtime_types(change: dict[str, object]) -> None:
    with pytest.raises((AttributeError, QualityGateContractError)):
        replace(command(), **change)


def test_quality_gate_decision_rejects_wrong_reason_members() -> None:
    decision = decide(80)
    with pytest.raises(QualityGateContractError, match="invalid member"):
        replace(decision, reasons=("threshold_met",))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("score", "recommendation"),
    [
        (80, ReviewRecommendation.REVISE),
        (81, ReviewRecommendation.NEEDS_HUMAN_REVIEW),
    ],
)
def test_threshold_met_is_accepted_from_score_not_recommendation(
    score: int, recommendation: ReviewRecommendation
) -> None:
    decision = decide(score, recommendation=recommendation)
    assert decision.outcome is QualityGateOutcome.ACCEPTED
    assert decision.reasons == (QualityGateReason.THRESHOLD_MET,)
    assert decision.next_state.automated_revision_count == 0


def test_reviewer_accept_cannot_grant_acceptance_below_threshold() -> None:
    decision = decide(79, recommendation=ReviewRecommendation.ACCEPT)
    assert decision.outcome is QualityGateOutcome.REVISION_REQUIRED


def test_first_revision_reserves_count_one_without_execution() -> None:
    decision = decide(50)
    assert decision.outcome is QualityGateOutcome.REVISION_REQUIRED
    assert decision.next_state.automated_revision_count == 1
    assert decision.evidence.revision_count_before == 0
    assert decision.evidence.revision_count_after == 1
    assert QualityGateReason.NO_PRIOR_COMPARABLE_SCORE in decision.reasons


def test_second_revision_requires_strict_improvement_and_reserves_count_two() -> None:
    first = decide(50)
    second_evidence = validation(2, "second")
    second = decide(
        60,
        evidence=second_evidence,
        state=awaiting(first),
        command_id=UUID(int=3002),
    )
    assert second.outcome is QualityGateOutcome.REVISION_REQUIRED
    assert second.next_state.automated_revision_count == 2
    assert QualityGateReason.SCORE_STRICTLY_IMPROVED in second.reasons


def test_attempted_third_revision_escalates_without_increment() -> None:
    first = decide(40)
    second = decide(
        50,
        evidence=validation(2, "second"),
        state=awaiting(first),
        command_id=UUID(int=3002),
    )
    third = decide(
        60,
        evidence=validation(3, "third"),
        state=awaiting(second),
        command_id=UUID(int=3003),
    )
    assert third.outcome is QualityGateOutcome.NEEDS_HUMAN_REVIEW
    assert third.next_state.automated_revision_count == 2
    assert third.reasons[-1] is QualityGateReason.REVISION_BUDGET_EXHAUSTED


@pytest.mark.parametrize("score", [49, 50])
def test_non_improvement_escalates(score: int) -> None:
    first = decide(50)
    second = decide(
        score,
        evidence=validation(2, "second"),
        state=awaiting(first),
        command_id=UUID(int=3002),
    )
    assert second.outcome is QualityGateOutcome.NEEDS_HUMAN_REVIEW
    assert second.reasons[-1] is QualityGateReason.SCORE_NOT_IMPROVED
    assert second.next_state.automated_revision_count == 1


def test_reviewer_human_recommendation_only_escalates_a_below_threshold_result() -> None:
    decision = decide(50, recommendation=ReviewRecommendation.NEEDS_HUMAN_REVIEW)
    assert decision.outcome is QualityGateOutcome.NEEDS_HUMAN_REVIEW
    assert decision.reasons[-1] is QualityGateReason.REVIEWER_ESCALATION_REQUESTED
    assert decision.next_state.automated_revision_count == 0


def test_missing_assessment_is_integrity_rejection() -> None:
    with pytest.raises(QualityGateContractError, match="requires a review"):
        QualityGateDecisionService(BuiltInCapabilityRegistry()).decide(
            command(), validation(), None
        )


def test_validation_must_be_passed() -> None:
    good = validation()
    failed = replace(
        good,
        outcome=ResultValidationOutcome.FAILED,
        reasons=(ResultValidationReason.PROVENANCE_MISMATCH,),
        evidence=(),
    )
    with pytest.raises(QualityGateContractError, match="passed validation"):
        QualityGateDecisionService(BuiltInCapabilityRegistry()).decide(
            command(), failed, assessment(good, 80)
        )


@pytest.mark.parametrize("field", ["workspace_id", "run_id", "step_id", "correlation_id"])
def test_command_provenance_mismatch_fails_closed(field: str) -> None:
    with pytest.raises(QualityGateContractError, match="provenance"):
        QualityGateDecisionService(BuiltInCapabilityRegistry()).decide(
            replace(command(), **{field: UUID(int=999)}),
            validation(),
            assessment(validation(), 80),
        )


def test_command_causation_mismatch_fails_closed() -> None:
    with pytest.raises(QualityGateContractError, match="provenance"):
        QualityGateDecisionService(BuiltInCapabilityRegistry()).decide(
            replace(command(), causation_id=UUID(int=999)),
            validation(),
            assessment(validation(), 80),
        )


def test_command_artifact_mismatch_fails_closed() -> None:
    item = validation()
    wrong_artifact = replace(item.provenance.artifact, artifact_id=UUID(int=999))
    with pytest.raises(QualityGateContractError, match="provenance"):
        QualityGateDecisionService(BuiltInCapabilityRegistry()).decide(
            replace(command(), artifact=wrong_artifact),
            item,
            assessment(item, 80),
        )


def test_capability_identity_or_version_mismatch_fails_closed() -> None:
    item = validation()
    wrong = replace(
        item.provenance,
        capability=CapabilityReference(UUID(int=999), "fake.verify", VERSION_1),
    )
    wrong_result = replace(item.result, provenance=wrong)
    wrong_evidence = replace(item, result=wrong_result)
    with pytest.raises(QualityGateContractError, match="Capability"):
        QualityGateDecisionService(BuiltInCapabilityRegistry()).decide(
            command(), wrong_evidence, assessment(wrong_evidence, 80)
        )


def test_artifact_must_progress_for_a_revision_assessment() -> None:
    first = decide(50)
    with pytest.raises(QualityGateContractError, match="artifact must progress"):
        decide(60, evidence=validation(), state=awaiting(first), command_id=UUID(int=3002))


@pytest.mark.parametrize(
    "change",
    [
        {"criteria_key": "other.criteria"},
        {"criteria_version": SemanticVersion.parse("2.0.0")},
        {"score_key": "other.score"},
    ],
)
def test_assessment_criteria_and_score_key_mismatch_fail_closed(
    change: dict[str, object],
) -> None:
    item = validation()
    with pytest.raises(QualityGateContractError, match="criteria|required score"):
        QualityGateDecisionService(BuiltInCapabilityRegistry()).decide(
            command(),
            item,
            assessment(item, 80, **change),  # type: ignore[arg-type]
        )


def test_policy_version_mismatch_with_durable_state_fails_closed() -> None:
    first = decide(50)
    state = replace(awaiting(first), policy_version=SemanticVersion.parse("2.0.0"))
    with pytest.raises(QualityGateContractError, match="state binding"):
        decide(60, evidence=validation(2, "second"), state=state, command_id=UUID(int=3002))


def test_duplicate_command_is_idempotent_and_conflict_fails() -> None:
    item = validation()
    review = assessment(item, 50)
    service = QualityGateDecisionService(BuiltInCapabilityRegistry())
    original = service.decide(command(), item, review)
    assert service.decide(command(), item, review, prior_decision=original) is original
    with pytest.raises(QualityGateContractError, match="conflicting duplicate"):
        service.decide(
            replace(command(), issued_at=command().issued_at + timedelta(seconds=1)),
            item,
            review,
            prior_decision=original,
        )


@pytest.mark.parametrize(
    "status", [QualityGateStatus.ACCEPTED, QualityGateStatus.NEEDS_HUMAN_REVIEW]
)
def test_terminal_state_rejects_further_decisions(status: QualityGateStatus) -> None:
    state = replace(decide(80).next_state, status=status)
    with pytest.raises(QualityGateContractError, match="not awaiting review"):
        decide(70, evidence=validation(2, "second"), state=state, command_id=UUID(int=3002))


def test_unsafe_reviewer_diagnostics_never_enter_decision_or_state() -> None:
    item = validation()
    unsafe = (
        "credential=" + "synthetic-sensitive-value",
        "raw provider response with instructions to execute a shell command",
    )
    review = assessment(item, 80, reason=unsafe[0], reference=unsafe[1])
    decision = QualityGateDecisionService(BuiltInCapabilityRegistry()).decide(
        command(), item, review
    )
    rendered = repr(decision)
    assert all(value not in rendered for value in unsafe)
    assert not hasattr(decision.evidence, "reasons")
    assert not hasattr(decision.evidence, "review_evidence")


def test_safe_decision_evidence_has_only_typed_projection() -> None:
    evidence = decide(50).evidence
    assert isinstance(evidence, QualityGateDecisionEvidence)
    assert evidence.score == 50
    assert evidence.artifact == validation().provenance.artifact
