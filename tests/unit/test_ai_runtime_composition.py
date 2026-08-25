import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from rightjob.ai_runtime import build_ai_planning_stack
from rightjob.contracts.ai import (
    AIFinishStatus,
    AIProvider,
    AIRequest,
    AIResponse,
    AIUsage,
)
from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.executive_intake import ExecutiveIntakeOutcome, ExecutiveIntakeRequest
from rightjob.registry import BuiltInCapabilityRegistry, BuiltInDepartmentRegistry
from rightjob.shared.config import ConfigurationError, Settings

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]


class Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> UUID:
        self.value += 1
        return UUID(f"21600000-0000-4000-8000-{self.value:012d}")


class SequenceProvider:
    def __init__(self, responses: tuple[str, ...]) -> None:
        self.responses = responses
        self.requests: list[AIRequest] = []

    def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        content = self.responses[len(self.requests) - 1]
        return AIResponse(
            request.invocation_id,
            request.correlation_id,
            request.model,
            AIFinishStatus.COMPLETED,
            content,
            AIUsage(10, 10, 20),
        )


def settings(**overrides: str) -> Settings:
    values = {
        "RIGHTJOB_AI_ENABLED": "true",
        "RIGHTJOB_AI_ADAPTER": "openai",
        "RIGHTJOB_AI_MODEL": "synthetic-model",
        "RIGHTJOB_OPENAI_API_KEY": "synthetic-test-secret",
    }
    values.update(overrides)
    return Settings.load(values)


def groq_settings(**overrides: str) -> Settings:
    values = {
        "RIGHTJOB_AI_ENABLED": "true",
        "RIGHTJOB_AI_ADAPTER": "groq",
        "RIGHTJOB_AI_MODEL": "openai/gpt-oss-20b",
        "RIGHTJOB_GROQ_API_KEY": "synthetic-groq-secret",
    }
    values.update(overrides)
    return Settings.load(values)


def intent(outcome: str = "planning_ready") -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "outcome": outcome,
            "reason": "ready" if outcome == "planning_ready" else "unsupported_request",
            "goal": "prepare_transform_verify" if outcome == "planning_ready" else None,
            "planning_input": (
                [{"key": "topic", "value": "synthetic content"}]
                if outcome == "planning_ready"
                else None
            ),
            "clarification_question": None,
            "missing_fields": [],
        }
    )


def proposal() -> str:
    values: tuple[tuple[str, str, str, str, list[int]], ...] = (
        ("prepare", "prepare", "foundation.operations", "fake.prepare", []),
        ("transform", "transform", "foundation.content", "fake.transform", [0]),
        ("verify", "verify", "foundation.operations", "fake.verify", [1]),
    )
    return json.dumps(
        {
            "schema_version": 1,
            "steps": [
                {
                    "sequence": sequence,
                    "objective": objective,
                    "work_category": category,
                    "department_key": department,
                    "department_semantic_version": "1.0.0",
                    "capability_key": capability,
                    "capability_semantic_version": "1.0.0",
                    "structured_input": [{"key": "topic", "value": "synthetic content"}],
                    "dependency_sequences": dependencies,
                }
                for sequence, (
                    objective,
                    category,
                    department,
                    capability,
                    dependencies,
                ) in enumerate(values)
            ],
        }
    )


def catalogs() -> tuple[BuiltInCapabilityRegistry, BuiltInDepartmentRegistry]:
    capabilities = BuiltInCapabilityRegistry()
    return capabilities, BuiltInDepartmentRegistry(capabilities)


def request() -> ExecutiveIntakeRequest:
    return ExecutiveIntakeRequest(
        UUID("21610000-0000-4000-8000-000000000001"),
        Actor(ActorType.USER, "trusted-smoke-user"),
        UUID("21610000-0000-4000-8000-000000000002"),
        UUID("21610000-0000-4000-8000-000000000003"),
        "Prepare, transform, and verify this synthetic content.",
    )


def test_fake_provider_composes_full_runtime_path_with_exactly_two_calls() -> None:
    provider = SequenceProvider((intent(), proposal()))
    capabilities, departments = catalogs()
    stack = build_ai_planning_stack(
        settings(),
        capabilities,
        departments,
        Ids(),
        lambda: NOW,
        provider_factory=lambda _: provider,
    )

    result = stack.interpret(request())

    assert result.outcome is ExecutiveIntakeOutcome.PLANNED
    assert result.plan is not None
    assert result.plan.workspace_id == request().workspace_id
    assert result.plan.actor == request().actor
    assert result.plan.correlation_id == request().correlation_id
    assert len(provider.requests) == 2
    assert all(item.model.provider_key == "openai" for item in provider.requests)
    assert all(not hasattr(item, "tools") for item in provider.requests)


def test_groq_composes_same_provider_neutral_runtime_path() -> None:
    provider = SequenceProvider((intent(), proposal()))
    capabilities, departments = catalogs()
    stack = build_ai_planning_stack(
        groq_settings(),
        capabilities,
        departments,
        Ids(),
        lambda: NOW,
        provider_factory=lambda key: provider,
    )

    result = stack.interpret(request())

    assert result.outcome is ExecutiveIntakeOutcome.PLANNED
    assert len(provider.requests) == 2
    assert all(item.model.provider_key == "groq" for item in provider.requests)
    assert all(item.model.model_key == "openai/gpt-oss-20b" for item in provider.requests)


def test_non_planning_intent_prevents_second_provider_call() -> None:
    provider = SequenceProvider((intent("unsupported"),))
    capabilities, departments = catalogs()
    stack = build_ai_planning_stack(
        settings(),
        capabilities,
        departments,
        Ids(),
        lambda: NOW,
        provider_factory=lambda _: provider,
    )
    assert stack.interpret(request()).outcome is ExecutiveIntakeOutcome.UNSUPPORTED
    assert len(provider.requests) == 1


def test_disabled_and_unsupported_runtime_configuration_fail_closed() -> None:
    capabilities, departments = catalogs()
    with pytest.raises(ConfigurationError, match="ENABLED"):
        build_ai_planning_stack(Settings.load({}), capabilities, departments, Ids(), lambda: NOW)
    with pytest.raises(ConfigurationError, match="openai or groq"):
        build_ai_planning_stack(
            settings(RIGHTJOB_AI_ADAPTER="unsupported"),
            capabilities,
            departments,
            Ids(),
            lambda: NOW,
        )


def test_missing_model_key_and_invalid_bounds_fail_before_provider_construction() -> None:
    with pytest.raises(ConfigurationError, match="RIGHTJOB_AI_MODEL"):
        Settings.load(
            {
                "RIGHTJOB_AI_ENABLED": "true",
                "RIGHTJOB_AI_ADAPTER": "openai",
                "RIGHTJOB_OPENAI_API_KEY": "synthetic-test-secret",
            }
        )
    with pytest.raises(ConfigurationError, match="RIGHTJOB_OPENAI_API_KEY"):
        Settings.load(
            {
                "RIGHTJOB_AI_ENABLED": "true",
                "RIGHTJOB_AI_ADAPTER": "openai",
                "RIGHTJOB_AI_MODEL": "synthetic-model",
            }
        )
    with pytest.raises(ConfigurationError, match="at most 30"):
        settings(RIGHTJOB_AI_TIMEOUT_SECONDS="31")
    with pytest.raises(ConfigurationError, match="at most 8192"):
        settings(RIGHTJOB_AI_MAX_OUTPUT_TOKENS="8193")


def test_synthetic_secret_is_not_exposed_and_construction_performs_no_call() -> None:
    value = settings()
    assert "synthetic-test-secret" not in repr(value)
    provider = SequenceProvider((intent(), proposal()))
    capabilities, departments = catalogs()
    build_ai_planning_stack(
        value,
        capabilities,
        departments,
        Ids(),
        lambda: NOW,
        provider_factory=lambda _: cast(AIProvider, provider),
    )
    assert provider.requests == []


def test_default_openai_stack_construction_with_synthetic_secret_does_not_generate() -> None:
    capabilities, departments = catalogs()
    stack = build_ai_planning_stack(settings(), capabilities, departments, Ids(), lambda: NOW)
    assert stack.__class__.__name__ == "ExecutiveIntakeService"


def test_default_groq_stack_construction_with_synthetic_secret_does_not_generate() -> None:
    capabilities, departments = catalogs()
    stack = build_ai_planning_stack(groq_settings(), capabilities, departments, Ids(), lambda: NOW)
    assert stack.__class__.__name__ == "ExecutiveIntakeService"


@pytest.mark.parametrize(
    "provided",
    [
        {"RIGHTJOB_OPENAI_API_KEY": "synthetic-test-secret"},
        {"RIGHTJOB_LIVE_AI_TESTS": "true"},
    ],
)
def test_live_harness_requires_both_explicit_opt_in_and_key(provided: dict[str, str]) -> None:
    environment = os.environ.copy()
    environment.pop("RIGHTJOB_LIVE_AI_TESTS", None)
    environment.pop("RIGHTJOB_OPENAI_API_KEY", None)
    environment.update(provided)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/live/test_openai_planning_smoke.py",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "1 skipped" in result.stdout


@pytest.mark.parametrize(
    "omitted",
    [
        "RIGHTJOB_LIVE_AI_TESTS",
        "RIGHTJOB_AI_ENABLED",
        "RIGHTJOB_AI_ADAPTER",
        "RIGHTJOB_AI_MODEL",
        "RIGHTJOB_GROQ_API_KEY",
    ],
)
def test_groq_live_harness_requires_every_gate(omitted: str) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "RIGHTJOB_LIVE_AI_TESTS": "true",
            "RIGHTJOB_AI_ENABLED": "true",
            "RIGHTJOB_AI_ADAPTER": "groq",
            "RIGHTJOB_AI_MODEL": "openai/gpt-oss-20b",
            "RIGHTJOB_GROQ_API_KEY": "synthetic-test-secret",
        }
    )
    environment.pop(omitted, None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/live/test_groq_planning_smoke.py",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "1 skipped" in result.stdout
