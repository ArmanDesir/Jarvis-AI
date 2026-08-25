"""Non-authoritative review application boundary and deterministic fake."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from rightjob.contracts.review import (
    EvidenceReference,
    ResultContractError,
    ResultValidationEvidence,
    ResultValidationOutcome,
    ReviewAssessment,
    ReviewCriteria,
    Reviewer,
    ReviewRecommendation,
    ReviewScore,
)

IdFactory = Callable[[], UUID]
Clock = Callable[[], datetime]


class ResultReviewService:
    """Enforces validation-before-review and delegates assessment only."""

    def __init__(self, reviewer: Reviewer) -> None:
        self._reviewer = reviewer

    def review(
        self, evidence: ResultValidationEvidence, criteria: ReviewCriteria
    ) -> ReviewAssessment:
        if evidence.outcome is not ResultValidationOutcome.PASSED:
            raise ResultContractError("failed results cannot be reviewed")
        assessment = self._reviewer.review(evidence, criteria)
        provenance = evidence.provenance
        if (
            assessment.validation_id != evidence.validation_id
            or assessment.workspace_id != provenance.workspace_id
            or assessment.run_id != provenance.run_id
            or assessment.step_id != provenance.step_id
            or assessment.criteria != criteria
            or assessment.assessed_at < evidence.validated_at
        ):
            raise ResultContractError("review assessment does not match validated evidence")
        return assessment


class FakeReviewer:
    """Deterministic assessment fake with no provider, state, or authority access."""

    def __init__(self, score: int, id_factory: IdFactory, clock: Clock) -> None:
        if not 0 <= score <= 100:
            raise ValueError("fake review score must be between 0 and 100")
        self._score = score
        self._id = id_factory
        self._clock = clock

    def review(
        self, evidence: ResultValidationEvidence, criteria: ReviewCriteria
    ) -> ReviewAssessment:
        if evidence.outcome is not ResultValidationOutcome.PASSED:
            raise ResultContractError("fake reviewer requires passed validation")
        if self._score >= criteria.minimum_score:
            recommendation = ReviewRecommendation.ACCEPT
            reason = "Synthetic result meets the declared review threshold."
        elif self._score > 0:
            recommendation = ReviewRecommendation.REVISE
            reason = "Synthetic result is below the declared review threshold."
        else:
            recommendation = ReviewRecommendation.NEEDS_HUMAN_REVIEW
            reason = "Synthetic result requires human review."
        provenance = evidence.provenance
        return ReviewAssessment(
            self._id(),
            evidence.validation_id,
            provenance.workspace_id,
            provenance.run_id,
            provenance.step_id,
            criteria,
            (ReviewScore(criteria.criteria_key, self._score),),
            (reason,),
            (EvidenceReference("validation.id", str(evidence.validation_id)),),
            recommendation,
            self._clock(),
        )
