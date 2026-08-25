from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from uuid import UUID

import pytest
from rightjob.contracts.capabilities import (
    CapabilityReference,
    ContractReference,
    EffectClassification,
    IdempotencyClassification,
    RetryableFailure,
    RetryMetadata,
    SemanticVersion,
    TimeoutMetadata,
)
from rightjob.orchestration.application.registry import BUILT_IN_WORKFLOWS
from rightjob.registry import (
    BUILT_IN_CAPABILITIES,
    BuiltInCapabilityRegistry,
    CapabilityDisabledError,
    CapabilityHandlerNotFoundError,
    CapabilityHandlerResolver,
    CapabilityNotFoundError,
)


def test_built_in_definitions_are_exact_immutable_and_bounded() -> None:
    assert tuple(item.capability_key for item in BUILT_IN_CAPABILITIES) == (
        "fake.prepare",
        "fake.transform",
        "fake.verify",
    )
    assert len({item.capability_definition_id for item in BUILT_IN_CAPABILITIES}) == 3
    assert all(item.owner_key == "synthetic.foundation" for item in BUILT_IN_CAPABILITIES)
    assert all(item.enabled for item in BUILT_IN_CAPABILITIES)
    assert all(item.input_contract.maximum_payload_bytes == 4_096 for item in BUILT_IN_CAPABILITIES)
    assert all(
        item.output_contract.maximum_payload_bytes == 4_096 for item in BUILT_IN_CAPABILITIES
    )
    with pytest.raises(FrozenInstanceError):
        BUILT_IN_CAPABILITIES[0].enabled = False  # type: ignore[misc]


def test_semantic_version_parsing_and_precedence_are_deterministic() -> None:
    release = SemanticVersion.parse("2.1.0+build.7")
    prerelease = SemanticVersion.parse("2.1.0-rc.1")
    assert str(release) == "2.1.0+build.7"
    assert release.precedence() > prerelease.precedence()
    with pytest.raises(ValueError, match="semantic version"):
        SemanticVersion.parse("01.0.0")


def test_contract_retry_and_timeout_metadata_are_bounded() -> None:
    with pytest.raises(ValueError, match="maximum_payload_bytes"):
        ContractReference("fake.input", SemanticVersion.parse("1.0.0"), 65_537)
    with pytest.raises(ValueError, match="maximum_attempts"):
        RetryMetadata(11)
    with pytest.raises(ValueError, match="timeout_seconds"):
        TimeoutMetadata(0)
    transform = BUILT_IN_CAPABILITIES[1]
    assert transform.effect_classification is EffectClassification.REVERSIBLE
    assert transform.idempotency is IdempotencyClassification.REQUIRES_IDEMPOTENCY_KEY
    assert transform.retry.maximum_attempts == 3
    assert transform.retry.retryable_failures == {RetryableFailure.TRANSIENT_DEPENDENCY}


def test_exact_enabled_latest_and_owner_lookup_fail_closed() -> None:
    first = BUILT_IN_CAPABILITIES[0]
    newer = replace(
        first,
        capability_definition_id=UUID("02800000-0000-4000-8000-000000000011"),
        semantic_version=SemanticVersion.parse("2.0.0"),
    )
    disabled = replace(
        first,
        capability_definition_id=UUID("02800000-0000-4000-8000-000000000012"),
        semantic_version=SemanticVersion.parse("3.0.0"),
        enabled=False,
    )
    registry = BuiltInCapabilityRegistry((*BUILT_IN_CAPABILITIES, newer, disabled))
    assert registry.get(first.capability_key, first.semantic_version) is first
    assert registry.get_enabled(newer.capability_key, newer.semantic_version) is newer
    assert registry.latest_enabled(first.capability_key) is newer
    assert registry.list_by_owner("synthetic.foundation") == (
        first,
        newer,
        BUILT_IN_CAPABILITIES[1],
        BUILT_IN_CAPABILITIES[2],
    )
    assert registry.list_by_owner("missing.owner") == ()
    with pytest.raises(CapabilityDisabledError):
        registry.get_enabled(disabled.capability_key, disabled.semantic_version)
    with pytest.raises(CapabilityNotFoundError):
        registry.get("fake.missing", SemanticVersion.parse("1.0.0"))


def test_duplicate_identity_and_key_version_are_rejected() -> None:
    first = BUILT_IN_CAPABILITIES[0]
    duplicate_identity = replace(first, capability_key="fake.duplicate")
    duplicate_version = replace(
        first, capability_definition_id=UUID("02800000-0000-4000-8000-000000000099")
    )
    with pytest.raises(ValueError, match="unique identity"):
        BuiltInCapabilityRegistry((first, duplicate_identity))
    with pytest.raises(ValueError, match="unique identity"):
        BuiltInCapabilityRegistry((first, duplicate_version))


def test_handler_resolution_is_explicit_and_registration_is_immutable() -> None:
    original = object()
    replacement = object()
    handlers = {"fake.prepare.v1": original}
    resolver = CapabilityHandlerResolver(handlers)
    handlers["fake.prepare.v1"] = replacement
    assert resolver.resolve(BUILT_IN_CAPABILITIES[0]) is original
    with pytest.raises(CapabilityHandlerNotFoundError):
        resolver.resolve(BUILT_IN_CAPABILITIES[1])


def test_workflow_definitions_pin_exact_capability_references() -> None:
    catalog = BuiltInCapabilityRegistry()
    sequence = BUILT_IN_WORKFLOWS[0]
    assert tuple(step.capability for step in sequence.steps) == tuple(
        catalog.get_enabled(item.capability_key, item.semantic_version).reference
        for item in BUILT_IN_CAPABILITIES
    )
    assert BUILT_IN_WORKFLOWS[1].steps[0].capability is None
    assert BUILT_IN_WORKFLOWS[1].steps[0].department is None
    with pytest.raises(ValueError, match="must match"):
        replace(
            sequence.steps[0],
            capability=CapabilityReference(
                BUILT_IN_CAPABILITIES[0].capability_definition_id,
                "fake.verify",
                SemanticVersion.parse("1.0.0"),
            ),
        )


def test_registry_contains_no_dynamic_loading_or_provider_runtime() -> None:
    root = Path(__file__).resolve().parents[2]
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "packages/core/src/rightjob/registry").glob("*.py")
    )
    assert "importlib" not in source
    assert "eval(" not in source
    assert "temporalio" not in source
    assert "provider_adapters" not in source
