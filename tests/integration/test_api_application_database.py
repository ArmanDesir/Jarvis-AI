from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient
from rightjob.identity.application.authentication import JwtAuthenticationProvider
from rightjob.identity.application.operations import IdentityApplicationService
from rightjob.identity.application.service import IdentityService
from rightjob.identity.infrastructure.jwt import PyJwtVerifier
from rightjob.identity.infrastructure.repositories import (
    SqlAlchemyMembershipRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
)
from rightjob.identity.infrastructure.unit_of_work import SqlAlchemyIdentityUnitOfWork
from rightjob_api.main import app
from rightjob_api.routes import identity_application_service
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

OWNER_URL = os.environ.get("RIGHTJOB_DATABASE_URL")
APP_URL = os.environ.get("RIGHTJOB_RLS_TEST_DATABASE_URL")
APP_ROLE = "rightjob_phase21_rls_verifier"
KEY = "phase24-database-signing-key-at-least-32-bytes"

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


def _drop_role(connection: Connection) -> None:
    connection.execute(text(f"REVOKE ALL ON memberships FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE ALL ON users FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE ALL ON workspaces FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE ALL ON SCHEMA public FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE CONNECT ON DATABASE rightjob_phase16 FROM {APP_ROLE}"))
    connection.execute(text(f"DROP ROLE IF EXISTS {APP_ROLE}"))


@pytest.fixture(scope="module")
def database_api() -> Iterator[tuple[TestClient, Engine]]:
    assert OWNER_URL and APP_URL
    owner = create_engine(OWNER_URL)
    application = create_engine(APP_URL)
    with owner.begin() as connection:
        if connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :role)"),
            {"role": APP_ROLE},
        ):
            _drop_role(connection)
        _delete_fixture_records(connection)
        connection.execute(
            text(
                f"CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOINHERIT NOBYPASSRLS"
            )
        )
        connection.execute(text(f"GRANT CONNECT ON DATABASE rightjob_phase16 TO {APP_ROLE}"))
        connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
        connection.execute(text(f"GRANT SELECT ON memberships, users TO {APP_ROLE}"))
        connection.execute(text(f"GRANT SELECT, UPDATE ON workspaces TO {APP_ROLE}"))
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
                "(:ma, :wa, :ua, 'owner', 'active'), (:mb, :wb, :ub, 'member', 'active')"
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

    identity_session = Session(application)
    app.state.authentication_provider = JwtAuthenticationProvider(
        "test", PyJwtVerifier(KEY, ("HS256",))
    )
    app.state.identity_service = IdentityService(
        SqlAlchemyUserRepository(identity_session),
        SqlAlchemyMembershipRepository(identity_session),
        SqlAlchemyWorkspaceRepository(identity_session),
    )
    factory = sessionmaker(bind=application, expire_on_commit=False)
    app.state.identity_uow_factory = lambda: SqlAlchemyIdentityUnitOfWork(factory)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, owner
    finally:
        app.dependency_overrides.clear()
        app.state.authentication_provider = None
        app.state.identity_service = None
        app.state.identity_uow_factory = None
        identity_session.close()
        application.dispose()
        with owner.begin() as connection:
            _delete_fixture_records(connection)
            _drop_role(connection)
        owner.dispose()


def _token(subject: str) -> str:
    return jwt.encode(
        {"sub": subject, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        KEY,
        algorithm="HS256",
    )


def _headers(subject: str = "a") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token(subject)}",
        "X-Workspace-ID": str(WORKSPACE_A),
        "X-Correlation-ID": "0198ff00-0000-7000-8000-000000000401",
    }


def test_database_api_reads_and_updates_exact_workspace(
    database_api: tuple[TestClient, Engine],
) -> None:
    client, owner = database_api
    assert client.get("/api/v1/me", headers=_headers()).status_code == 200
    assert client.get("/api/v1/workspace", headers=_headers()).status_code == 200
    assert client.get("/api/v1/membership", headers=_headers()).status_code == 200

    updated = client.patch(
        "/api/v1/workspace",
        headers=_headers(),
        json={
            "expected_version": 1,
            "name": "Workspace A Updated",
            "timezone": "Asia/Manila",
            "locale": "en-PH",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    with owner.connect() as connection:
        stored = connection.execute(
            text("SELECT name, timezone, locale, version FROM workspaces WHERE id = :id"),
            {"id": WORKSPACE_A},
        ).one()
        other = connection.execute(
            text("SELECT name, timezone, locale, version FROM workspaces WHERE id = :id"),
            {"id": WORKSPACE_B},
        ).one()
    assert stored == ("Workspace A Updated", "Asia/Manila", "en-PH", 2)
    assert other == ("Workspace B", "UTC", "en", 1)


def test_failed_database_requests_persist_nothing(database_api: tuple[TestClient, Engine]) -> None:
    client, owner = database_api
    stale = client.patch(
        "/api/v1/workspace",
        headers=_headers(),
        json={"expected_version": 1, "name": "Stale"},
    )
    forbidden = client.patch(
        "/api/v1/workspace",
        headers=_headers("b"),
        json={"expected_version": 2, "name": "Forbidden"},
    )
    invalid = client.patch(
        "/api/v1/workspace",
        headers=_headers(),
        json={"expected_version": 2, "slug": "invalid"},
    )
    assert (stale.status_code, forbidden.status_code, invalid.status_code) == (409, 403, 422)
    with owner.connect() as connection:
        stored = connection.execute(
            text("SELECT name, timezone, locale, version FROM workspaces WHERE id = :id"),
            {"id": WORKSPACE_A},
        ).one()
    assert stored == ("Workspace A Updated", "Asia/Manila", "en-PH", 2)


def test_application_failure_rolls_back_database_update(
    database_api: tuple[TestClient, Engine],
) -> None:
    client, owner = database_api

    class FailingApplication(IdentityApplicationService):
        def update_current_workspace(self, context, update, metadata, unit_of_work):  # type: ignore[no-untyped-def]
            workspace = unit_of_work.workspaces.get(context.workspace.id)
            assert workspace is not None
            unit_of_work.workspaces.save(
                workspace.__class__(
                    **(
                        workspace.__dict__
                        | {"name": "Rolled Back", "version": update.expected_version}
                    )
                )
            )
            raise RuntimeError("forced failure")

    app.dependency_overrides[identity_application_service] = FailingApplication
    try:
        response = client.patch(
            "/api/v1/workspace",
            headers=_headers(),
            json={"expected_version": 2, "name": "Rolled Back"},
        )
    finally:
        app.dependency_overrides.pop(identity_application_service, None)

    assert response.status_code == 500
    with owner.connect() as connection:
        stored = connection.execute(
            text("SELECT name, timezone, locale, version FROM workspaces WHERE id = :id"),
            {"id": WORKSPACE_A},
        ).one()
    assert stored == ("Workspace A Updated", "Asia/Manila", "en-PH", 2)
