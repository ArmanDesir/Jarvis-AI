"""Environment configuration with explicit namespaces and startup validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from os import environ
from typing import Mapping


class ConfigurationError(ValueError):
    pass


def _bool(values: Mapping[str, str], key: str, default: bool = False) -> bool:
    raw = values.get(key, str(default)).lower()
    if raw not in {"true", "false"}:
        raise ConfigurationError(f"{key} must be true or false")
    return raw == "true"


def _int(values: Mapping[str, str], key: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(values.get(key, str(default)))
    except ValueError as error:
        raise ConfigurationError(f"{key} must be an integer") from error
    if value < minimum:
        raise ConfigurationError(f"{key} must be at least {minimum}")
    return value


@dataclass(frozen=True)
class ApiSettings:
    host: str
    port: int
    database_required: bool


@dataclass(frozen=True)
class WorkerSettings:
    worker_id: str
    poll_seconds: int


@dataclass(frozen=True)
class DatabaseSettings:
    enabled: bool
    url: str | None


@dataclass(frozen=True)
class OptionalAdapterSettings:
    enabled: bool
    adapter: str


@dataclass(frozen=True)
class AISettings:
    enabled: bool
    adapter: str
    model: str | None
    timeout_seconds: int
    maximum_output_tokens: int
    api_key: str | None = field(repr=False)


@dataclass(frozen=True)
class StorageSettings:
    enabled: bool
    endpoint: str | None
    region: str | None


@dataclass(frozen=True)
class Settings:
    environment: str
    log_level: str
    build_version: str
    api: ApiSettings
    worker: WorkerSettings
    database: DatabaseSettings
    storage: StorageSettings
    identity: OptionalAdapterSettings
    ai: AISettings
    workflow: OptionalAdapterSettings

    @classmethod
    def load(cls, values: Mapping[str, str] | None = None) -> "Settings":
        source = environ if values is None else values
        database_enabled = _bool(source, "RIGHTJOB_DATABASE_ENABLED")
        database_url = source.get("RIGHTJOB_DATABASE_URL") or None
        if database_enabled and not database_url:
            raise ConfigurationError(
                "RIGHTJOB_DATABASE_URL is required when RIGHTJOB_DATABASE_ENABLED=true"
            )

        def adapter(namespace: str) -> OptionalAdapterSettings:
            enabled = _bool(source, f"RIGHTJOB_{namespace}_ENABLED")
            name = source.get(f"RIGHTJOB_{namespace}_ADAPTER", "disabled")
            if enabled and name == "disabled":
                raise ConfigurationError(
                    f"RIGHTJOB_{namespace}_ADAPTER must be configured when enabled"
                )
            return OptionalAdapterSettings(enabled, name)

        workflow = adapter("WORKFLOW")
        ai_enabled = _bool(source, "RIGHTJOB_AI_ENABLED")
        ai_adapter = source.get("RIGHTJOB_AI_ADAPTER", "disabled")
        ai_model = source.get("RIGHTJOB_AI_MODEL") or None
        selected_credential = None
        if ai_enabled and ai_adapter == "disabled":
            raise ConfigurationError("RIGHTJOB_AI_ADAPTER must be configured when enabled")
        if ai_enabled and not ai_model:
            raise ConfigurationError("RIGHTJOB_AI_MODEL is required when AI is enabled")
        if ai_enabled and ai_adapter not in {"openai", "groq"}:
            raise ConfigurationError("RIGHTJOB_AI_ADAPTER must be openai or groq when enabled")
        if ai_enabled and ai_adapter == "groq" and ai_model != "openai/gpt-oss-20b":
            raise ConfigurationError("the Groq adapter requires openai/gpt-oss-20b")
        if ai_enabled:
            credential = {
                "openai": "RIGHTJOB_OPENAI_API_KEY",
                "groq": "RIGHTJOB_GROQ_API_KEY",
            }[ai_adapter]
            selected_credential = source.get(credential) or None
            if not selected_credential:
                raise ConfigurationError(
                    f"{credential} is required when the {ai_adapter} adapter is enabled"
                )
        if len(ai_adapter) > 100 or (ai_model is not None and len(ai_model) > 200):
            raise ConfigurationError("AI adapter and model identifiers must be bounded")
        ai_timeout = _int(source, "RIGHTJOB_AI_TIMEOUT_SECONDS", 30)
        if ai_timeout > 30:
            raise ConfigurationError("RIGHTJOB_AI_TIMEOUT_SECONDS must be at most 30")
        ai_output_tokens = _int(source, "RIGHTJOB_AI_MAX_OUTPUT_TOKENS", 2_048)
        if ai_output_tokens > 8_192:
            raise ConfigurationError("RIGHTJOB_AI_MAX_OUTPUT_TOKENS must be at most 8192")
        return cls(
            environment=source.get("RIGHTJOB_ENVIRONMENT", "local"),
            log_level=source.get("RIGHTJOB_LOG_LEVEL", "INFO").upper(),
            build_version=source.get("RIGHTJOB_BUILD_VERSION", "dev"),
            api=ApiSettings(
                host=source.get("RIGHTJOB_API_HOST", "127.0.0.1"),
                port=_int(source, "RIGHTJOB_API_PORT", 8000),
                database_required=_bool(source, "RIGHTJOB_API_DATABASE_REQUIRED"),
            ),
            worker=WorkerSettings(
                worker_id=source.get("RIGHTJOB_WORKER_ID", "worker-local"),
                poll_seconds=_int(source, "RIGHTJOB_WORKER_POLL_SECONDS", 30),
            ),
            database=DatabaseSettings(database_enabled, database_url),
            storage=StorageSettings(
                enabled=_bool(source, "RIGHTJOB_STORAGE_ENABLED"),
                endpoint=source.get("RIGHTJOB_STORAGE_ENDPOINT") or None,
                region=source.get("RIGHTJOB_STORAGE_REGION") or None,
            ),
            identity=adapter("IDENTITY"),
            ai=AISettings(
                ai_enabled,
                ai_adapter,
                ai_model,
                ai_timeout,
                ai_output_tokens,
                selected_credential,
            ),
            workflow=workflow,
        )
