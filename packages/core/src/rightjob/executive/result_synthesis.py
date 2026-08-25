"""Presentation-only synthesis of validated Capability result evidence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from rightjob.contracts.review import (
    ExecutiveResultPresentation,
    ExecutiveReviewSummary,
    ResultContractError,
    ResultValidationEvidence,
    ResultValidationOutcome,
    ReviewAssessment,
)

Clock = Callable[[], datetime]


class ExecutiveResultSynthesisService:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def synthesize(
        self,
        evidence: ResultValidationEvidence,
        review: ReviewAssessment | None = None,
    ) -> ExecutiveResultPresentation:
        if evidence.outcome is not ResultValidationOutcome.PASSED:
            raise ResultContractError("only validated results can be presented")
        provenance = evidence.provenance
        if review is not None and (
            review.validation_id != evidence.validation_id
            or review.workspace_id != provenance.workspace_id
            or review.run_id != provenance.run_id
            or review.step_id != provenance.step_id
            or review.assessed_at < evidence.validated_at
        ):
            raise ResultContractError("review does not match validated result")
        presented_at = self._clock()
        latest_evidence_at = review.assessed_at if review is not None else evidence.validated_at
        if presented_at < latest_evidence_at:
            raise ResultContractError("presentation timestamp precedes its evidence")
        return ExecutiveResultPresentation(
            provenance.workspace_id,
            provenance.run_id,
            provenance.step_id,
            provenance.correlation_id,
            provenance.causation_id,
            provenance.capability,
            provenance.output_contract,
            provenance.artifact,
            evidence.validation_id,
            evidence.evidence,
            (
                ExecutiveReviewSummary(
                    review.criteria.criteria_key,
                    review.criteria.semantic_version,
                    review.scores,
                    review.recommendation,
                )
                if review is not None
                else None
            ),
            presented_at,
        )
