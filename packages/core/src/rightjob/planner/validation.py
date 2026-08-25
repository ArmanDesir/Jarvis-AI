"""Deterministic validation of untrusted typed plan proposals."""

from __future__ import annotations

from uuid import UUID

from rightjob.contracts.capabilities import CapabilityCatalog
from rightjob.contracts.departments import DepartmentCatalog
from rightjob.contracts.planning import (
    ExecutionPlan,
    PlanningContext,
    PlanningRequest,
    ProposedPlan,
    SyntheticPlanningGoal,
    SyntheticStepObjective,
)

_GOAL_OBJECTIVES = {
    SyntheticPlanningGoal.PREPARE: (SyntheticStepObjective.PREPARE,),
    SyntheticPlanningGoal.TRANSFORM: (SyntheticStepObjective.TRANSFORM,),
    SyntheticPlanningGoal.VERIFY: (SyntheticStepObjective.VERIFY,),
    SyntheticPlanningGoal.PREPARE_TRANSFORM_VERIFY: (
        SyntheticStepObjective.PREPARE,
        SyntheticStepObjective.TRANSFORM,
        SyntheticStepObjective.VERIFY,
    ),
}


class PlanValidationError(ValueError):
    """An untrusted proposal failed deterministic validation."""


class PlanValidator:
    def __init__(self, capabilities: CapabilityCatalog, departments: DepartmentCatalog) -> None:
        self._capabilities = capabilities
        self._departments = departments

    def validate(
        self,
        request: PlanningRequest,
        context: PlanningContext,
        proposal: ProposedPlan,
    ) -> ExecutionPlan:
        self._validate_envelope(request, context, proposal)
        self._validate_graph(proposal)
        for step in proposal.steps:
            if step.input.encoded_bytes > request.constraints.maximum_input_bytes:
                raise PlanValidationError("plan step input exceeds the configured bound")
            if step.department not in context.available_departments:
                raise PlanValidationError("plan Department was not available in context")
            if step.capability not in context.available_capabilities:
                raise PlanValidationError("plan Capability was not available in context")
            try:
                department = self._departments.get_enabled(
                    step.department.department_key, step.department.semantic_version
                )
                capability = self._capabilities.get_enabled(
                    step.capability.capability_key, step.capability.semantic_version
                )
            except LookupError as error:
                raise PlanValidationError("plan references an unavailable definition") from error
            if department.reference != step.department:
                raise PlanValidationError("plan Department identity does not match catalog")
            if capability.reference != step.capability:
                raise PlanValidationError("plan Capability identity does not match catalog")
            if step.capability not in department.capability_references:
                raise PlanValidationError("plan Capability does not belong to its Department")
            if step.work_category not in department.work_categories:
                raise PlanValidationError("plan work category does not belong to its Department")
            if step.expected_output != capability.output_contract:
                raise PlanValidationError("plan output contract does not match Capability")
            if step.effect_classification is not capability.effect_classification:
                raise PlanValidationError("plan effect classification does not match Capability")
        return ExecutionPlan(
            proposal.plan_id,
            proposal.workspace_id,
            proposal.planning_request_id,
            proposal.correlation_id,
            proposal.causation_id,
            proposal.planner,
            proposal.plan_version,
            proposal.steps,
            proposal.created_at,
        )

    @staticmethod
    def _validate_envelope(
        request: PlanningRequest, context: PlanningContext, proposal: ProposedPlan
    ) -> None:
        request_identity = (
            request.workspace_id,
            request.actor,
            request.correlation_id,
            request.causation_id,
            request.constraints,
        )
        context_identity = (
            context.workspace_id,
            context.actor,
            context.correlation_id,
            context.causation_id,
            context.constraints,
        )
        if request_identity != context_identity:
            raise PlanValidationError("planning request and context do not match")
        if (
            proposal.workspace_id != request.workspace_id
            or proposal.planning_request_id != request.planning_request_id
            or proposal.correlation_id != request.correlation_id
            or proposal.causation_id != request.causation_id
        ):
            raise PlanValidationError("plan provenance does not match its request")
        if len(proposal.steps) > request.constraints.maximum_steps:
            raise PlanValidationError("plan exceeds the configured step bound")
        if tuple(step.objective for step in proposal.steps) != _GOAL_OBJECTIVES[request.goal]:
            raise PlanValidationError("plan steps do not match the requested synthetic goal")

    @staticmethod
    def _validate_graph(proposal: ProposedPlan) -> None:
        steps = proposal.steps
        ids = tuple(step.step_id for step in steps)
        if len(ids) != len(set(ids)):
            raise PlanValidationError("plan step IDs must be unique")
        if tuple(step.sequence for step in steps) != tuple(range(len(steps))):
            raise PlanValidationError("plan sequence must be contiguous")
        known = set(ids)
        dependencies = {step.step_id: step.dependency_step_ids for step in steps}
        for step in steps:
            if not set(step.dependency_step_ids) <= known:
                raise PlanValidationError("plan dependency does not exist")
        visiting: set[UUID] = set()
        visited: set[UUID] = set()

        def visit(step_id: UUID) -> None:
            if step_id in visiting:
                raise PlanValidationError("plan dependencies contain a cycle")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in dependencies[step_id]:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in ids:
            visit(step_id)
        positions = {step_id: index for index, step_id in enumerate(ids)}
        if any(
            positions[dependency] >= step.sequence
            for step in steps
            for dependency in step.dependency_step_ids
        ):
            raise PlanValidationError("plan dependencies must precede their dependent step")
