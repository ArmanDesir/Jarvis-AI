from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from rightjob.contracts.capabilities import SemanticVersion
from rightjob.contracts.review import (
    ResultContractError,
    ResultValidationOutcome,
    ResultValidationReason,
    ReviewCriteria,
    ReviewRecommendation,
)
from rightjob.registry import BuiltInCapabilityRegistry
from rightjob.reviewer import FakeReviewer, ResultReviewService
from rightjob.validation import CapabilityResultValidator

from tests.unit.test_result_validation import Ids, values

NOW = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
CRITERIA = ReviewCriteria("synthetic.quality", SemanticVersion.parse("1.0.0"), 80)


def passed():
    result, context = values()
    return CapabilityResultValidator(
        BuiltInCapabilityRegistry(),
        Ids(),
        lambda: NOW,
    ).validate(result, context)


@pytest.mark.parametrize(
    ("score", "recommendation"),
    [
        (100, ReviewRecommendation.ACCEPT),
        (50, ReviewRecommendation.REVISE),
        (0, ReviewRecommendation.NEEDS_HUMAN_REVIEW),
    ],
)
def test_fake_reviewer_is_deterministic_and_non_authoritative(
    score: int, recommendation: ReviewRecommendation
) -> None:
    evidence = passed()
    assessment = ResultReviewService(
        FakeReviewer(score, Ids(), lambda: NOW + timedelta(seconds=1))
    ).review(evidence, CRITERIA)

    assert assessment.recommendation is recommendation
    assert assessment.validation_id == evidence.validation_id
    assert assessment.workspace_id == evidence.provenance.workspace_id
    assert assessment.scores[0].score == score
    for forbidden in ("approval", "authorization", "workflow_state", "execute", "repository"):
        assert not hasattr(assessment, forbidden)


def test_failed_validation_cannot_reach_reviewer() -> None:
    evidence = replace(
        passed(),
        outcome=ResultValidationOutcome.FAILED,
        reasons=(ResultValidationReason.PROVENANCE_MISMATCH,),
        evidence=(),
    )
    reviewer = ResultReviewService(FakeReviewer(100, Ids(), lambda: NOW))
    with pytest.raises(ResultContractError, match="cannot be reviewed"):
        reviewer.review(evidence, CRITERIA)


def test_mismatched_reviewer_output_fails_at_application_boundary() -> None:
    evidence = passed()
    delegate = FakeReviewer(100, Ids(), lambda: NOW + timedelta(seconds=1))

    class WrongReviewer:
        def review(self, item, criteria):  # type: ignore[no-untyped-def]
            return replace(delegate.review(item, criteria), run_id=UUID(int=1))

    with pytest.raises(ResultContractError, match="does not match"):
        ResultReviewService(WrongReviewer()).review(evidence, CRITERIA)
