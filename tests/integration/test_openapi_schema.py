import json

import pytest
from rightjob_api.main import app

APPROVED_PATHS = {
    "/health",
    "/ready",
    "/version",
    "/identity/context",
    "/api/v1/me",
    "/api/v1/workspace",
    "/api/v1/membership",
}


@pytest.mark.integration
def test_internal_openapi_is_deterministic_and_exactly_scoped() -> None:
    app.openapi_schema = None
    first = json.dumps(app.openapi(), sort_keys=True, separators=(",", ":"))
    app.openapi_schema = None
    second = json.dumps(app.openapi(), sort_keys=True, separators=(",", ":"))
    schema = json.loads(first)

    assert first == second
    assert set(schema["paths"]) == APPROVED_PATHS
    assert app.openapi_url is None
    assert app.docs_url is None
    assert app.redoc_url is None


@pytest.mark.integration
def test_application_openapi_has_stable_operations_contracts_and_security() -> None:
    schema = app.openapi()
    assert schema["paths"]["/api/v1/me"]["get"]["operationId"] == "getCurrentPrincipalContext"
    assert schema["paths"]["/api/v1/workspace"]["get"]["operationId"] == "getCurrentWorkspace"
    assert schema["paths"]["/api/v1/workspace"]["patch"]["operationId"] == "updateCurrentWorkspace"
    assert schema["paths"]["/api/v1/membership"]["get"]["operationId"] == "getCurrentMembership"
    patch = schema["paths"]["/api/v1/workspace"]["patch"]
    assert patch["requestBody"]["content"]["application/json"]["schema"]
    assert patch["responses"]["200"]["content"]["application/json"]["schema"]
    assert set(patch["responses"]) >= {"200", "401", "403", "404", "409", "422", "500"}
    assert patch["security"] == [{"BearerAuth": []}]
    assert schema["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"
