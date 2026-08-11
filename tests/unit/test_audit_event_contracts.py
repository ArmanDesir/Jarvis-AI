from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import UUID

import pytest
from rightjob.contracts.events import (
    Actor,
    ActorType,
    AuditEvidence,
    AuditOutcome,
    DataSensitivity,
    IntegrationEvent,
)

WORKSPACE_ID = UUID("26000000-0000-4000-8000-000000000001")
EVENT_ID = UUID("26000000-0000-4000-8000-000000000002")
CORRELATION_ID = UUID("26000000-0000-4000-8000-000000000003")
CAUSATION_ID = UUID("26000000-0000-4000-8000-000000000004")
NOW = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)


def event(**changes: object) -> IntegrationEvent:
    values: dict[str, object] = {
        "event_id": EVENT_ID,
        "event_type": "workspace.updated",
        "event_version": 1,
        "schema_version": 1,
        "occurred_at": NOW,
        "workspace_id": WORKSPACE_ID,
        "actor": Actor(ActorType.USER, "user-1"),
        "correlation_id": CORRELATION_ID,
        "causation_id": CAUSATION_ID,
        "producer": "identity",
        "sensitivity": DataSensitivity.INTERNAL,
        "payload": {"name": "Updated"},
        "idempotency_key": "workspace-update-1",
    }
    values.update(changes)
    return IntegrationEvent(**values)  # type: ignore[arg-type]


def test_event_preserves_producer_owned_semantics_and_causation() -> None:
    value = event()

    assert value.event_type == "workspace.updated"
    assert value.producer == "identity"
    assert value.workspace_id == WORKSPACE_ID
    assert value.correlation_id == CORRELATION_ID
    assert value.causation_id == CAUSATION_ID


def test_event_envelope_is_frozen() -> None:
    value = event()

    with pytest.raises(FrozenInstanceError):
        value.event_type = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"event_version": 0}, "versions must be positive"),
        ({"occurred_at": datetime(2026, 8, 11)}, "timezone-aware"),
        ({"payload": {"token": "unsafe"}}, "secret-bearing field"),
    ],
)
def test_event_rejects_invalid_or_secret_bearing_content(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        event(**changes)


def test_audit_evidence_is_typed_append_only_input() -> None:
    evidence = AuditEvidence(
        id=EVENT_ID,
        workspace_id=WORKSPACE_ID,
        actor=Actor(ActorType.SERVICE, "identity-api"),
        action="identity.workspace.update",
        resource_type="workspace",
        resource_id=str(WORKSPACE_ID),
        outcome=AuditOutcome.SUCCEEDED,
        correlation_id=CORRELATION_ID,
        causation_id=CAUSATION_ID,
        occurred_at=NOW,
        before={"name": "Before"},
        after={"name": "After"},
    )

    assert evidence.outcome is AuditOutcome.SUCCEEDED
    assert evidence.before == {"name": "Before"}
    assert evidence.after == {"name": "After"}
