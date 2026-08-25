"""Deterministic validation of immutable Capability results."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from rightjob.contracts.capabilities import CapabilityCatalog, SemanticVersion
from rightjob.contracts.review import (
    CapabilityResult,
    EvidenceReference,
    ResultValidationContext,
    ResultValidationEvidence,
    ResultValidationOutcome,
    ResultValidationReason,
    ValidationCriteriaReference,
)

IdFactory = Callable[[], UUID]
Clock = Callable[[], datetime]

RESULT_VALIDATION_CRITERIA = ValidationCriteriaReference(
    "capability.result.validation", SemanticVersion.parse("1.0.0")
)


class CapabilityResultValidator:
    def __init__(
        self, capabilities: CapabilityCatalog, id_factory: IdFactory, clock: Clock
    ) -> None:
        self._capabilities = capabilities
        self._id = id_factory
        self._clock = clock

    def validate(
        self, result: CapabilityResult, context: ResultValidationContext
    ) -> ResultValidationEvidence:
        validated_at = self._clock()
        provenance = result.provenance
        reasons: list[ResultValidationReason] = []
        if (
            provenance.workspace_id != context.workspace_id
            or provenance.run_id != context.run_id
            or provenance.step_id != context.step_id
            or provenance.correlation_id != context.correlation_id
            or provenance.causation_id != context.causation_id
        ):
            reasons.append(ResultValidationReason.PROVENANCE_MISMATCH)

        try:
            capability = self._capabilities.get_enabled(
                context.capability.capability_key, context.capability.semantic_version
            )
        except LookupError:
            capability = None
            reasons.append(ResultValidationReason.CAPABILITY_UNAVAILABLE)
        if capability is not None and (
            capability.reference != context.capability
            or provenance.capability != capability.reference
        ):
            reasons.append(ResultValidationReason.CAPABILITY_MISMATCH)
        if capability is not None and (
            context.output_contract != capability.output_contract
            or provenance.output_contract != capability.output_contract
        ):
            reasons.append(ResultValidationReason.OUTPUT_CONTRACT_MISMATCH)
        if provenance.artifact != context.artifact:
            reasons.append(ResultValidationReason.ARTIFACT_MISMATCH)
        if provenance.produced_at > validated_at:
            reasons.append(ResultValidationReason.INVALID_TIMESTAMP)
        if len(result.payload_json) > context.output_contract.maximum_payload_bytes:
            reasons.append(ResultValidationReason.PAYLOAD_TOO_LARGE)

        unique_reasons = tuple(dict.fromkeys(reasons))
        if unique_reasons:
            return ResultValidationEvidence(
                self._id(),
                result,
                RESULT_VALIDATION_CRITERIA,
                ResultValidationOutcome.FAILED,
                unique_reasons,
                (),
                validated_at,
            )
        return ResultValidationEvidence(
            self._id(),
            result,
            RESULT_VALIDATION_CRITERIA,
            ResultValidationOutcome.PASSED,
            (ResultValidationReason.ACCEPTED,),
            (
                EvidenceReference("artifact.sha256", context.artifact.sha256),
                EvidenceReference(
                    "capability.version",
                    f"{context.capability.capability_key}@{context.capability.semantic_version}",
                ),
                EvidenceReference(
                    "output.contract",
                    f"{context.output_contract.contract_key}@{context.output_contract.semantic_version}",
                ),
            ),
            validated_at,
        )
