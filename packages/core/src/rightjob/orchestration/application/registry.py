"""Immutable code-owned registry for approved synthetic workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from rightjob.contracts.capabilities import CapabilityReference, SemanticVersion
from rightjob.contracts.departments import DepartmentReference

_CAPABILITY_IDS = {
    "fake.prepare": UUID("02800000-0000-4000-8000-000000000001"),
    "fake.transform": UUID("02800000-0000-4000-8000-000000000002"),
    "fake.verify": UUID("02800000-0000-4000-8000-000000000003"),
}
_CAPABILITY_VERSION = SemanticVersion.parse("1.0.0")
_DEPARTMENT_IDS = {
    "foundation.operations": UUID("02900000-0000-4000-8000-000000000001"),
    "foundation.content": UUID("02900000-0000-4000-8000-000000000002"),
}


def _capability(key: str) -> CapabilityReference:
    return CapabilityReference(_CAPABILITY_IDS[key], key, _CAPABILITY_VERSION)


def _department(key: str) -> DepartmentReference:
    return DepartmentReference(_DEPARTMENT_IDS[key], key, _CAPABILITY_VERSION)


class WorkflowDefinitionStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class WorkflowStepDefinition:
    step_type: str
    max_attempts: int = 1
    capability: CapabilityReference | None = None
    department: DepartmentReference | None = None

    def __post_init__(self) -> None:
        if self.capability is not None and self.capability.capability_key != self.step_type:
            raise ValueError("workflow step type must match its capability reference")
        if (self.capability is None) != (self.department is None):
            raise ValueError("workflow capability and Department references must be paired")


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    id: UUID
    workflow_type: str
    version: str
    input_schema: Mapping[str, type]
    steps: tuple[WorkflowStepDefinition, ...]
    handler: str
    status: WorkflowDefinitionStatus


BUILT_IN_WORKFLOWS: tuple[WorkflowDefinition, ...] = (
    WorkflowDefinition(
        id=UUID("02700000-0000-4000-8000-000000000001"),
        workflow_type="synthetic.sequence",
        version="1.0.0",
        input_schema=MappingProxyType({"value": str}),
        steps=(
            WorkflowStepDefinition(
                "fake.prepare",
                capability=_capability("fake.prepare"),
                department=_department("foundation.operations"),
            ),
            WorkflowStepDefinition(
                "fake.transform",
                max_attempts=3,
                capability=_capability("fake.transform"),
                department=_department("foundation.content"),
            ),
            WorkflowStepDefinition(
                "fake.verify",
                capability=_capability("fake.verify"),
                department=_department("foundation.operations"),
            ),
        ),
        handler="rightjob.synthetic.sequence",
        status=WorkflowDefinitionStatus.ENABLED,
    ),
    WorkflowDefinition(
        id=UUID("02700000-0000-4000-8000-000000000002"),
        workflow_type="synthetic.signal",
        version="1.0.0",
        input_schema=MappingProxyType({"value": str}),
        steps=(WorkflowStepDefinition("fake.wait_for_signal"),),
        handler="rightjob.synthetic.signal",
        status=WorkflowDefinitionStatus.ENABLED,
    ),
)


class WorkflowNotAvailableError(LookupError):
    """The exact built-in workflow is absent or disabled."""


class WorkflowRegistry:
    def __init__(self, definitions: tuple[WorkflowDefinition, ...] = BUILT_IN_WORKFLOWS) -> None:
        keys = [(item.workflow_type, item.version) for item in definitions]
        if len(keys) != len(set(keys)) or len({item.id for item in definitions}) != len(
            definitions
        ):
            raise ValueError("workflow definitions require unique identity and type/version")
        self._definitions = definitions

    def get_enabled(self, workflow_type: str, version: str) -> WorkflowDefinition:
        for definition in self._definitions:
            if definition.workflow_type == workflow_type and definition.version == version:
                if definition.status is not WorkflowDefinitionStatus.ENABLED:
                    break
                return definition
        raise WorkflowNotAvailableError("workflow definition is unavailable")
