"""Executive presentation façade over the published Planning application boundary."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from rightjob.contracts.capabilities import CapabilityCatalog
from rightjob.contracts.departments import DepartmentCatalog
from rightjob.contracts.executive import (
    ExecutivePlanningFailure,
    ExecutivePlanningOutcome,
    ExecutivePlanningRequest,
    ExecutivePlanningResult,
    ExecutivePlanPresentation,
    ExecutivePlanStep,
)
from rightjob.contracts.planning import (
    ExecutionPlan,
    PlanningApplication,
    PlanningApplicationError,
    PlanningContext,
    PlanningFailure,
    PlanningRequest,
)

IdFactory = Callable[[], UUID]
Clock = Callable[[], datetime]


class ExecutivePlanningService:
    def __init__(
        self,
        planning: PlanningApplication,
        capabilities: CapabilityCatalog,
        departments: DepartmentCatalog,
        id_factory: IdFactory,
        clock: Clock,
    ) -> None:
        self._planning = planning
        self._capabilities = capabilities
        self._departments = departments
        self._id = id_factory
        self._clock = clock

    def plan(self, request: ExecutivePlanningRequest) -> ExecutivePlanningResult:
        try:
            planning_request = PlanningRequest(
                planning_request_id=self._id(),
                workspace_id=request.workspace_id,
                correlation_id=request.correlation_id,
                causation_id=request.causation_id,
                actor=request.actor,
                goal=request.goal,
                constraints=request.constraints,
                input=request.input,
                created_at=self._clock(),
            )
            context = PlanningContext(
                workspace_id=request.workspace_id,
                actor=request.actor,
                correlation_id=request.correlation_id,
                causation_id=request.causation_id,
                available_departments=tuple(
                    item.reference
                    for item in sorted(
                        self._departments.list_enabled(),
                        key=lambda item: (item.department_key, str(item.semantic_version)),
                    )
                ),
                available_capabilities=tuple(
                    item.reference
                    for item in sorted(
                        self._capabilities.list_enabled(),
                        key=lambda item: (item.capability_key, str(item.semantic_version)),
                    )
                ),
                constraints=request.constraints,
            )
            plan = self._planning.plan(planning_request, context)
            if (
                plan.workspace_id != planning_request.workspace_id
                or plan.planning_request_id != planning_request.planning_request_id
                or plan.correlation_id != planning_request.correlation_id
                or plan.causation_id != planning_request.causation_id
            ):
                raise ValueError("validated plan provenance does not match Executive request")
            return ExecutivePlanningResult(
                ExecutivePlanningOutcome.PLANNED,
                plan=_presentation(plan, planning_request),
            )
        except PlanningApplicationError as error:
            outcome, failure = _planning_failure(error.failure)
            return ExecutivePlanningResult(outcome, failure=failure)
        except (LookupError, ValueError):
            return ExecutivePlanningResult(
                ExecutivePlanningOutcome.NOT_PLANNABLE,
                failure=ExecutivePlanningFailure.PLANNING_REJECTED,
            )
        except Exception:
            return ExecutivePlanningResult(
                ExecutivePlanningOutcome.FAILED,
                failure=ExecutivePlanningFailure.INTERNAL_FAILURE,
            )


def _presentation(
    plan: ExecutionPlan, planning_request: PlanningRequest
) -> ExecutivePlanPresentation:
    return ExecutivePlanPresentation(
        plan.plan_id,
        plan.planning_request_id,
        plan.workspace_id,
        plan.correlation_id,
        plan.causation_id,
        planning_request.actor,
        plan.planner,
        tuple(
            ExecutivePlanStep(
                step.step_id,
                step.sequence,
                step.objective,
                step.department,
                step.capability,
                step.dependency_step_ids,
                step.effect_classification,
                step.input,
            )
            for step in plan.steps
        ),
    )


def _planning_failure(
    failure: PlanningFailure,
) -> tuple[ExecutivePlanningOutcome, ExecutivePlanningFailure]:
    if failure is PlanningFailure.PROPOSAL_REJECTED:
        return (
            ExecutivePlanningOutcome.NOT_PLANNABLE,
            ExecutivePlanningFailure.PLANNING_REJECTED,
        )
    if failure is PlanningFailure.PROVIDER_CONFIGURATION:
        return (
            ExecutivePlanningOutcome.FAILED,
            ExecutivePlanningFailure.PROVIDER_CONFIGURATION,
        )
    if failure is PlanningFailure.PROVIDER_TRANSIENT:
        return (
            ExecutivePlanningOutcome.FAILED,
            ExecutivePlanningFailure.PROVIDER_UNAVAILABLE,
        )
    return (
        ExecutivePlanningOutcome.NOT_PLANNABLE,
        ExecutivePlanningFailure.INVALID_PROVIDER_OUTPUT,
    )
