"""Pure deterministic decisions for Orchestration-owned result quality governance."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

from rightjob.contracts.capabilities import (
    CapabilityCatalog,
    CapabilityDefinition,
    CapabilityQualityGatePolicy,
    QualityScoreImprovementRule,
)
from rightjob.contracts.events import (
    AuditEvidence,
    AuditOutcome,
    DataSensitivity,
    IntegrationEvent,
    JsonValue,
)
from rightjob.contracts.review import (
    ResultProvenance,
    ResultValidationEvidence,
    ResultValidationOutcome,
    ReviewAssessment,
    ReviewRecommendation,
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
from rightjob.orchestration.application.repositories import ExecutionUnitOfWork

QualityGateUnitOfWorkFactory = Callable[[], ExecutionUnitOfWork]
QualityGateIdFactory = Callable[[], UUID]


class QualityGateDecisionService:
    """Re-resolve trusted policy and decide without persistence or execution."""

    def __init__(self, capabilities: CapabilityCatalog) -> None:
        self._capabilities = capabilities

    def decide(
        self,
        command: QualityGateCommand,
        validation: ResultValidationEvidence,
        assessment: ReviewAssessment | None,
        state: QualityGateState | None = None,
        prior_decision: QualityGateDecision | None = None,
    ) -> QualityGateDecision:
        _exact("command", command, QualityGateCommand)
        _exact("validation", validation, ResultValidationEvidence)
        if assessment is not None:
            _exact("assessment", assessment, ReviewAssessment)
        if state is not None:
            _exact("state", state, QualityGateState)
        if prior_decision is not None:
            _exact("prior_decision", prior_decision, QualityGateDecision)
            if prior_decision.command.command_id != command.command_id:
                raise QualityGateContractError("prior decision must bind the command identity")
            if prior_decision.command != command:
                raise QualityGateContractError("conflicting duplicate quality-gate command")
            return prior_decision

        if validation.outcome is not ResultValidationOutcome.PASSED:
            raise QualityGateContractError("quality gate requires passed validation evidence")
        provenance = validation.provenance
        if (
            command.workspace_id != provenance.workspace_id
            or command.run_id != provenance.run_id
            or command.step_id != provenance.step_id
            or command.correlation_id != provenance.correlation_id
            or command.causation_id != provenance.causation_id
            or command.artifact != provenance.artifact
        ):
            raise QualityGateContractError("quality-gate command provenance does not match")
        if command.issued_at < validation.validated_at:
            raise QualityGateContractError("quality-gate command predates validation")

        definition = self._resolve_capability(validation)
        policy = definition.quality_gate_policy
        if policy is None:
            raise QualityGateContractError("Capability has no quality-gate policy")
        _exact("quality_gate_policy", policy, CapabilityQualityGatePolicy)
        if policy.capability != provenance.capability:
            raise QualityGateContractError("quality policy Capability binding does not match")
        if policy.improvement_rule is not QualityScoreImprovementRule.STRICTLY_GREATER:
            raise QualityGateContractError("unsupported quality improvement rule")

        if assessment is None:
            raise QualityGateContractError("configured quality gate requires a review assessment")
        score = _assessment_score(command, validation, assessment, policy)
        before, prior_score, next_version = _validate_state(command, state, provenance, policy)
        outcome, reasons, after = _outcome(policy, assessment, score, before, prior_score)
        evidence = QualityGateDecisionEvidence(
            command.command_id,
            command.command_id,
            command.quality_gate_id,
            command.workspace_id,
            command.run_id,
            command.step_id,
            command.correlation_id,
            command.causation_id,
            provenance.capability,
            policy.policy_key,
            policy.semantic_version,
            policy.review_criteria_key,
            policy.review_criteria_version,
            policy.score_key,
            score,
            policy.minimum_score,
            prior_score,
            provenance.artifact,
            validation.validation_id,
            assessment.assessment_id,
            before,
            after,
            command.issued_at,
        )
        next_state = QualityGateState(
            command.quality_gate_id,
            command.workspace_id,
            command.run_id,
            command.step_id,
            command.correlation_id,
            command.causation_id,
            provenance.capability,
            policy.policy_key,
            policy.semantic_version,
            policy.review_criteria_key,
            policy.review_criteria_version,
            policy.score_key,
            QualityGateStatus(outcome.value),
            after,
            provenance.artifact,
            validation.validation_id,
            assessment.assessment_id,
            score,
            command.command_id,
            next_version,
            command.issued_at,
        )
        return QualityGateDecision(command, outcome, reasons, evidence, next_state)

    def _resolve_capability(self, validation: ResultValidationEvidence) -> CapabilityDefinition:
        reference = validation.provenance.capability
        try:
            definition = self._capabilities.get_enabled(
                reference.capability_key, reference.semantic_version
            )
        except (LookupError, ValueError) as error:
            raise QualityGateContractError(
                "enabled Capability definition is unavailable"
            ) from error
        if definition.reference != reference:
            raise QualityGateContractError("Capability definition identity does not match")
        return definition


class DurableQualityGateService:
    """Persist one deterministic decision and its safe evidence atomically."""

    def __init__(
        self,
        decision_service: QualityGateDecisionService,
        unit_of_work: QualityGateUnitOfWorkFactory,
        id_factory: QualityGateIdFactory = uuid4,
    ) -> None:
        self._decisions = decision_service
        self._unit_of_work = unit_of_work
        self._id = id_factory

    def decide(
        self,
        command: QualityGateCommand,
        validation: ResultValidationEvidence,
        assessment: ReviewAssessment | None,
    ) -> QualityGateDecision:
        with self._unit_of_work() as uow:
            prior = uow.quality_gate_decisions.get_by_command(
                command.workspace_id, command.command_id
            )
            if prior is not None:
                return self._decisions.decide(command, validation, assessment, prior_decision=prior)
            state = uow.quality_gate_states.get(command.workspace_id, command.quality_gate_id)
            decision = self._decisions.decide(command, validation, assessment, state)
            if state is None:
                uow.quality_gate_states.add(
                    command.workspace_id, decision.next_state, decision.evidence.minimum_score
                )
            else:
                uow.quality_gate_states.save(
                    command.workspace_id,
                    decision.next_state,
                    decision.evidence.minimum_score,
                    state.version,
                )
            uow.quality_gate_decisions.append(
                command.workspace_id, decision, state.version if state else None
            )
            self._record(uow, decision)
            uow.commit()
            return decision

    def _record(self, uow: ExecutionUnitOfWork, decision: QualityGateDecision) -> None:
        command, evidence = decision.command, decision.evidence
        payload: dict[str, JsonValue] = {
            "quality_gate_id": str(command.quality_gate_id),
            "run_id": str(command.run_id),
            "step_id": str(command.step_id),
            "capability_key": evidence.capability.capability_key,
            "capability_version": str(evidence.capability.semantic_version),
            "policy_key": evidence.policy_key,
            "policy_version": str(evidence.policy_version),
            "criteria_key": evidence.criteria_key,
            "criteria_version": str(evidence.criteria_version),
            "score_key": evidence.score_key,
            "score": evidence.score,
            "minimum_score": evidence.minimum_score,
            "artifact_id": str(evidence.artifact.artifact_id),
            "artifact_version": evidence.artifact.version,
            "artifact_sha256": evidence.artifact.sha256,
            "validation_id": str(evidence.validation_id),
            "assessment_id": str(evidence.assessment_id),
            "outcome": decision.outcome.value,
            "reasons": [reason.value for reason in decision.reasons],
            "revision_count_before": evidence.revision_count_before,
            "revision_count_after": evidence.revision_count_after,
            "state_version": decision.next_state.version,
        }
        uow.audit_evidence.append(
            command.workspace_id,
            AuditEvidence(
                id=self._id(),
                workspace_id=command.workspace_id,
                actor=command.actor,
                action="quality_gate.decided",
                resource_type="quality_gate",
                resource_id=str(command.quality_gate_id),
                outcome=AuditOutcome.SUCCEEDED,
                correlation_id=command.correlation_id,
                causation_id=command.causation_id,
                occurred_at=evidence.decided_at,
                after=payload,
            ),
        )
        uow.outbox.add(
            command.workspace_id,
            IntegrationEvent(
                event_id=self._id(),
                event_type="quality_gate.decided.v1",
                event_version=1,
                schema_version=1,
                occurred_at=evidence.decided_at,
                workspace_id=command.workspace_id,
                actor=command.actor,
                correlation_id=command.correlation_id,
                causation_id=command.causation_id,
                producer="orchestration",
                sensitivity=DataSensitivity.INTERNAL,
                payload=payload,
                idempotency_key=f"quality-gate:{command.command_id}",
            ),
        )


def _assessment_score(
    command: QualityGateCommand,
    validation: ResultValidationEvidence,
    assessment: ReviewAssessment | None,
    policy: CapabilityQualityGatePolicy,
) -> int:
    if assessment is None:
        raise QualityGateContractError("configured quality gate requires a review assessment")
    provenance = validation.provenance
    if (
        assessment.validation_id != validation.validation_id
        or assessment.workspace_id != command.workspace_id
        or assessment.run_id != command.run_id
        or assessment.step_id != command.step_id
        or assessment.criteria.criteria_key != policy.review_criteria_key
        or assessment.criteria.semantic_version != policy.review_criteria_version
        or assessment.criteria.minimum_score != policy.minimum_score
        or assessment.assessed_at < validation.validated_at
        or assessment.assessed_at > command.issued_at
    ):
        raise QualityGateContractError("review assessment provenance or criteria does not match")
    scores = tuple(
        item.score for item in assessment.scores if item.criteria_key == policy.score_key
    )
    if len(scores) != 1:
        raise QualityGateContractError("review assessment must contain the required score key")
    if provenance.artifact.sha256 != validation.result.provenance.artifact.sha256:
        raise QualityGateContractError("validation artifact identity does not match")
    return scores[0]


def _validate_state(
    command: QualityGateCommand,
    state: QualityGateState | None,
    provenance: ResultProvenance,
    policy: CapabilityQualityGatePolicy,
) -> tuple[int, int | None, int]:
    _exact("provenance", provenance, ResultProvenance)
    if state is None:
        if command.expected_state_version is not None:
            raise QualityGateContractError("new quality gate cannot expect existing state")
        return 0, None, 1
    if command.expected_state_version != state.version:
        raise QualityGateContractError("quality-gate state version does not match")
    if state.status is not QualityGateStatus.AWAITING_REVIEW:
        raise QualityGateContractError("quality-gate state is not awaiting review")
    if (
        state.quality_gate_id != command.quality_gate_id
        or state.workspace_id != command.workspace_id
        or state.run_id != command.run_id
        or state.step_id != command.step_id
        or state.correlation_id != command.correlation_id
        or state.causation_id != command.causation_id
        or state.capability != provenance.capability
        or state.policy_key != policy.policy_key
        or state.policy_version != policy.semantic_version
        or state.criteria_key != policy.review_criteria_key
        or state.criteria_version != policy.review_criteria_version
        or state.score_key != policy.score_key
    ):
        raise QualityGateContractError("quality-gate state binding does not match")
    artifact = provenance.artifact
    if (
        artifact.artifact_id != state.last_artifact.artifact_id
        or artifact.version <= state.last_artifact.version
        or artifact.sha256 == state.last_artifact.sha256
    ):
        raise QualityGateContractError("revision artifact must progress identity and content")
    if state.automated_revision_count > policy.maximum_automated_revisions:
        raise QualityGateContractError("quality-gate state exceeds policy revision budget")
    return state.automated_revision_count, state.last_score, state.version + 1


def _outcome(
    policy: CapabilityQualityGatePolicy,
    assessment: ReviewAssessment,
    score: int,
    revision_count: int,
    prior_score: int | None,
) -> tuple[QualityGateOutcome, tuple[QualityGateReason, ...], int]:
    if score >= policy.minimum_score:
        return QualityGateOutcome.ACCEPTED, (QualityGateReason.THRESHOLD_MET,), revision_count
    if assessment.recommendation is ReviewRecommendation.NEEDS_HUMAN_REVIEW:
        return (
            QualityGateOutcome.NEEDS_HUMAN_REVIEW,
            (
                QualityGateReason.THRESHOLD_NOT_MET,
                QualityGateReason.REVIEWER_ESCALATION_REQUESTED,
            ),
            revision_count,
        )
    if revision_count >= policy.maximum_automated_revisions:
        return (
            QualityGateOutcome.NEEDS_HUMAN_REVIEW,
            (
                QualityGateReason.THRESHOLD_NOT_MET,
                QualityGateReason.REVISION_BUDGET_EXHAUSTED,
            ),
            revision_count,
        )
    if prior_score is not None and score <= prior_score:
        return (
            QualityGateOutcome.NEEDS_HUMAN_REVIEW,
            (
                QualityGateReason.THRESHOLD_NOT_MET,
                QualityGateReason.SCORE_NOT_IMPROVED,
            ),
            revision_count,
        )
    improvement = (
        QualityGateReason.NO_PRIOR_COMPARABLE_SCORE
        if prior_score is None
        else QualityGateReason.SCORE_STRICTLY_IMPROVED
    )
    return (
        QualityGateOutcome.REVISION_REQUIRED,
        (
            QualityGateReason.THRESHOLD_NOT_MET,
            improvement,
            QualityGateReason.REVISION_BUDGET_REMAINING,
        ),
        revision_count + 1,
    )


def _exact(name: str, value: object, expected: type[object]) -> None:
    if type(value) is not expected:
        raise QualityGateContractError(f"{name} must be a {expected.__name__}")
