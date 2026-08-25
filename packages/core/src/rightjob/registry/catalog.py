"""Immutable code-owned catalog of approved synthetic capabilities."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Sequence
from uuid import UUID

from rightjob.contracts.capabilities import (
    CapabilityDefinition,
    ContractReference,
    EffectClassification,
    IdempotencyClassification,
    RetryableFailure,
    RetryMetadata,
    SemanticVersion,
    TimeoutMetadata,
)

VERSION_1 = SemanticVersion.parse("1.0.0")
SYNTHETIC_OWNER = "synthetic.foundation"


def _contract(key: str) -> ContractReference:
    return ContractReference(key, VERSION_1, 4_096)


BUILT_IN_CAPABILITIES: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        UUID("02800000-0000-4000-8000-000000000001"),
        "fake.prepare",
        VERSION_1,
        SYNTHETIC_OWNER,
        "Synthetic Prepare",
        "Prepares bounded synthetic input without external effects.",
        True,
        _contract("fake.prepare.input"),
        _contract("fake.prepare.output"),
        "fake.prepare.v1",
        EffectClassification.READ_ONLY,
        IdempotencyClassification.NATURALLY_IDEMPOTENT,
        TimeoutMetadata(30),
        RetryMetadata(1),
    ),
    CapabilityDefinition(
        UUID("02800000-0000-4000-8000-000000000002"),
        "fake.transform",
        VERSION_1,
        SYNTHETIC_OWNER,
        "Synthetic Transform",
        "Transforms bounded synthetic input without external effects.",
        True,
        _contract("fake.transform.input"),
        _contract("fake.transform.output"),
        "fake.transform.v1",
        EffectClassification.REVERSIBLE,
        IdempotencyClassification.REQUIRES_IDEMPOTENCY_KEY,
        TimeoutMetadata(30),
        RetryMetadata(3, frozenset({RetryableFailure.TRANSIENT_DEPENDENCY})),
    ),
    CapabilityDefinition(
        UUID("02800000-0000-4000-8000-000000000003"),
        "fake.verify",
        VERSION_1,
        SYNTHETIC_OWNER,
        "Synthetic Verify",
        "Verifies bounded synthetic output without external effects.",
        True,
        _contract("fake.verify.input"),
        _contract("fake.verify.output"),
        "fake.verify.v1",
        EffectClassification.READ_ONLY,
        IdempotencyClassification.NATURALLY_IDEMPOTENT,
        TimeoutMetadata(30),
        RetryMetadata(1),
    ),
)


class CapabilityNotFoundError(LookupError):
    """The requested capability key and exact version are not registered."""


class CapabilityDisabledError(LookupError):
    """The requested capability exists but is disabled."""


class BuiltInCapabilityRegistry:
    def __init__(self, definitions: Sequence[CapabilityDefinition] = BUILT_IN_CAPABILITIES) -> None:
        by_identity = {
            definition.capability_definition_id: definition for definition in definitions
        }
        by_version = {
            (definition.capability_key, definition.semantic_version): definition
            for definition in definitions
        }
        if len(by_identity) != len(definitions) or len(by_version) != len(definitions):
            raise ValueError("capability definitions require unique identity and key/version")
        ordered = tuple(
            sorted(definitions, key=lambda item: (item.capability_key, str(item.semantic_version)))
        )
        self._definitions = ordered
        self._by_version: Mapping[tuple[str, SemanticVersion], CapabilityDefinition] = (
            MappingProxyType(by_version)
        )

    def get(self, capability_key: str, version: SemanticVersion) -> CapabilityDefinition:
        try:
            return self._by_version[(capability_key, version)]
        except KeyError as error:
            raise CapabilityNotFoundError("capability definition is unavailable") from error

    def get_enabled(self, capability_key: str, version: SemanticVersion) -> CapabilityDefinition:
        definition = self.get(capability_key, version)
        if not definition.enabled:
            raise CapabilityDisabledError("capability definition is disabled")
        return definition

    def latest_enabled(self, capability_key: str) -> CapabilityDefinition:
        candidates = tuple(
            definition
            for definition in self._definitions
            if definition.capability_key == capability_key and definition.enabled
        )
        if not candidates:
            raise CapabilityNotFoundError("enabled capability definition is unavailable")
        return max(
            candidates,
            key=lambda item: (item.semantic_version.precedence(), str(item.semantic_version)),
        )

    def list_enabled(self) -> Sequence[CapabilityDefinition]:
        return tuple(definition for definition in self._definitions if definition.enabled)

    def list_by_owner(
        self, owner_key: str, *, enabled_only: bool = True
    ) -> Sequence[CapabilityDefinition]:
        return tuple(
            definition
            for definition in self._definitions
            if definition.owner_key == owner_key and (definition.enabled or not enabled_only)
        )
