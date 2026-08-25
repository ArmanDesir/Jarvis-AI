"""Orchestration-owned validated-plan to ExecutionRequest compiler."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from rightjob.contracts.authorization import ExecutionAuthorizationReference
from rightjob.contracts.events import ActorType
from rightjob.contracts.planning import ExecutionPlan, PlanningRequest
from rightjob.orchestration.application.registry import (
    WorkflowDefinition,
    WorkflowDefinitionStatus,
)
from rightjob.orchestration.domain import ExecutionRequest, InitiatorType, RequestedStep


class ExecutionPlanCompilationError(ValueError):
    """A validated plan is incompatible with the exact workflow definition."""


class ExecutionPlanCompiler:
    def compile(
        self,
        plan: ExecutionPlan,
        planning_request: PlanningRequest,
        workflow: WorkflowDefinition,
        authorization: ExecutionAuthorizationReference,
        execution_id: UUID,
        created_at: datetime,
    ) -> ExecutionRequest:
        if (
            plan.workspace_id != planning_request.workspace_id
            or plan.planning_request_id != planning_request.planning_request_id
            or plan.correlation_id != planning_request.correlation_id
            or plan.causation_id != planning_request.causation_id
        ):
            raise ExecutionPlanCompilationError("plan provenance does not match planning request")
        if authorization.workspace_id != plan.workspace_id or authorization.plan_id != plan.plan_id:
            raise ExecutionPlanCompilationError("authorization does not match exact plan")
        if workflow.status is not WorkflowDefinitionStatus.ENABLED:
            raise ExecutionPlanCompilationError("workflow definition is disabled")
        if len(plan.steps) != len(workflow.steps):
            raise ExecutionPlanCompilationError("plan does not match workflow step count")
        for plan_step, workflow_step in zip(plan.steps, workflow.steps, strict=True):
            if (
                workflow_step.department != plan_step.department
                or workflow_step.capability != plan_step.capability
                or workflow_step.step_type != plan_step.capability.capability_key
            ):
                raise ExecutionPlanCompilationError(
                    "plan references do not match exact workflow definition"
                )
        return ExecutionRequest(
            execution_id=execution_id,
            workspace_id=plan.workspace_id,
            correlation_id=plan.correlation_id,
            causation_id=plan.causation_id,
            actor=planning_request.actor,
            initiator_type=(
                InitiatorType.USER
                if planning_request.actor.type is ActorType.USER
                else InitiatorType.SYSTEM
            ),
            authorization=authorization,
            workflow_definition_id=workflow.id,
            workflow_type=workflow.workflow_type,
            workflow_version=workflow.version,
            steps=tuple(
                RequestedStep(
                    id=plan_step.step_id,
                    step_type=workflow_step.step_type,
                    sequence=plan_step.sequence,
                    input_ref=f"plan:{plan.plan_id}:step:{plan_step.step_id}",
                    max_attempts=workflow_step.max_attempts,
                )
                for plan_step, workflow_step in zip(plan.steps, workflow.steps, strict=True)
            ),
            input=planning_request.input.as_dict(),
            created_at=created_at,
        )
