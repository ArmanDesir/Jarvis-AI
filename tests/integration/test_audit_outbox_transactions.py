from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
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
from rightjob.identity.infrastructure.repositories import SqlAlchemyWorkspaceRepository
from sqlalchemy import create_engine, insert, text
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

OWNER_URL = os.environ.get("RIGHTJOB_DATABASE_URL")
APP_URL = os.environ.get("RIGHTJOB_PHASE26_RLS_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not OWNER_URL or not APP_URL, reason="isolated Phase 2.6 URLs required"),
]

WORKSPACE_A = UUID("0198ff00-0000-7000-8000-000000000001")
WORKSPACE_B = UUID("0198ff00-0000-7000-8000-000000000002")
USER_A = UUID("0198ff00-0000-7000-8000-000000000011")
USER_B = UUID("0198ff00-0000-7000-8000-000000000012")
MEMBERSHIP_A = UUID("0198ff00-0000-7000-8000-000000000021")
MEMBERSHIP_B = UUID("0198ff00-0000-7000-8000-000000000022")

AUDIT_COMMITTED_A = UUID("02600000-0000-4000-8000-000000000001")
AUDIT_ROLLBACK_A = UUID("02600000-0000-4000-8000-000000000002")
AUDIT_ISOLATION_B = UUID("02600000-0000-4000-8000-000000000003")
AUDIT_APPEND_ONLY_A = UUID("02600000-0000-4000-8000-000000000004")
OUTBOX_COMMITTED_A = UUID("02600000-0000-4000-8000-000000000011")
OUTBOX_ROLLBACK_A = UUID("02600000-0000-4000-8000-000000000012")
OUTBOX_ISOLATION_B = UUID("02600000-0000-4000-8000-000000000013")
OUTBOX_DUPLICATE_A = UUID("02600000-0000-4000-8000-000000000014")

AUDIT_IDS = (AUDIT_COMMITTED_A, AUDIT_ROLLBACK_A, AUDIT_ISOLATION_B, AUDIT_APPEND_ONLY_A)
OUTBOX_IDS = (OUTBOX_COMMITTED_A, OUTBOX_ROLLBACK_A, OUTBOX_ISOLATION_B, OUTBOX_DUPLICATE_A)
APP_ROLE = "rightjob_phase26_rls_verifier"
NOW = datetime(2026, 8, 11, 13, tzinfo=timezone.utc)
CORRELATION_ID = UUID("02600000-0000-4000-8000-000000000101")
CAUSATION_ID = UUID("02600000-0000-4000-8000-000000000102")


def _audit(
    evidence_id: UUID,
    workspace_id: UUID,
    *,
    action: str = "identity.workspace.updated",
) -> AuditEvidence:
    return AuditEvidence(
        id=evidence_id,
        workspace_id=workspace_id,
        actor=Actor(ActorType.USER, str(USER_A)),
        action=action,
        resource_type="workspace",
        resource_id=str(workspace_id),
        outcome=AuditOutcome.SUCCEEDED,
        correlation_id=CORRELATION_ID,
        causation_id=CAUSATION_ID,
        occurred_at=NOW,
        before={"name": "Workspace A"},
        after={"name": "Workspace A committed"},
    )


def _outbox(
    event_id: UUID,
    workspace_id: UUID,
    *,
    idempotency_key: str,
) -> IntegrationEvent:
    return IntegrationEvent(
        event_id=event_id,
        event_type="workspace.updated",
        event_version=1,
        schema_version=1,
        occurred_at=NOW,
        workspace_id=workspace_id,
        actor=Actor(ActorType.USER, str(USER_A)),
        correlation_id=CORRELATION_ID,
        causation_id=CAUSATION_ID,
        producer="identity",
        sensitivity=DataSensitivity.INTERNAL,
        payload={"workspace_id": str(workspace_id)},
        idempotency_key=idempotency_key,
    )


@contextmanager
def _context(engine: Engine, workspace_id: UUID | None) -> Iterator[Connection]:
    with engine.begin() as connection:
        if workspace_id is not None:
            connection.execute(
                text("SELECT set_config('app.current_workspace_id', :workspace_id, true)"),
                {"workspace_id": str(workspace_id)},
            )
        yield connection


def _delete_exact_fixtures(connection: Connection) -> None:
    connection.execute(
        text(
            "DELETE FROM outbox_events WHERE "
            "(workspace_id = :wa AND id IN (:o1, :o2, :o4)) OR "
            "(workspace_id = :wb AND id = :o3)"
        ),
        {
            "wa": WORKSPACE_A,
            "wb": WORKSPACE_B,
            "o1": OUTBOX_COMMITTED_A,
            "o2": OUTBOX_ROLLBACK_A,
            "o3": OUTBOX_ISOLATION_B,
            "o4": OUTBOX_DUPLICATE_A,
        },
    )
    connection.execute(
        text(
            "DELETE FROM audit_entries WHERE "
            "(workspace_id = :wa AND id IN (:a1, :a2, :a4)) OR "
            "(workspace_id = :wb AND id = :a3)"
        ),
        {
            "wa": WORKSPACE_A,
            "wb": WORKSPACE_B,
            "a1": AUDIT_COMMITTED_A,
            "a2": AUDIT_ROLLBACK_A,
            "a3": AUDIT_ISOLATION_B,
            "a4": AUDIT_APPEND_ONLY_A,
        },
    )
    connection.execute(
        text(
            "DELETE FROM memberships WHERE "
            "(workspace_id = :wa AND id = :ma) OR (workspace_id = :wb AND id = :mb)"
        ),
        {"wa": WORKSPACE_A, "wb": WORKSPACE_B, "ma": MEMBERSHIP_A, "mb": MEMBERSHIP_B},
    )
    connection.execute(
        text("DELETE FROM users WHERE id IN (:ua, :ub)"), {"ua": USER_A, "ub": USER_B}
    )
    connection.execute(
        text("DELETE FROM workspaces WHERE id IN (:wa, :wb)"),
        {"wa": WORKSPACE_A, "wb": WORKSPACE_B},
    )


def _drop_role(connection: Connection) -> None:
    connection.execute(text(f"REVOKE ALL ON audit_entries FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE ALL ON outbox_events FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE ALL ON users FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE ALL ON workspaces FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE ALL ON SCHEMA public FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE CONNECT ON DATABASE rightjob_phase16 FROM {APP_ROLE}"))
    connection.execute(text(f"DROP ROLE {APP_ROLE}"))


@pytest.fixture(scope="module")
def phase26_engines() -> Iterator[tuple[Engine, Engine]]:
    assert OWNER_URL and APP_URL
    owner = create_engine(OWNER_URL)
    app = create_engine(APP_URL)
    with owner.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260811_0002"
        assert connection.execute(
            text(
                "SELECT (SELECT count(*) FROM workspaces), (SELECT count(*) FROM users), "
                "(SELECT count(*) FROM memberships), (SELECT count(*) FROM audit_entries), "
                "(SELECT count(*) FROM outbox_events)"
            )
        ).one() == (0, 0, 0, 0, 0)
        assert not connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :role)"),
            {"role": APP_ROLE},
        )
        connection.execute(
            text(
                f"CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOINHERIT NOBYPASSRLS"
            )
        )
        connection.execute(text(f"GRANT CONNECT ON DATABASE rightjob_phase16 TO {APP_ROLE}"))
        connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
        connection.execute(text(f"GRANT SELECT ON users TO {APP_ROLE}"))
        connection.execute(text(f"GRANT SELECT, UPDATE ON workspaces TO {APP_ROLE}"))
        connection.execute(text(f"GRANT SELECT, INSERT ON audit_entries TO {APP_ROLE}"))
        connection.execute(text(f"GRANT SELECT, INSERT, UPDATE ON outbox_events TO {APP_ROLE}"))
        connection.execute(
            text(
                "INSERT INTO workspaces "
                "(id, name, slug, status, timezone, locale, settings) VALUES "
                "(:wa, 'Workspace A', 'workspace-a', 'active', 'UTC', 'en', '{}'), "
                "(:wb, 'Workspace B', 'workspace-b', 'active', 'UTC', 'en', '{}')"
            ),
            {"wa": WORKSPACE_A, "wb": WORKSPACE_B},
        )
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, external_identity_provider, external_subject, email, display_name, status) "
                "VALUES (:ua, 'test', 'a', 'a@example.test', 'A', 'active'), "
                "(:ub, 'test', 'b', 'b@example.test', 'B', 'active')"
            ),
            {"ua": USER_A, "ub": USER_B},
        )
        connection.execute(
            text(
                "INSERT INTO memberships (id, workspace_id, user_id, role, status) VALUES "
                "(:ma, :wa, :ua, 'owner', 'active'), (:mb, :wb, :ub, 'owner', 'active')"
            ),
            {
                "ma": MEMBERSHIP_A,
                "mb": MEMBERSHIP_B,
                "wa": WORKSPACE_A,
                "wb": WORKSPACE_B,
                "ua": USER_A,
                "ub": USER_B,
            },
        )
        isolation_audit = _audit(AUDIT_ISOLATION_B, WORKSPACE_B)
        connection.execute(
            insert(AuditEntryRecord),
            {
                "id": isolation_audit.id,
                "workspace_id": isolation_audit.workspace_id,
                "actor_type": isolation_audit.actor.type.value,
                "actor_id": isolation_audit.actor.id,
                "action": isolation_audit.action,
                "resource_type": isolation_audit.resource_type,
                "resource_id": isolation_audit.resource_id,
                "outcome": isolation_audit.outcome.value,
                "correlation_id": isolation_audit.correlation_id,
                "causation_id": isolation_audit.causation_id,
                "before_json": isolation_audit.before,
                "after_json": isolation_audit.after,
                "sensitivity": isolation_audit.sensitivity.value,
                "occurred_at": isolation_audit.occurred_at,
                "created_at": NOW,
            },
        )
        isolation_event = _outbox(
            OUTBOX_ISOLATION_B, WORKSPACE_B, idempotency_key="workspace-b-update"
        )
        connection.execute(
            insert(OutboxEventRecord),
            {
                "id": isolation_event.event_id,
                "workspace_id": isolation_event.workspace_id,
                "event_type": isolation_event.event_type,
                "event_version": isolation_event.event_version,
                "schema_version": isolation_event.schema_version,
                "occurred_at": isolation_event.occurred_at,
                "actor_type": isolation_event.actor.type.value,
                "actor_id": isolation_event.actor.id,
                "correlation_id": isolation_event.correlation_id,
                "causation_id": isolation_event.causation_id,
                "producer": isolation_event.producer,
                "sensitivity": isolation_event.sensitivity.value,
                "payload_json": isolation_event.payload,
                "idempotency_key": isolation_event.idempotency_key,
                "attempts": 0,
                "created_at": NOW,
            },
        )
    try:
        yield owner, app
    finally:
        app.dispose()
        with owner.begin() as connection:
            _delete_exact_fixtures(connection)
            _drop_role(connection)
        owner.dispose()


def test_role_is_minimal_non_bypass_and_append_only(
    phase26_engines: tuple[Engine, Engine],
) -> None:
    owner, app = phase26_engines
    with owner.connect() as connection:
        assert connection.execute(
            text(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolbypassrls "
                "FROM pg_roles WHERE rolname = :role"
            ),
            {"role": APP_ROLE},
        ).one() == (False, False, False, False, False)
        grants = connection.execute(
            text(
                "SELECT table_name, privilege_type FROM information_schema.role_table_grants "
                "WHERE grantee = :role ORDER BY table_name, privilege_type"
            ),
            {"role": APP_ROLE},
        ).all()
    assert grants == [
        ("audit_entries", "INSERT"),
        ("audit_entries", "SELECT"),
        ("outbox_events", "INSERT"),
        ("outbox_events", "SELECT"),
        ("outbox_events", "UPDATE"),
        ("users", "SELECT"),
        ("workspaces", "SELECT"),
        ("workspaces", "UPDATE"),
    ]

    with Session(app) as session, session.begin():
        SqlAlchemyAuditEvidenceRepository(session).append(
            WORKSPACE_A, _audit(AUDIT_APPEND_ONLY_A, WORKSPACE_A, action="audit.append.proved")
        )
    with (
        pytest.raises(ProgrammingError, match="permission denied"),
        _context(app, WORKSPACE_A) as connection,
    ):
        connection.execute(
            text("UPDATE audit_entries SET outcome = 'failed' WHERE id = :id"),
            {"id": AUDIT_APPEND_ONLY_A},
        )
    with (
        pytest.raises(ProgrammingError, match="permission denied"),
        _context(app, WORKSPACE_A) as connection,
    ):
        connection.execute(
            text("DELETE FROM audit_entries WHERE id = :id"),
            {"id": AUDIT_APPEND_ONLY_A},
        )


def test_atomic_workspace_audit_outbox_commit_once(
    phase26_engines: tuple[Engine, Engine],
) -> None:
    owner, app = phase26_engines
    commit_count = 0

    def count_commit(session: Session) -> None:
        nonlocal commit_count
        commit_count += 1

    with Session(app, expire_on_commit=False) as session:
        sqlalchemy_event.listen(session, "after_commit", count_commit)
        workspaces = SqlAlchemyWorkspaceRepository(session)
        audit = SqlAlchemyAuditEvidenceRepository(session)
        outbox = SqlAlchemyOutboxRepository(session)
        workspace = workspaces.get(WORKSPACE_A)
        assert workspace is not None
        saved = workspaces.save(workspace=replace(workspace, name="Workspace A committed"))
        audit.append(WORKSPACE_A, _audit(AUDIT_COMMITTED_A, WORKSPACE_A))
        outbox.add(
            WORKSPACE_A,
            _outbox(OUTBOX_COMMITTED_A, WORKSPACE_A, idempotency_key="workspace-a-update"),
        )
        session.commit()
        sqlalchemy_event.remove(session, "after_commit", count_commit)
    assert commit_count == 1
    assert saved.version == 2
    with owner.connect() as connection:
        assert connection.execute(
            text("SELECT name, version FROM workspaces WHERE id = :id"), {"id": WORKSPACE_A}
        ).one() == ("Workspace A committed", 2)
        assert connection.execute(
            text(
                "SELECT workspace_id, correlation_id, causation_id FROM audit_entries "
                "WHERE id = :id"
            ),
            {"id": AUDIT_COMMITTED_A},
        ).one() == (WORKSPACE_A, CORRELATION_ID, CAUSATION_ID)
        assert connection.execute(
            text(
                "SELECT workspace_id, correlation_id, causation_id FROM outbox_events "
                "WHERE id = :id"
            ),
            {"id": OUTBOX_COMMITTED_A},
        ).one() == (WORKSPACE_A, CORRELATION_ID, CAUSATION_ID)


def test_rollback_leaves_no_partial_state(phase26_engines: tuple[Engine, Engine]) -> None:
    owner, app = phase26_engines
    pool = app.pool
    assert isinstance(pool, QueuePool)
    with pytest.raises(RuntimeError, match="rollback proof"), Session(app) as session:
        workspaces = SqlAlchemyWorkspaceRepository(session)
        audit = SqlAlchemyAuditEvidenceRepository(session)
        outbox = SqlAlchemyOutboxRepository(session)
        workspace = workspaces.get(WORKSPACE_A)
        assert workspace is not None
        workspaces.save(replace(workspace, name="Must roll back"))
        audit.append(WORKSPACE_A, _audit(AUDIT_ROLLBACK_A, WORKSPACE_A))
        outbox.add(
            WORKSPACE_A,
            _outbox(OUTBOX_ROLLBACK_A, WORKSPACE_A, idempotency_key="workspace-a-rollback"),
        )
        raise RuntimeError("rollback proof")
    assert pool.checkedout() == 0
    with owner.connect() as connection:
        assert connection.execute(
            text("SELECT name, version FROM workspaces WHERE id = :id"), {"id": WORKSPACE_A}
        ).one() == ("Workspace A committed", 2)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM audit_entries WHERE id = :id"), {"id": AUDIT_ROLLBACK_A}
            )
            == 0
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM outbox_events WHERE id = :id"),
                {"id": OUTBOX_ROLLBACK_A},
            )
            == 0
        )


def test_outbox_idempotency_and_duplicate_event_id(
    phase26_engines: tuple[Engine, Engine],
) -> None:
    owner, app = phase26_engines
    with Session(app) as session:
        with pytest.raises(IntegrityError, match="uq_outbox_events_workspace_idempotency"):
            SqlAlchemyOutboxRepository(session).add(
                WORKSPACE_A,
                _outbox(
                    OUTBOX_DUPLICATE_A,
                    WORKSPACE_A,
                    idempotency_key="workspace-a-update",
                ),
            )
            session.commit()
        session.rollback()
    with Session(app) as session:
        with pytest.raises(IntegrityError, match="pk_outbox_events"):
            SqlAlchemyOutboxRepository(session).add(
                WORKSPACE_A,
                _outbox(
                    OUTBOX_COMMITTED_A,
                    WORKSPACE_A,
                    idempotency_key="workspace-a-other",
                ),
            )
            session.commit()
        session.rollback()
    with owner.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM outbox_events "
                    "WHERE workspace_id = :workspace_id AND idempotency_key = :key"
                ),
                {"workspace_id": WORKSPACE_A, "key": "workspace-a-update"},
            )
            == 1
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM outbox_events WHERE id = :id"),
                {"id": OUTBOX_DUPLICATE_A},
            )
            == 0
        )


def test_workspace_isolation_and_missing_context_fail_closed(
    phase26_engines: tuple[Engine, Engine],
) -> None:
    _, app = phase26_engines
    with _context(app, WORKSPACE_A) as connection:
        assert set(
            connection.execute(text("SELECT workspace_id FROM audit_entries")).scalars()
        ) == {WORKSPACE_A}
        assert set(
            connection.execute(text("SELECT workspace_id FROM outbox_events")).scalars()
        ) == {WORKSPACE_A}
        assert (
            connection.execute(
                text("UPDATE outbox_events SET attempts = attempts + 1 WHERE id = :id"),
                {"id": OUTBOX_ISOLATION_B},
            ).rowcount
            == 0
        )
    with (
        pytest.raises(DBAPIError, match="row-level security"),
        _context(app, WORKSPACE_A) as connection,
    ):
        connection.execute(
            text(
                "INSERT INTO audit_entries "
                "(id, workspace_id, actor_type, actor_id, action, resource_type, resource_id, "
                "outcome, correlation_id, sensitivity, occurred_at, created_at) VALUES "
                "(:id, :wb, 'user', 'user-a', 'denied', 'workspace', :resource_id, "
                "'denied', :correlation_id, 'internal', :now, :now)"
            ),
            {
                "id": AUDIT_ROLLBACK_A,
                "wb": WORKSPACE_B,
                "resource_id": str(WORKSPACE_B),
                "correlation_id": CORRELATION_ID,
                "now": NOW,
            },
        )
    with _context(app, None) as connection:
        assert connection.execute(text("SELECT id FROM audit_entries")).all() == []
        assert connection.execute(text("SELECT id FROM outbox_events")).all() == []
    with pytest.raises(DBAPIError, match="row-level security"), _context(app, None) as connection:
        connection.execute(
            text(
                "INSERT INTO outbox_events "
                "(id, workspace_id, event_type, event_version, schema_version, occurred_at, "
                "actor_type, actor_id, correlation_id, producer, sensitivity, payload_json, "
                "idempotency_key, attempts, created_at) VALUES "
                "(:id, :wa, 'workspace.updated', 1, 1, :now, 'user', 'user-a', "
                ":correlation_id, 'identity', 'internal', '{}', 'missing-context', 0, :now)"
            ),
            {
                "id": OUTBOX_ROLLBACK_A,
                "wa": WORKSPACE_A,
                "correlation_id": CORRELATION_ID,
                "now": NOW,
            },
        )


def test_forced_rls_policies_and_publication_update(
    phase26_engines: tuple[Engine, Engine],
) -> None:
    owner, app = phase26_engines
    with owner.connect() as connection:
        assert connection.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname IN ('audit_entries', 'outbox_events') ORDER BY relname"
            )
        ).all() == [
            ("audit_entries", True, True),
            ("outbox_events", True, True),
        ]
        assert connection.execute(
            text(
                "SELECT tablename, policyname, cmd FROM pg_policies "
                "WHERE schemaname = 'public' AND tablename IN "
                "('audit_entries', 'outbox_events') ORDER BY tablename"
            )
        ).all() == [
            ("audit_entries", "audit_entries_workspace_isolation", "ALL"),
            ("outbox_events", "outbox_events_workspace_isolation", "ALL"),
        ]
    published_at = datetime(2026, 8, 11, 14, tzinfo=timezone.utc)
    with Session(app) as session, session.begin():
        SqlAlchemyOutboxRepository(session).mark_published(
            WORKSPACE_A, OUTBOX_COMMITTED_A, published_at
        )
    with owner.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT published_at FROM outbox_events WHERE id = :id"),
                {"id": OUTBOX_COMMITTED_A},
            )
            == published_at
        )
