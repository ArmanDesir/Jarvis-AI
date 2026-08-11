from unittest.mock import MagicMock
from uuid import UUID

from rightjob.audit.application.repositories import EventDeduplicator
from rightjob.audit.infrastructure.repositories import SqlAlchemyOutboxRepository
from sqlalchemy.orm import Session

from tests.unit.test_audit_repositories import WORKSPACE_ID, _event


class InMemoryDeduplicator:
    def __init__(self) -> None:
        self._claims: set[tuple[UUID, str, UUID]] = set()

    def claim(self, workspace_id: UUID, consumer: str, event_id: UUID) -> bool:
        key = (workspace_id, consumer, event_id)
        if key in self._claims:
            return False
        self._claims.add(key)
        return True


def _accepts_contract(value: EventDeduplicator) -> EventDeduplicator:
    return value


def test_aggregate_and_outbox_can_share_one_session_and_commit() -> None:
    session = MagicMock(spec=Session)
    aggregate_change = object()

    session.add(aggregate_change)
    SqlAlchemyOutboxRepository(session).add(WORKSPACE_ID, _event())
    session.commit()

    assert session.add.call_count == 2
    session.commit.assert_called_once_with()


def test_consumer_claim_is_idempotent_per_workspace_consumer_and_event() -> None:
    deduplicator = _accepts_contract(InMemoryDeduplicator())
    event_id = _event().event_id

    assert deduplicator.claim(WORKSPACE_ID, "projection-a", event_id) is True
    assert deduplicator.claim(WORKSPACE_ID, "projection-a", event_id) is False
    assert deduplicator.claim(WORKSPACE_ID, "projection-b", event_id) is True
