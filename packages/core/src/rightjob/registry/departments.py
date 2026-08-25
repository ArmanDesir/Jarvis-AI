"""Immutable code-owned catalog of approved synthetic Departments."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Sequence
from uuid import UUID

from rightjob.contracts.capabilities import CapabilityCatalog, CapabilityReference, SemanticVersion
from rightjob.contracts.departments import (
    DepartmentDefinition,
    DepartmentRole,
    WorkCategory,
)
from rightjob.registry.catalog import BUILT_IN_CAPABILITIES, VERSION_1


def _capability(index: int) -> CapabilityReference:
    return BUILT_IN_CAPABILITIES[index].reference


BUILT_IN_DEPARTMENTS: tuple[DepartmentDefinition, ...] = (
    DepartmentDefinition(
        department_definition_id=UUID("02900000-0000-4000-8000-000000000001"),
        department_key="foundation.operations",
        semantic_version=VERSION_1,
        display_name="Foundation Operations",
        description="Owns synthetic preparation and verification metadata.",
        enabled=True,
        role=DepartmentRole.FOUNDATION,
        capability_references=(_capability(0), _capability(2)),
        work_categories=(WorkCategory.PREPARE, WorkCategory.VERIFY),
    ),
    DepartmentDefinition(
        department_definition_id=UUID("02900000-0000-4000-8000-000000000002"),
        department_key="foundation.content",
        semantic_version=VERSION_1,
        display_name="Foundation Content",
        description="Owns synthetic transformation metadata.",
        enabled=True,
        role=DepartmentRole.FOUNDATION,
        capability_references=(_capability(1),),
        work_categories=(WorkCategory.TRANSFORM,),
    ),
)


class DepartmentNotFoundError(LookupError):
    """The requested Department key and exact version are not registered."""


class DepartmentDisabledError(LookupError):
    """The requested Department exists but is disabled."""


class BuiltInDepartmentRegistry:
    def __init__(
        self,
        capabilities: CapabilityCatalog,
        definitions: Sequence[DepartmentDefinition] = BUILT_IN_DEPARTMENTS,
    ) -> None:
        by_identity = {
            definition.department_definition_id: definition for definition in definitions
        }
        by_version = {
            (definition.department_key, definition.semantic_version): definition
            for definition in definitions
        }
        if len(by_identity) != len(definitions) or len(by_version) != len(definitions):
            raise ValueError("Department definitions require unique identity and key/version")
        assigned: set[CapabilityReference] = set()
        for definition in definitions:
            for reference in definition.capability_references:
                capability = capabilities.get_enabled(
                    reference.capability_key, reference.semantic_version
                )
                if capability.reference != reference:
                    raise ValueError("Department capability identity does not match catalog")
                if definition.enabled and reference in assigned:
                    raise ValueError("enabled capabilities require one Department owner")
                if definition.enabled:
                    assigned.add(reference)
        self._definitions = tuple(
            sorted(definitions, key=lambda item: (item.department_key, str(item.semantic_version)))
        )
        self._by_version: Mapping[tuple[str, SemanticVersion], DepartmentDefinition] = (
            MappingProxyType(by_version)
        )

    def get(self, department_key: str, version: SemanticVersion) -> DepartmentDefinition:
        try:
            return self._by_version[(department_key, version)]
        except KeyError as error:
            raise DepartmentNotFoundError("Department definition is unavailable") from error

    def get_enabled(self, department_key: str, version: SemanticVersion) -> DepartmentDefinition:
        definition = self.get(department_key, version)
        if not definition.enabled:
            raise DepartmentDisabledError("Department definition is disabled")
        return definition

    def latest_enabled(self, department_key: str) -> DepartmentDefinition:
        candidates = tuple(
            definition
            for definition in self._definitions
            if definition.department_key == department_key and definition.enabled
        )
        if not candidates:
            raise DepartmentNotFoundError("enabled Department definition is unavailable")
        return max(
            candidates,
            key=lambda item: (item.semantic_version.precedence(), str(item.semantic_version)),
        )

    def list_enabled(self) -> Sequence[DepartmentDefinition]:
        return tuple(definition for definition in self._definitions if definition.enabled)

    def list_by_capability(
        self, capability: CapabilityReference, *, enabled_only: bool = True
    ) -> Sequence[DepartmentDefinition]:
        return tuple(
            definition
            for definition in self._definitions
            if capability in definition.capability_references
            and (definition.enabled or not enabled_only)
        )

    def list_by_work_category(
        self, category: WorkCategory, *, enabled_only: bool = True
    ) -> Sequence[DepartmentDefinition]:
        return tuple(
            definition
            for definition in self._definitions
            if category in definition.work_categories and (definition.enabled or not enabled_only)
        )
