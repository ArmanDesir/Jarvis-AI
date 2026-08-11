from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import TracebackType
from typing import Iterator

import jwt
import pytest
from fastapi.testclient import TestClient
from rightjob.identity.application.authentication import JwtAuthenticationProvider
from rightjob.identity.application.repositories import ConcurrentUpdateError, IdentityUnitOfWork
from rightjob.identity.domain.entities import Membership, Workspace
from rightjob.identity.domain.values import MembershipRole
from rightjob.identity.infrastructure.jwt import PyJwtVerifier
from rightjob_api.main import app
from rightjob_api.routes import identity_application_service
from sqlalchemy.exc import SQLAlchemyError

from tests.unit.test_identity_service import MEMBERSHIP_A, USER, WORKSPACE_A, _service

KEY = "phase24-http-test-signing-key-at-least-32-bytes"


def _token() -> str:
    return jwt.encode(
        {"sub": "subject-1", "exp": datetime.now(timezone.utc) + timedelta(seconds=60)},
        KEY,
        algorithm="HS256",
    )


class Workspaces:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def get(self, workspace_id: object) -> Workspace | None:
        return self.workspace if workspace_id == self.workspace.id else None

    def save(self, workspace: Workspace) -> Workspace:
        if workspace.version != self.workspace.version:
            raise ConcurrentUpdateError("stale")
        self.workspace = replace(workspace, version=workspace.version + 1)
        return self.workspace


class Memberships:
    def __init__(self, membership: Membership) -> None:
        self.membership = membership

    def get_for_user(self, workspace_id: object, user_id: object) -> Membership | None:
        if (workspace_id, user_id) == (self.membership.workspace_id, self.membership.user_id):
            return self.membership
        return None


class FakeUnitOfWork:
    def __init__(self, workspace: Workspace, membership: Membership) -> None:
        self.workspaces = Workspaces(workspace)
        self.memberships = Memberships(membership)
        self.users = object()
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exception_type is not None:
            self.rollback()
        self.close()

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def api_client() -> Iterator[tuple[TestClient, list[FakeUnitOfWork]]]:
    created: list[FakeUnitOfWork] = []

    def factory() -> IdentityUnitOfWork:
        unit_of_work = FakeUnitOfWork(WORKSPACE_A, MEMBERSHIP_A)
        created.append(unit_of_work)
        return unit_of_work  # type: ignore[return-value]

    app.state.authentication_provider = JwtAuthenticationProvider(
        "test-oidc", PyJwtVerifier(KEY, ("HS256",))
    )
    app.state.identity_service = _service()
    app.state.identity_uow_factory = factory
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, created
    app.state.authentication_provider = None
    app.state.identity_service = None
    app.state.identity_uow_factory = None


def _headers(correlation_id: str = "0198ff00-0000-7000-8000-000000000299") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "X-Workspace-ID": str(WORKSPACE_A.id),
        "X-Correlation-ID": correlation_id,
    }


@pytest.mark.integration
def test_current_context_routes_are_typed_and_workspace_scoped(
    api_client: tuple[TestClient, list[FakeUnitOfWork]],
) -> None:
    client, created = api_client

    me = client.get("/api/v1/me", headers=_headers())
    workspace = client.get("/api/v1/workspace", headers=_headers())
    membership = client.get("/api/v1/membership", headers=_headers())

    assert me.status_code == workspace.status_code == membership.status_code == 200
    assert me.json() == {
        "user_id": str(USER.id),
        "workspace_id": str(WORKSPACE_A.id),
        "membership_id": str(MEMBERSHIP_A.id),
        "role": "owner",
        "authentication_provider": "test-oidc",
        "permissions": [],
    }
    assert workspace.json()["slug"] == WORKSPACE_A.slug
    assert "settings" not in workspace.json()
    assert membership.json()["user_id"] == str(USER.id)
    assert len(created) == 2
    assert all(unit_of_work.closed for unit_of_work in created)
    assert all(unit_of_work.commits == 0 for unit_of_work in created)


@pytest.mark.integration
def test_owner_workspace_update_commits_once(
    api_client: tuple[TestClient, list[FakeUnitOfWork]],
) -> None:
    client, created = api_client
    response = client.patch(
        "/api/v1/workspace",
        headers=_headers(),
        json={"expected_version": 1, "name": "Updated", "timezone": "Asia/Manila"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated"
    assert response.json()["version"] == 2
    assert len(created) == 1
    assert created[0].commits == 1
    assert created[0].rollbacks == 0
    assert created[0].closed is True


@pytest.mark.integration
def test_admin_workspace_update_is_authorized(
    api_client: tuple[TestClient, list[FakeUnitOfWork]],
) -> None:
    client, created = api_client
    app.state.identity_service = _service(
        memberships=(replace(MEMBERSHIP_A, role=MembershipRole.ADMIN),)
    )
    response = client.patch(
        "/api/v1/workspace",
        headers=_headers(),
        json={"expected_version": 1, "locale": "en-PH"},
    )

    assert response.status_code == 200
    assert response.json()["locale"] == "en-PH"
    assert created[0].commits == 1
    assert created[0].closed is True


@pytest.mark.integration
def test_member_update_is_forbidden_and_closed(
    api_client: tuple[TestClient, list[FakeUnitOfWork]],
) -> None:
    client, created = api_client
    app.state.identity_service = _service(
        memberships=(replace(MEMBERSHIP_A, role=MembershipRole.MEMBER),)
    )
    response = client.patch(
        "/api/v1/workspace",
        headers=_headers(),
        json={"expected_version": 1, "name": "Denied"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert response.json()["correlation_id"] == _headers()["X-Correlation-ID"]
    assert created[0].commits == 0
    assert created[0].rollbacks == 1
    assert created[0].closed is True


@pytest.mark.integration
def test_stale_and_invalid_updates_do_not_commit(
    api_client: tuple[TestClient, list[FakeUnitOfWork]],
) -> None:
    client, created = api_client
    stale = client.patch(
        "/api/v1/workspace",
        headers=_headers(),
        json={"expected_version": 2, "name": "Stale"},
    )
    invalid = client.patch(
        "/api/v1/workspace", headers=_headers(), json={"expected_version": 1, "slug": "no"}
    )

    assert stale.status_code == 409
    assert stale.json()["code"] == "VERSION_CONFLICT"
    assert created[0].commits == 0
    assert created[0].rollbacks == 1
    assert created[0].closed is True
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "VALIDATION_ERROR"
    assert invalid.json()["correlation_id"] == _headers()["X-Correlation-ID"]
    assert created[1].commits == 0
    assert created[1].closed is True


@pytest.mark.integration
def test_unauthenticated_error_is_stable_and_correlated(
    api_client: tuple[TestClient, list[FakeUnitOfWork]],
) -> None:
    client, _ = api_client
    response = client.get(
        "/api/v1/me",
        headers={
            "X-Workspace-ID": str(WORKSPACE_A.id),
            "X-Correlation-ID": "0198ff00-0000-7000-8000-000000000298",
        },
    )

    assert response.status_code == 401
    assert response.json()["code"] == "missing_token"
    assert response.json()["correlation_id"] == "0198ff00-0000-7000-8000-000000000298"
    assert "traceback" not in response.text.lower()


@pytest.mark.integration
def test_unknown_route_is_sanitized_and_correlated(
    api_client: tuple[TestClient, list[FakeUnitOfWork]],
) -> None:
    client, _ = api_client
    response = client.get("/not-a-route", headers=_headers())
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    assert response.json()["correlation_id"] == _headers()["X-Correlation-ID"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "failure",
    [SQLAlchemyError("database-url-secret"), RuntimeError("jwt-secret")],
)
def test_internal_failures_are_sanitized_and_uow_is_closed(
    api_client: tuple[TestClient, list[FakeUnitOfWork]], failure: Exception
) -> None:
    client, created = api_client

    class ExplodingService:
        def update_current_workspace(self, *args: object) -> None:
            raise failure

    app.dependency_overrides[identity_application_service] = lambda: ExplodingService()
    try:
        response = client.patch(
            "/api/v1/workspace",
            headers=_headers(),
            json={"expected_version": 1, "name": "Failure"},
        )
    finally:
        app.dependency_overrides.pop(identity_application_service, None)

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"
    assert response.json()["correlation_id"] == _headers()["X-Correlation-ID"]
    assert "secret" not in response.text.lower()
    assert "sql" not in response.text.lower()
    assert "traceback" not in response.text.lower()
    assert created[0].commits == 0
    assert created[0].rollbacks == 1
    assert created[0].closed is True
