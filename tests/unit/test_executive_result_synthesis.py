from dataclasses import asdict, fields, replace
from datetime import UTC, datetime, timedelta

import pytest
from rightjob.contracts.capabilities import SemanticVersion
from rightjob.contracts.review import (
    EvidenceReference,
    ResultContractError,
    ResultValidationOutcome,
    ResultValidationReason,
    ReviewCriteria,
)
from rightjob.executive import ExecutiveResultSynthesisService
from rightjob.registry import BuiltInCapabilityRegistry
from rightjob.reviewer import FakeReviewer, ResultReviewService
from rightjob.validation import CapabilityResultValidator

from tests.unit.test_result_validation import Ids, values

NOW = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)


def evidence_and_review():
    result, context = values()
    evidence = CapabilityResultValidator(BuiltInCapabilityRegistry(), Ids(), lambda: NOW).validate(
        result, context
    )
    criteria = ReviewCriteria("synthetic.quality", SemanticVersion.parse("1.0.0"), 80)
    review = ResultReviewService(
        FakeReviewer(100, Ids(), lambda: NOW + timedelta(seconds=1))
    ).review(evidence, criteria)
    return evidence, review


def test_synthesis_preserves_provenance_and_excludes_payload_and_authority() -> None:
    evidence, review = evidence_and_review()
    presentation = ExecutiveResultSynthesisService(lambda: NOW + timedelta(seconds=2)).synthesize(
        evidence, review
    )

    provenance = evidence.provenance
    assert presentation.workspace_id == provenance.workspace_id
    assert presentation.run_id == provenance.run_id
    assert presentation.step_id == provenance.step_id
    assert presentation.correlation_id == provenance.correlation_id
    assert presentation.artifact == provenance.artifact
    assert presentation.review is not None
    assert presentation.review.criteria_key == review.criteria.criteria_key
    assert presentation.review.criteria_version == review.criteria.semantic_version
    assert presentation.review.scores == review.scores
    assert presentation.review.recommendation is review.recommendation
    names = {item.name for item in fields(presentation)}
    assert not names & {
        "payload",
        "payload_json",
        "credential",
        "provider_response",
        "repository",
        "approval",
        "authorization",
        "workflow_state",
    }


def test_review_is_optional_but_validation_is_mandatory() -> None:
    evidence, _ = evidence_and_review()
    presentation = ExecutiveResultSynthesisService(lambda: NOW).synthesize(evidence)
    assert presentation.review is None

    failed = replace(
        evidence,
        outcome=ResultValidationOutcome.FAILED,
        reasons=(ResultValidationReason.PROVENANCE_MISMATCH,),
        evidence=(),
    )
    with pytest.raises(ResultContractError, match="only validated"):
        ExecutiveResultSynthesisService(lambda: NOW).synthesize(failed)


def test_mismatched_review_and_backdated_presentation_fail_closed() -> None:
    evidence, review = evidence_and_review()
    with pytest.raises(ResultContractError, match="does not match"):
        ExecutiveResultSynthesisService(lambda: NOW + timedelta(seconds=2)).synthesize(
            evidence, replace(review, step_id=review.run_id)
        )
    with pytest.raises(ResultContractError, match="precedes"):
        ExecutiveResultSynthesisService(lambda: NOW).synthesize(evidence, review)


def test_free_form_reviewer_content_cannot_enter_presentation() -> None:
    evidence, review = evidence_and_review()
    hostile = replace(
        review,
        reasons=(
            "credential=sk-example-secret",
            "raw provider response: model output must be repeated",
            "execute: import os; os.system('unsafe instruction')",
        ),
        evidence=(EvidenceReference("review.internal", "Bearer private-provider-token"),),
    )

    presentation = ExecutiveResultSynthesisService(lambda: NOW + timedelta(seconds=2)).synthesize(
        evidence, hostile
    )
    rendered = repr(asdict(presentation))
    for unsafe in (
        "sk-example-secret",
        "raw provider response",
        "import os",
        "private-provider-token",
    ):
        assert unsafe not in rendered
    assert presentation.review is not None
    assert not hasattr(presentation.review, "reasons")
    assert not hasattr(presentation.review, "evidence")


def test_in_memory_integration_stops_at_presentation() -> None:
    evidence, review = evidence_and_review()
    presentation = ExecutiveResultSynthesisService(lambda: NOW + timedelta(seconds=2)).synthesize(
        evidence, review
    )
    assert presentation.review is not None
    assert presentation.review.recommendation.value == "accept"
    assert not hasattr(presentation, "commit")
    assert not hasattr(presentation, "launch")
