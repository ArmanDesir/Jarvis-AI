"""Provider-neutral durable workflow execution contract."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Protocol


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TERMINATED = "terminated"
    TIMED_OUT = "timed_out"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class WorkflowContext:
    workspace_id: str
    correlation_id: str
    causation_id: str | None
    logical_operation_id: str
    workflow_type: str
    workflow_version: str

    def canonical_id(self) -> str:
        material = ":".join((self.workspace_id, self.workflow_type, self.logical_operation_id))
        digest = hashlib.sha256(material.encode()).hexdigest()[:24]
        return f"rj-{self.workflow_type}-{digest}"


@dataclass(frozen=True)
class WorkflowRef:
    workflow_id: str
    workspace_id: str


@dataclass(frozen=True)
class WorkflowResult:
    status: WorkflowStatus
    value: Any | None = None


class DurableWorkflowEngine(Protocol):
    async def start(self, context: WorkflowContext, payload: Mapping[str, Any]) -> WorkflowRef: ...

    async def status(self, workspace_id: str, ref: WorkflowRef) -> WorkflowStatus: ...

    async def signal(
        self,
        workspace_id: str,
        ref: WorkflowRef,
        signal_name: str,
        payload: Mapping[str, Any],
    ) -> None: ...

    async def cancel(self, workspace_id: str, ref: WorkflowRef) -> None: ...

    async def result(self, workspace_id: str, ref: WorkflowRef) -> WorkflowResult: ...
