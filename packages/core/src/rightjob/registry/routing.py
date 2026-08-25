"""Deterministic structured Department routing."""

from rightjob.contracts.departments import (
    DepartmentCatalog,
    DepartmentDefinition,
    DepartmentReference,
    DepartmentRouteRequest,
)


class DepartmentRouteNotFoundError(LookupError):
    """No enabled Department satisfies the structured request."""


class DepartmentRouteAmbiguousError(LookupError):
    """More than one enabled Department satisfies the structured request."""


class DepartmentRouter:
    def __init__(self, departments: DepartmentCatalog) -> None:
        self._departments = departments

    def route(self, request: DepartmentRouteRequest) -> DepartmentReference:
        if request.exact_department is not None:
            candidate = self._departments.get_enabled(
                request.exact_department.department_key,
                request.exact_department.semantic_version,
            )
            if candidate.reference != request.exact_department or not _matches(candidate, request):
                raise DepartmentRouteNotFoundError("exact Department does not satisfy the request")
            return candidate.reference
        candidates = tuple(
            definition
            for definition in self._departments.list_enabled()
            if _matches(definition, request)
        )
        if not candidates:
            raise DepartmentRouteNotFoundError("no Department satisfies the request")
        if len(candidates) > 1:
            raise DepartmentRouteAmbiguousError("Department routing is ambiguous")
        return candidates[0].reference


def _matches(definition: DepartmentDefinition, request: DepartmentRouteRequest) -> bool:
    return (
        request.work_category is None or request.work_category in definition.work_categories
    ) and all(
        capability in definition.capability_references
        for capability in request.required_capabilities
    )
