from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from rightjob_api.main import app


@pytest.mark.integration
def test_health_and_readiness_without_paid_services() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        readiness = client.get("/ready")
        version = client.get("/version")

    assert health.status_code == 200
    assert health.json() == {"status": "running"}
    assert health.headers["X-Correlation-ID"]
    assert readiness.status_code == 200
    assert readiness.json()["required_dependencies_ready"] is True
    assert readiness.json()["dependencies"]["workflow"]["state"] == "disabled"
    assert version.status_code == 200
    assert version.json()["service"] == "rightjob-api"


@pytest.mark.integration
def test_required_unavailable_database_marks_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    from rightjob_api import main

    monkeypatch.setattr(
        main,
        "settings",
        replace(main.settings, api=replace(main.settings.api, database_required=True)),
    )
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
