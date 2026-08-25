"""Deterministic synthetic Planner adapter without AI or execution."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from rightjob.contracts.capabilities import (
    ContractReference,
    EffectClassification,
    SemanticVersion,
)
from rightjob.contracts.departments import WorkCategory
from rightjob.contracts.planning import (
    PlannerIdentity,
    PlanningContext,
    PlanningRequest,
    PlanStep,
    ProposedPlan,
    SyntheticPlanningGoal,
    SyntheticStepObjective,
)

_VERSION = SemanticVersion.parse("1.0.0")
_PLANNER = PlannerIdentity("synthetic.planner", _VERSION)
_GOAL_STEPS = {
    SyntheticPlanningGoal.PREPARE: (SyntheticStepObjective.PREPARE,),
    SyntheticPlanningGoal.TRANSFORM: (SyntheticStepObjective.TRANSFORM,),
    SyntheticPlanningGoal.VERIFY: (SyntheticStepObjective.VERIFY,),
    SyntheticPlanningGoal.PREPARE_TRANSFORM_VERIFY: (
        SyntheticStepObjective.PREPARE,
        SyntheticStepObjective.TRANSFORM,
        SyntheticStepObjective.VERIFY,
    ),
}
_STEP_METADATA = {
    SyntheticStepObjective.PREPARE: (
        "foundation.operations",
        "fake.prepare",
        WorkCategory.PREPARE,
        EffectClassification.READ_ONLY,
    ),
    SyntheticStepObjective.TRANSFORM: (
        "foundation.content",
        "fake.transform",
        WorkCategory.TRANSFORM,
        EffectClassification.REVERSIBLE,
    ),
    SyntheticStepObjective.VERIFY: (
        "foundation.operations",
        "fake.verify",
        WorkCategory.VERIFY,
        EffectClassification.READ_ONLY,
    ),
}


class SyntheticPlanner:
    def __init__(self, id_factory: Callable[[], UUID]) -> None:
        self._id = id_factory

    def plan(self, request: PlanningRequest, context: PlanningContext) -> ProposedPlan:
        objectives = _GOAL_STEPS[request.goal]
        if len(objectives) > context.constraints.maximum_steps:
            raise ValueError("synthetic plan exceeds the configured step bound")
        step_ids = tuple(self._id() for _ in objectives)
        steps = tuple(
            self._step(objective, sequence, step_ids, request, context)
            for sequence, objective in enumerate(objectives)
        )
        return ProposedPlan(
            plan_id=self._id(),
            workspace_id=request.workspace_id,
            planning_request_id=request.planning_request_id,
            correlation_id=request.correlation_id,
            causation_id=request.causation_id,
            planner=_PLANNER,
            plan_version=_VERSION,
            steps=steps,
            created_at=request.created_at,
        )

    @staticmethod
    def _step(
        objective: SyntheticStepObjective,
        sequence: int,
        step_ids: tuple[UUID, ...],
        request: PlanningRequest,
        context: PlanningContext,
    ) -> PlanStep:
        department_key, capability_key, category, effect = _STEP_METADATA[objective]
        department = next(
            item for item in context.available_departments if item.department_key == department_key
        )
        capability = next(
            item for item in context.available_capabilities if item.capability_key == capability_key
        )
        return PlanStep(
            step_id=step_ids[sequence],
            sequence=sequence,
            objective=objective,
            work_category=category,
            department=department,
            capability=capability,
            input=request.input,
            dependency_step_ids=() if sequence == 0 else (step_ids[sequence - 1],),
            expected_output=ContractReference(
                f"{capability_key}.output", capability.semantic_version, 4_096
            ),
            effect_classification=effect,
        )
