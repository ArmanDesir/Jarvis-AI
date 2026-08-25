"""Published provider-neutral Department Registry contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Sequence
from uuid import UUID

from rightjob.contracts.capabilities import CapabilityReference, SemanticVersion

_KEY = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class DepartmentRole(StrEnum):
    FOUNDATION = "foundation"


class WorkCategory(StrEnum):
    PREPARE = "prepare"
    TRANSFORM = "transform"
    VERIFY = "verify"


@dataclass(frozen=True, slots=True)
class DepartmentReference:
    department_definition_id: UUID
    department_key: str
    semantic_version: SemanticVersion

    def __post_init__(self) -> None:
        if self.department_definition_id.int == 0:
            raise ValueError("department_definition_id must not be nil")
        if _KEY.fullmatch(self.department_key) is None:
            raise ValueError("department_key must be canonical")


@dataclass(frozen=True, slots=True)
class DepartmentDefinition:
    department_definition_id: UUID
    department_key: str
    semantic_version: SemanticVersion
    display_name: str
    description: str
    enabled: bool
    role: DepartmentRole
    capability_references: tuple[CapabilityReference, ...]
    work_categories: tuple[WorkCategory, ...]

    def __post_init__(self) -> None:
        DepartmentReference(
            self.department_definition_id, self.department_key, self.semantic_version
        )
        _require_text("display_name", self.display_name, 100)
        _require_text("description", self.description, 1_000)
        if not self.capability_references:
            raise ValueError("capability_references must not be empty")
        if len(set(self.capability_references)) != len(self.capability_references):
            raise ValueError("capability_references must be unique")
        if not self.work_categories:
            raise ValueError("work_categories must not be empty")
        if len(set(self.work_categories)) != len(self.work_categories):
            raise ValueError("work_categories must be unique")

    @property
    def reference(self) -> DepartmentReference:
        return DepartmentReference(
            self.department_definition_id, self.department_key, self.semantic_version
        )


class DepartmentCatalog(Protocol):
    def get(self, department_key: str, version: SemanticVersion) -> DepartmentDefinition: ...

    def get_enabled(
        self, department_key: str, version: SemanticVersion
    ) -> DepartmentDefinition: ...

    def latest_enabled(self, department_key: str) -> DepartmentDefinition: ...

    def list_enabled(self) -> Sequence[DepartmentDefinition]: ...

    def list_by_capability(
        self, capability: CapabilityReference, *, enabled_only: bool = True
    ) -> Sequence[DepartmentDefinition]: ...

    def list_by_work_category(
        self, category: WorkCategory, *, enabled_only: bool = True
    ) -> Sequence[DepartmentDefinition]: ...


@dataclass(frozen=True, slots=True)
class DepartmentRouteRequest:
    work_category: WorkCategory | None = None
    required_capabilities: tuple[CapabilityReference, ...] = ()
    exact_department: DepartmentReference | None = None

    def __post_init__(self) -> None:
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError("required_capabilities must be unique")
        if (
            self.work_category is None
            and not self.required_capabilities
            and self.exact_department is None
        ):
            raise ValueError("a structured routing criterion is required")


def _require_text(name: str, value: str, maximum: int) -> None:
    if not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be nonblank and at most {maximum} characters")
