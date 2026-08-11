from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import pytest
from rightjob.identity.application.authentication import ExternalIdentity
from rightjob.identity.application.service import IdentityService
from rightjob.identity.infrastructure.repositories import (
    SqlAlchemyMembershipRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
)
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

OWNER_URL = os.environ.get("RIGHTJOB_DATABASE_URL")
APP_URL = os.environ.get("RIGHTJOB_RLS_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not OWNER_URL or not APP_URL, reason="isolated PostgreSQL URLs required"),
]

WORKSPACE_A = UUID("0198ff00-0000-7000-8000-000000000001")
WORKSPACE_B = UUID("0198ff00-0000-7000-8000-000000000002")
USER_A = UUID("0198ff00-0000-7000-8000-000000000011")
USER_B = UUID("0198ff00-0000-7000-8000-000000000012")
MEMBERSHIP_A = UUID("0198ff00-0000-7000-8000-000000000021")
MEMBERSHIP_B = UUID("0198ff00-0000-7000-8000-000000000022")
APP_ROLE = "rightjob_phase21_rls_verifier"


def _drop_verification_role(connection: Connection) -> None:
    connection.execute(text(f"REVOKE ALL ON memberships FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE ALL ON users FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE ALL ON workspaces FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE ALL ON SCHEMA public FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE CONNECT ON DATABASE rightjob_phase16 FROM {APP_ROLE}"))
    connection.execute(text(f"DROP ROLE IF EXISTS {APP_ROLE}"))


def _delete_fixture_records(connection: Connection) -> None:
    connection.execute(
        text("DELETE FROM memberships WHERE id IN (:ma, :mb)"),
        {"ma": MEMBERSHIP_A, "mb": MEMBERSHIP_B},
    )
    connection.execute(
        text("DELETE FROM users WHERE id IN (:ua, :ub)"), {"ua": USER_A, "ub": USER_B}
    )
    connection.execute(
        text("DELETE FROM workspaces WHERE id IN (:wa, :wb)"),
        {"wa": WORKSPACE_A, "wb": WORKSPACE_B},
    )


@contextmanager
def _context(engine: Engine, workspace_id: UUID | None) -> Iterator[Connection]:
    with engine.begin() as connection:
        if workspace_id:
            connection.execute(
                text("SELECT set_config('app.current_workspace_id', :workspace_id, true)"),
                {"workspace_id": str(workspace_id)},
            )
        yield connection


@pytest.fixture(scope="module")
def rls_engines() -> Iterator[tuple[Engine, Engine]]:
    assert OWNER_URL and APP_URL
    owner = create_engine(OWNER_URL)
    app = create_engine(APP_URL)
    with owner.begin() as connection:
        role_exists = connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :role)"),
            {"role": APP_ROLE},
        )
        if role_exists:
            _drop_verification_role(connection)
        _delete_fixture_records(connection)
        connection.execute(
            text(
                f"CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOINHERIT NOBYPASSRLS"
            )
        )
        connection.execute(text(f"GRANT CONNECT ON DATABASE rightjob_phase16 TO {APP_ROLE}"))
        connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
        connection.execute(
            text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON memberships TO {APP_ROLE}")
        )
        connection.execute(text(f"GRANT SELECT ON users, workspaces TO {APP_ROLE}"))
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
    try:
        yield owner, app
    finally:
        app.dispose()
        with owner.begin() as connection:
            _delete_fixture_records(connection)
            _drop_verification_role(connection)
        owner.dispose()


def test_workspace_a_reads_only_its_membership(rls_engines: tuple[Engine, Engine]) -> None:
    _, app = rls_engines
    with _context(app, WORKSPACE_A) as connection:
        rows = connection.execute(text("SELECT workspace_id FROM memberships")).scalars().all()
    assert rows == [WORKSPACE_A]


def test_repository_query_is_explicitly_workspace_scoped(
    rls_engines: tuple[Engine, Engine],
) -> None:
    _, app = rls_engines
    with Session(app) as session, session.begin():
        memberships = SqlAlchemyMembershipRepository(session).list_for_workspace(WORKSPACE_A)
    assert [membership.workspace_id for membership in memberships] == [WORKSPACE_A]


def test_identity_service_resolution_is_read_only(rls_engines: tuple[Engine, Engine]) -> None:
    owner, app = rls_engines
    with owner.connect() as connection:
        before = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM workspaces), "
                "(SELECT count(*) FROM users), (SELECT count(*) FROM memberships)"
            )
        ).one()
    with Session(app) as session, session.begin():
        context = IdentityService(
            SqlAlchemyUserRepository(session),
            SqlAlchemyMembershipRepository(session),
            SqlAlchemyWorkspaceRepository(session),
        ).resolve(ExternalIdentity("test", "a"), WORKSPACE_A)
    with owner.connect() as connection:
        after = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM workspaces), "
                "(SELECT count(*) FROM users), (SELECT count(*) FROM memberships)"
            )
        ).one()
    assert context.principal.user_id == USER_A
    assert context.principal.workspace_id == WORKSPACE_A
    assert before == after == (2, 2, 2)


def test_cross_workspace_insert_is_denied(rls_engines: tuple[Engine, Engine]) -> None:
    _, app = rls_engines
    with (
        pytest.raises(DBAPIError, match="row-level security"),
        _context(app, WORKSPACE_A) as connection,
    ):
        connection.execute(
            text(
                "INSERT INTO memberships "
                "(id, workspace_id, user_id, role, status) VALUES "
                "(gen_random_uuid(), :wb, :ua, 'member', 'active')"
            ),
            {"wb": WORKSPACE_B, "ua": USER_A},
        )


def test_cross_workspace_update_and_delete_are_denied(rls_engines: tuple[Engine, Engine]) -> None:
    _, app = rls_engines
    with _context(app, WORKSPACE_A) as connection:
        updated = connection.execute(
            text("UPDATE memberships SET role = 'admin' WHERE id = :mb"), {"mb": MEMBERSHIP_B}
        )
        deleted = connection.execute(
            text("DELETE FROM memberships WHERE id = :mb"), {"mb": MEMBERSHIP_B}
        )
    assert updated.rowcount == 0
    assert deleted.rowcount == 0


def test_missing_workspace_context_fails_closed(rls_engines: tuple[Engine, Engine]) -> None:
    _, app = rls_engines
    with _context(app, None) as connection:
        assert connection.execute(text("SELECT id FROM memberships")).all() == []
        assert (
            connection.execute(
                text("UPDATE memberships SET role = 'admin' WHERE id = :ma"),
                {"ma": MEMBERSHIP_A},
            ).rowcount
            == 0
        )
        assert (
            connection.execute(
                text("DELETE FROM memberships WHERE id = :ma"), {"ma": MEMBERSHIP_A}
            ).rowcount
            == 0
        )
    with pytest.raises(DBAPIError, match="row-level security"), _context(app, None) as connection:
        connection.execute(
            text(
                "INSERT INTO memberships "
                "(id, workspace_id, user_id, role, status) VALUES "
                "(gen_random_uuid(), :wa, :ub, 'member', 'active')"
            ),
            {"wa": WORKSPACE_A, "ub": USER_B},
        )
