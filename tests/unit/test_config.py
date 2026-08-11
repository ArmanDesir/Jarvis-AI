import pytest
from rightjob.shared.config import ConfigurationError, Settings


def test_defaults_disable_unproven_dependencies() -> None:
    settings = Settings.load({})

    assert settings.database.enabled is False
    assert settings.identity.enabled is False
    assert settings.ai.enabled is False
    assert settings.workflow.enabled is False


def test_enabled_database_requires_url() -> None:
    with pytest.raises(ConfigurationError, match="RIGHTJOB_DATABASE_URL"):
        Settings.load({"RIGHTJOB_DATABASE_ENABLED": "true"})


def test_invalid_boolean_fails_startup_validation() -> None:
    with pytest.raises(ConfigurationError, match="true or false"):
        Settings.load({"RIGHTJOB_AI_ENABLED": "sometimes"})


def test_enabled_proof_gate_requires_adapter() -> None:
    with pytest.raises(ConfigurationError, match="RIGHTJOB_WORKFLOW_ADAPTER"):
        Settings.load({"RIGHTJOB_WORKFLOW_ENABLED": "true"})
