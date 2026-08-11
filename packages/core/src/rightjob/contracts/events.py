"""Provider-neutral audit and integration-event contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TypeAlias
from uuid import UUID

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

_SECRET_KEYS = frozenset({"authorization", "credential", "password", "secret", "token"})


class ActorType(StrEnum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"
    SERVICE = "service"
    PROVIDER = "provider"


class DataSensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class AuditOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class Actor:
    type: ActorType
    id: str

    def __post_init__(self) -> None:
        _require_text("actor.id", self.id)


@dataclass(frozen=True, slots=True)
class AuditEvidence:
    id: UUID
    workspace_id: UUID
    actor: Actor
    action: str
    resource_type: str
    resource_id: str
    outcome: AuditOutcome
    correlation_id: UUID
    occurred_at: datetime
    sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    causation_id: UUID | None = None
    policy_ref: str | None = None
    approval_ref: str | None = None
    before: dict[str, JsonValue] | None = None
    after: dict[str, JsonValue] | None = None
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        _require_text("action", self.action)
        _require_text("resource_type", self.resource_type)
        _require_text("resource_id", self.resource_id)
        _require_aware("occurred_at", self.occurred_at)
        _require_safe_json(self.before)
        _require_safe_json(self.after)


@dataclass(frozen=True, slots=True)
class IntegrationEvent:
    event_id: UUID
    event_type: str
    event_version: int
    schema_version: int
    occurred_at: datetime
    workspace_id: UUID
    actor: Actor
    correlation_id: UUID
    producer: str
    sensitivity: DataSensitivity
    payload: dict[str, JsonValue]
    idempotency_key: str
    causation_id: UUID | None = None

    def __post_init__(self) -> None:
        _require_text("event_type", self.event_type)
        _require_text("producer", self.producer)
        _require_text("idempotency_key", self.idempotency_key)
        if self.event_version < 1 or self.schema_version < 1:
            raise ValueError("event and schema versions must be positive")
        _require_aware("occurred_at", self.occurred_at)
        _require_safe_json(self.payload)


def _require_text(field: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field} must not be empty")


def _require_aware(field: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")


def _require_safe_json(value: JsonValue) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in _SECRET_KEYS:
                raise ValueError(f"secret-bearing field is not permitted: {key}")
            _require_safe_json(item)
    elif isinstance(value, list):
        for item in value:
            _require_safe_json(item)
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise ValueError("payload must contain JSON-compatible values")
