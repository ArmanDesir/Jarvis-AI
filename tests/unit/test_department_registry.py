from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from uuid import UUID

import pytest
from rightjob.contracts.capabilities import CapabilityReference, SemanticVersion
from rightjob.contracts.departments import (
    DepartmentRole,
    DepartmentRouteRequest,
    WorkCategory,
)
from rightjob.orchestration.application.registry import BUILT_IN_WORKFLOWS
from rightjob.registry import (
    BUILT_IN_CAPABILITIES,
    BUILT_IN_DEPARTMENTS,
    BuiltInCapabilityRegistry,
    BuiltInDepartmentRegistry,
    DepartmentDisabledError,
    DepartmentNotFoundError,
    DepartmentRouteAmbiguousError,
    DepartmentRouteNotFoundError,
    DepartmentRouter,
)


def test_built_in_departments_are_exact_immutable_and_bounded() -> None:
    operations, content = BUILT_IN_DEPARTMENTS
    assert (operations.department_key, content.department_key) == (
        "foundation.operations",
        "foundation.content",
    )
    assert operations.role is DepartmentRole.FOUNDATION
    assert content.role is DepartmentRole.FOUNDATION
    assert operations.work_categories == (WorkCategory.PREPARE, WorkCategory.VERIFY)
    assert content.work_categories == (WorkCategory.TRANSFORM,)
    assert operations.capability_references == (
        BUILT_IN_CAPABILITIES[0].reference,
        BUILT_IN_CAPABILITIES[2].reference,
    )
    assert content.capability_references == (BUILT_IN_CAPABILITIES[1].reference,)
    with pytest.raises(FrozenInstanceError):
        operations.enabled = False  # type: ignore[misc]


def test_definition_validation_rejects_invalid_and_duplicate_metadata() -> None:
    operations = BUILT_IN_DEPARTMENTS[0]
    with pytest.raises(ValueError, match="canonical"):
        replace(operations, department_key="not canonical")
    with pytest.raises(ValueError, match="must not be empty"):
        replace(operations, capability_references=())
    with pytest.raises(ValueError, match="must be unique"):
        replace(
            operations,
            capability_references=(operations.capability_references[0],) * 2,
        )
    with pytest.raises(ValueError, match="must be unique"):
        replace(operations, work_categories=(WorkCategory.PREPARE,) * 2)


def test_registry_validates_identity_version_and_capability_membership() -> None:
    capabilities = BuiltInCapabilityRegistry()
    operations = BUILT_IN_DEPARTMENTS[0]
    duplicate_identity = replace(operations, department_key="foundation.duplicate")
    duplicate_version = replace(
        operations,
        department_definition_id=UUID("02900000-0000-4000-8000-000000000099"),
    )
    with pytest.raises(ValueError, match="unique identity"):
        BuiltInDepartmentRegistry(capabilities, (operations, duplicate_identity))
    with pytest.raises(ValueError, match="unique identity"):
        BuiltInDepartmentRegistry(capabilities, (operations, duplicate_version))
    bad_capability = CapabilityReference(
        UUID("02800000-0000-4000-8000-000000000099"),
        "fake.prepare",
        SemanticVersion.parse("1.0.0"),
    )
    with pytest.raises(ValueError, match="identity"):
        BuiltInDepartmentRegistry(
            capabilities, (replace(operations, capability_references=(bad_capability,)),)
        )
    with pytest.raises(ValueError, match="one Department owner"):
        BuiltInDepartmentRegistry(
            capabilities,
            (
                operations,
                replace(
                    BUILT_IN_DEPARTMENTS[1],
                    capability_references=(operations.capability_references[0],),
                ),
            ),
        )


def test_exact_enabled_latest_and_stable_discovery_fail_closed() -> None:
    operations = BUILT_IN_DEPARTMENTS[0]
    newer = replace(
        operations,
        department_definition_id=UUID("02900000-0000-4000-8000-000000000011"),
        semantic_version=SemanticVersion.parse("2.0.0"),
        enabled=False,
    )
    registry = BuiltInDepartmentRegistry(
        BuiltInCapabilityRegistry(), (*BUILT_IN_DEPARTMENTS, newer)
    )
    assert registry.get(operations.department_key, operations.semantic_version) is operations
    assert (
        registry.get_enabled(operations.department_key, operations.semantic_version) is operations
    )
    assert registry.latest_enabled(operations.department_key) is operations
    assert tuple(item.department_key for item in registry.list_enabled()) == (
        "foundation.content",
        "foundation.operations",
    )
    assert registry.list_by_capability(BUILT_IN_CAPABILITIES[1].reference) == (
        BUILT_IN_DEPARTMENTS[1],
    )
    assert registry.list_by_work_category(WorkCategory.VERIFY) == (operations,)
    with pytest.raises(DepartmentDisabledError):
        registry.get_enabled(newer.department_key, newer.semantic_version)
    with pytest.raises(DepartmentNotFoundError):
        registry.get("foundation.missing", SemanticVersion.parse("1.0.0"))


def test_router_is_structured_deterministic_and_fail_closed() -> None:
    capabilities = BuiltInCapabilityRegistry()
    registry = BuiltInDepartmentRegistry(capabilities)
    router = DepartmentRouter(registry)
    operations, content = BUILT_IN_DEPARTMENTS
    assert router.route(DepartmentRouteRequest(work_category=WorkCategory.TRANSFORM)) == (
        content.reference
    )
    assert (
        router.route(
            DepartmentRouteRequest(
                required_capabilities=(BUILT_IN_CAPABILITIES[2].reference,),
                exact_department=operations.reference,
            )
        )
        == operations.reference
    )
    with pytest.raises(DepartmentRouteNotFoundError):
        router.route(
            DepartmentRouteRequest(
                work_category=WorkCategory.PREPARE,
                required_capabilities=(BUILT_IN_CAPABILITIES[1].reference,),
            )
        )
    ambiguous_content = replace(
        content,
        work_categories=(WorkCategory.PREPARE, WorkCategory.TRANSFORM),
    )
    ambiguous = DepartmentRouter(
        BuiltInDepartmentRegistry(capabilities, (operations, ambiguous_content))
    )
    with pytest.raises(DepartmentRouteAmbiguousError):
        ambiguous.route(DepartmentRouteRequest(work_category=WorkCategory.PREPARE))


def test_workflows_pin_exact_department_and_capability_references() -> None:
    departments = BuiltInDepartmentRegistry(BuiltInCapabilityRegistry())
    sequence = BUILT_IN_WORKFLOWS[0]
    for step in sequence.steps:
        assert step.department is not None
        department = departments.get_enabled(
            step.department.department_key, step.department.semantic_version
        )
        assert department.reference == step.department
        assert step.capability in department.capability_references
    signal = BUILT_IN_WORKFLOWS[1].steps[0]
    assert signal.department is None
    assert signal.capability is None
    with pytest.raises(ValueError, match="must be paired"):
        replace(sequence.steps[0], department=None)


def test_department_foundation_has_no_dynamic_ai_provider_or_temporal_behavior() -> None:
    root = Path(__file__).resolve().parents[2]
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            root / "packages/core/src/rightjob/contracts/departments.py",
            root / "packages/core/src/rightjob/registry/departments.py",
            root / "packages/core/src/rightjob/registry/routing.py",
        )
    )
    for forbidden in ("importlib", "eval(", "temporalio", "openai", "anthropic", "prompt"):
        assert forbidden not in source.lower()
