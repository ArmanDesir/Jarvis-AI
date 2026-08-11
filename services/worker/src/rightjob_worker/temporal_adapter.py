"""Temporal infrastructure adapter for the provider-neutral workflow contract."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from rightjob.orchestration import WorkflowContext, WorkflowRef, WorkflowResult, WorkflowStatus
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDConflictPolicy


class WorkflowScopeError(PermissionError):
    """Raised before Temporal is contacted for a cross-workspace operation."""


def canonical_workflow_id(context: WorkflowContext) -> str:
    material = ":".join((context.workspace_id, context.workflow_type, context.logical_operation_id))
    digest = hashlib.sha256(material.encode()).hexdigest()[:24]
    return f"rj-{context.workflow_type}-{digest}"


_STATUS = {
    WorkflowExecutionStatus.RUNNING: WorkflowStatus.RUNNING,
    WorkflowExecutionStatus.COMPLETED: WorkflowStatus.COMPLETED,
    WorkflowExecutionStatus.FAILED: WorkflowStatus.FAILED,
    WorkflowExecutionStatus.CANCELED: WorkflowStatus.CANCELLED,
    WorkflowExecutionStatus.TERMINATED: WorkflowStatus.TERMINATED,
    WorkflowExecutionStatus.TIMED_OUT: WorkflowStatus.TIMED_OUT,
}


class TemporalWorkflowEngine:
    def __init__(self, client: Client, task_queue: str) -> None:
        self._client = client
        self._task_queue = task_queue

    async def start(self, context: WorkflowContext, payload: Mapping[str, Any]) -> WorkflowRef:
        workflow_id = canonical_workflow_id(context)
        await self._client.start_workflow(
            context.workflow_type,
            {"context": context.__dict__, "payload": dict(payload)},
            id=workflow_id,
            task_queue=self._task_queue,
            id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
        )
        return WorkflowRef(workflow_id=workflow_id, workspace_id=context.workspace_id)

    async def status(self, workspace_id: str, ref: WorkflowRef) -> WorkflowStatus:
        description = await self._handle(workspace_id, ref).describe()
        return _STATUS.get(description.status, WorkflowStatus.UNKNOWN)

    async def signal(
        self,
        workspace_id: str,
        ref: WorkflowRef,
        signal_name: str,
        payload: Mapping[str, Any],
    ) -> None:
        await self._handle(workspace_id, ref).signal(signal_name, dict(payload))

    async def cancel(self, workspace_id: str, ref: WorkflowRef) -> None:
        await self._handle(workspace_id, ref).cancel(reason="rightjob-requested")

    async def result(self, workspace_id: str, ref: WorkflowRef) -> WorkflowResult:
        value = await self._handle(workspace_id, ref).result()
        return WorkflowResult(status=WorkflowStatus.COMPLETED, value=value)

    def _handle(self, workspace_id: str, ref: WorkflowRef):  # type: ignore[no-untyped-def]
        if workspace_id != ref.workspace_id:
            raise WorkflowScopeError("workflow is outside the authorized workspace")
        return self._client.get_workflow_handle(ref.workflow_id)
