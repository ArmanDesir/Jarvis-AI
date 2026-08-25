"""Provider-neutral deterministic workflow compiler boundary."""

from __future__ import annotations

from typing import Protocol

from rightjob.contracts.capabilities import CapabilityCatalog
from rightjob.contracts.departments import DepartmentCatalog
from rightjob.orchestration.application.registry import WorkflowDefinition
from rightjob.orchestration.domain import CompiledExecution, ExecutionContext, ExecutionRequest


class WorkflowCompilationError(ValueError):
    """A validated request does not match its approved built-in definition."""


class WorkflowCompiler(Protocol):
    def compile(
        self, request: ExecutionRequest, definition: WorkflowDefinition
    ) -> CompiledExecution: ...


class SyntheticWorkflowCompiler:
    def __init__(self, capabilities: CapabilityCatalog, departments: DepartmentCatalog) -> None:
        self._capabilities = capabilities
        self._departments = departments

    def compile(
        self, request: ExecutionRequest, definition: WorkflowDefinition
    ) -> CompiledExecution:
        if (
            request.workflow_definition_id != definition.id
            or request.workflow_type != definition.workflow_type
            or request.workflow_version != definition.version
        ):
            raise WorkflowCompilationError("request does not identify the selected definition")
        expected = tuple((step.step_type, step.max_attempts) for step in definition.steps)
        actual = tuple((step.step_type, step.max_attempts) for step in request.steps)
        if actual != expected:
            raise WorkflowCompilationError("request steps do not match the approved definition")
        for step in definition.steps:
            if step.capability is None:
                continue
            capability = self._capabilities.get_enabled(
                step.capability.capability_key, step.capability.semantic_version
            )
            if capability.reference != step.capability:
                raise WorkflowCompilationError(
                    "workflow capability identity does not match catalog"
                )
            if step.department is None:
                raise WorkflowCompilationError("workflow capability requires a Department")
            department = self._departments.get_enabled(
                step.department.department_key, step.department.semantic_version
            )
            if department.reference != step.department:
                raise WorkflowCompilationError(
                    "workflow Department identity does not match catalog"
                )
            if step.capability not in department.capability_references:
                raise WorkflowCompilationError("workflow capability is not owned by its Department")
        if set(request.input) != set(definition.input_schema):
            raise WorkflowCompilationError("input fields do not match the approved schema")
        for field, expected_type in definition.input_schema.items():
            if not isinstance(request.input[field], expected_type):
                raise WorkflowCompilationError(f"invalid input field: {field}")
        return CompiledExecution(
            context=ExecutionContext(
                execution_id=request.execution_id,
                workspace_id=request.workspace_id,
                correlation_id=request.correlation_id,
                causation_id=request.causation_id,
                actor=request.actor,
                initiator_type=request.initiator_type,
            ),
            workflow_definition_id=definition.id,
            workflow_type=definition.handler,
            workflow_version=definition.version,
            steps=request.steps,
            input=request.input,
        )
