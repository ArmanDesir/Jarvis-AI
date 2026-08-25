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


def test_enabled_ai_requires_model_and_openai_key_without_exposing_secret() -> None:
    with pytest.raises(ConfigurationError, match="RIGHTJOB_AI_MODEL"):
        Settings.load({"RIGHTJOB_AI_ENABLED": "true", "RIGHTJOB_AI_ADAPTER": "openai"})
    with pytest.raises(ConfigurationError, match="RIGHTJOB_OPENAI_API_KEY"):
        Settings.load(
            {
                "RIGHTJOB_AI_ENABLED": "true",
                "RIGHTJOB_AI_ADAPTER": "openai",
                "RIGHTJOB_AI_MODEL": "configured-model",
            }
        )
    settings = Settings.load(
        {
            "RIGHTJOB_AI_ENABLED": "true",
            "RIGHTJOB_AI_ADAPTER": "openai",
            "RIGHTJOB_AI_MODEL": "configured-model",
            "RIGHTJOB_OPENAI_API_KEY": "redacted",
        }
    )
    assert settings.ai.maximum_output_tokens == 2_048
    assert "redacted" not in repr(settings)


def test_groq_requires_only_its_credential_and_exact_free_model() -> None:
    with pytest.raises(ConfigurationError, match="RIGHTJOB_GROQ_API_KEY"):
        Settings.load(
            {
                "RIGHTJOB_AI_ENABLED": "true",
                "RIGHTJOB_AI_ADAPTER": "groq",
                "RIGHTJOB_AI_MODEL": "openai/gpt-oss-20b",
                "RIGHTJOB_OPENAI_API_KEY": "must-not-be-reused",
            }
        )
    with pytest.raises(ConfigurationError, match="openai/gpt-oss-20b"):
        Settings.load(
            {
                "RIGHTJOB_AI_ENABLED": "true",
                "RIGHTJOB_AI_ADAPTER": "groq",
                "RIGHTJOB_AI_MODEL": "paid-or-unknown-model",
                "RIGHTJOB_GROQ_API_KEY": "synthetic-groq-secret",
            }
        )
    settings = Settings.load(
        {
            "RIGHTJOB_AI_ENABLED": "true",
            "RIGHTJOB_AI_ADAPTER": "groq",
            "RIGHTJOB_AI_MODEL": "openai/gpt-oss-20b",
            "RIGHTJOB_GROQ_API_KEY": "synthetic-groq-secret",
        }
    )
    assert settings.ai.api_key == "synthetic-groq-secret"
    assert "synthetic-groq-secret" not in repr(settings)


def test_unknown_ai_adapter_fails_closed() -> None:
    with pytest.raises(ConfigurationError, match="openai or groq"):
        Settings.load(
            {
                "RIGHTJOB_AI_ENABLED": "true",
                "RIGHTJOB_AI_ADAPTER": "unknown",
                "RIGHTJOB_AI_MODEL": "configured-model",
            }
        )


def test_ai_bounds_fail_closed() -> None:
    with pytest.raises(ConfigurationError, match="at most 30"):
        Settings.load({"RIGHTJOB_AI_TIMEOUT_SECONDS": "31"})
    with pytest.raises(ConfigurationError, match="at most 8192"):
        Settings.load({"RIGHTJOB_AI_MAX_OUTPUT_TOKENS": "8193"})
