"""Deterministic Policy evaluation over a validated in-memory plan."""

from __future__ import annotations

from dataclasses import dataclass

from rightjob.contracts.planning import ExecutionPlan, PlanningRequest
from rightjob.contracts.policy import (
    PolicyAction,
    PolicyContext,
    PolicyDecision,
    PolicyEvaluation,
    PolicyEvaluationError,
    PolicyEvaluator,
    PolicyOperation,
    PolicySubject,
)

_PRECEDENCE = {
    PolicyDecision.ALLOW: 0,
    PolicyDecision.REQUIRE_APPROVAL: 1,
    PolicyDecision.DENY: 2,
}


@dataclass(frozen=True, slots=True)
class PlanPolicyEvaluation:
    """Aggregate of in-memory step decisions; never execution authority."""

    decision: PolicyDecision
    step_evaluations: tuple[PolicyEvaluation, ...]

    def __post_init__(self) -> None:
        if not self.step_evaluations:
            raise ValueError("step_evaluations must not be empty")
        expected = max(
            (item.decision for item in self.step_evaluations), key=_PRECEDENCE.__getitem__
        )
        if self.decision is not expected:
            raise ValueError("aggregate decision must preserve strongest step decision")


class PlanPolicyEvaluator:
    def __init__(self, evaluator: PolicyEvaluator) -> None:
        self._evaluator = evaluator

    def evaluate(
        self,
        request: PlanningRequest,
        plan: ExecutionPlan,
        subject: PolicySubject,
        context: PolicyContext,
    ) -> PlanPolicyEvaluation:
        if (
            request.workspace_id != plan.workspace_id
            or request.workspace_id != subject.workspace_id
            or request.workspace_id != context.workspace_id
            or request.planning_request_id != plan.planning_request_id
            or request.planning_request_id != context.planning_request_id
            or request.correlation_id != plan.correlation_id
            or request.correlation_id != context.correlation_id
            or request.causation_id != plan.causation_id
            or request.causation_id != context.causation_id
            or plan.plan_id != context.plan_id
        ):
            raise PolicyEvaluationError("plan Policy provenance does not match")
        evaluations = tuple(
            self._evaluator.evaluate(
                subject,
                PolicyAction(
                    PolicyOperation.EXECUTE_CAPABILITY,
                    plan.plan_id,
                    step.step_id,
                    step.department,
                    step.capability,
                    step.work_category,
                    step.effect_classification,
                ),
                context,
            )
            for step in plan.steps
        )
        decision = max((item.decision for item in evaluations), key=_PRECEDENCE.__getitem__)
        return PlanPolicyEvaluation(decision, evaluations)
