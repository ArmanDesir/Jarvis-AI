from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from rightjob.identity.application.authentication import JwtAuthenticationProvider
from rightjob.identity.infrastructure.jwt import PyJwtVerifier
from rightjob_api.main import app

from tests.unit.test_identity_service import WORKSPACE_A, _service

KEY = "phase22-http-test-signing-key-at-least-32-bytes"


def _token(expires_in: int = 60, key: str = KEY) -> str:
    return jwt.encode(
        {"sub": "subject-1", "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in)},
        key,
        algorithm="HS256",
    )


@pytest.fixture
def client() -> TestClient:
    app.state.authentication_provider = JwtAuthenticationProvider(
        "test-oidc", PyJwtVerifier(KEY, ("HS256",))
    )
    app.state.identity_service = _service()
    with TestClient(app) as test_client:
        yield test_client
    app.state.authentication_provider = None
    app.state.identity_service = None


@pytest.mark.integration
def test_authorized_request_injects_principal_workspace_and_membership(
    client: TestClient,
) -> None:
    response = client.get(
        "/identity/context",
        headers={"Authorization": f"Bearer {_token()}", "X-Workspace-ID": str(WORKSPACE_A.id)},
    )
    assert response.status_code == 200
    assert response.json() == {
        "user_id": "0198ff00-0000-7000-8000-000000000111",
        "external_subject": "subject-1",
        "workspace_id": str(WORKSPACE_A.id),
        "membership_id": "0198ff00-0000-7000-8000-000000000121",
        "roles": ["owner"],
        "permissions": [],
        "authentication_provider": "test-oidc",
    }


@pytest.mark.integration
@pytest.mark.parametrize(
    ("headers", "code"),
    [
        ({"X-Workspace-ID": str(WORKSPACE_A.id)}, "missing_token"),
        (
            {"Authorization": "Bearer not-a-jwt", "X-Workspace-ID": str(WORKSPACE_A.id)},
            "malformed_token",
        ),
        (
            {
                "Authorization": f"Bearer {_token(expires_in=-1)}",
                "X-Workspace-ID": str(WORKSPACE_A.id),
            },
            "expired_token",
        ),
        (
            {
                "Authorization": f"Bearer {_token(key='wrong-key-at-least-32-bytes-long')}",
                "X-Workspace-ID": str(WORKSPACE_A.id),
            },
            "invalid_token",
        ),
    ],
)
def test_unauthorized_requests_fail_closed(
    client: TestClient, headers: dict[str, str], code: str
) -> None:
    response = client.get("/identity/context", headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == code


@pytest.mark.integration
def test_authenticated_request_requires_workspace_context(client: TestClient) -> None:
    response = client.get("/identity/context", headers={"Authorization": f"Bearer {_token()}"})
    assert response.status_code == 400
    assert response.json()["code"] == "workspace_required"


@pytest.mark.integration
def test_authenticated_public_request_cannot_bypass_workspace_resolution(
    client: TestClient,
) -> None:
    response = client.get(
        "/health",
        headers={
            "Authorization": f"Bearer {_token()}",
            "X-Workspace-ID": "0198ff00-0000-7000-8000-000000000199",
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "workspace_access_denied"
