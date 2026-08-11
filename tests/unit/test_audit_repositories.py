from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from rightjob.audit.infrastructure.models import AuditEntryRecord, OutboxEventRecord
from rightjob.audit.infrastructure.repositories import (
    SqlAlchemyAuditEvidenceRepository,
    SqlAlchemyOutboxRepository,
)
from rightjob.contracts.events import (
    Actor,
    ActorType,
    AuditEvidence,
    AuditOutcome,
    DataSensitivity,
    IntegrationEvent,
)
from sqlalchemy.orm import Session

WORKSPACE_ID = UUID("26000000-0000-4000-8000-000000000001")
OTHER_WORKSPACE_ID = UUID("26000000-0000-4000-8000-000000000099")
EVENT_ID = UUID("26000000-0000-4000-8000-000000000002")
CORRELATION_ID = UUID("26000000-0000-4000-8000-000000000003")
NOW = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)


def _session() -> MagicMock:
    return MagicMock(spec=Session)


def _event() -> IntegrationEvent:
    return IntegrationEvent(
        event_id=EVENT_ID,
        event_type="workspace.updated",
        event_version=1,
        schema_version=1,
        occurred_at=NOW,
        workspace_id=WORKSPACE_ID,
        actor=Actor(ActorType.USER, "user-1"),
        correlation_id=CORRELATION_ID,
        producer="identity",
        sensitivity=DataSensitivity.INTERNAL,
        payload={"name": "Updated"},
        idempotency_key="workspace-update-1",
    )


def _evidence() -> AuditEvidence:
    return AuditEvidence(
        id=EVENT_ID,
        workspace_id=WORKSPACE_ID,
        actor=Actor(ActorType.USER, "user-1"),
        action="identity.workspace.update",
        resource_type="workspace",
        resource_id=str(WORKSPACE_ID),
        outcome=AuditOutcome.SUCCEEDED,
        correlation_id=CORRELATION_ID,
        occurred_at=NOW,
    )


def test_append_adds_audit_record_after_setting_workspace_context() -> None:
    session = _session()

    SqlAlchemyAuditEvidenceRepository(session).append(WORKSPACE_ID, _evidence())

    record = session.add.call_args.args[0]
    assert isinstance(record, AuditEntryRecord)
    assert record.workspace_id == WORKSPACE_ID
    assert record.correlation_id == CORRELATION_ID
    session.execute.assert_called_once()


def test_outbox_add_maps_versioned_event_and_idempotency_key() -> None:
    session = _session()

    SqlAlchemyOutboxRepository(session).add(WORKSPACE_ID, _event())

    record = session.add.call_args.args[0]
    assert isinstance(record, OutboxEventRecord)
    assert record.id == EVENT_ID
    assert record.event_version == 1
    assert record.schema_version == 1
    assert record.idempotency_key == "workspace-update-1"
    assert record.published_at is None


@pytest.mark.parametrize("repository", ["audit", "outbox"])
def test_workspace_mismatch_fails_before_session_use(repository: str) -> None:
    session = _session()

    with pytest.raises(ValueError, match="workspace must match"):
        if repository == "audit":
            SqlAlchemyAuditEvidenceRepository(session).append(OTHER_WORKSPACE_ID, _evidence())
        else:
            SqlAlchemyOutboxRepository(session).add(OTHER_WORKSPACE_ID, _event())

    session.execute.assert_not_called()
    session.add.assert_not_called()


def test_pending_list_requires_bounded_positive_limit() -> None:
    session = _session()

    with pytest.raises(ValueError, match="limit must be positive"):
        SqlAlchemyOutboxRepository(session).list_pending(WORKSPACE_ID, 0)

    session.execute.assert_not_called()


def test_mark_published_rejects_naive_timestamp_before_database_use() -> None:
    session = _session()

    with pytest.raises(ValueError, match="timezone-aware"):
        SqlAlchemyOutboxRepository(session).mark_published(
            WORKSPACE_ID, EVENT_ID, datetime(2026, 8, 11)
        )

    session.execute.assert_not_called()
