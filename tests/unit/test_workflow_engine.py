from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from rightjob.orchestration import DurableWorkflowEngine, WorkflowContext, WorkflowRef
from rightjob_worker.proof_activities import FakeExternalEffects
from rightjob_worker.proof_workflows import PROOF_WORKFLOWS
from rightjob_worker.temporal_adapter import (
    TemporalWorkflowEngine,
    WorkflowScopeError,
    canonical_workflow_id,
)
from rightjob_worker.temporal_runtime import TemporalSettings
from temporalio.client import Client, WorkflowExecutionStatus


def context(workspace_id: str = "workspace-a") -> WorkflowContext:
    return WorkflowContext(
        workspace_id=workspace_id,
        correlation_id="correlation-1",
        causation_id=None,
        logical_operation_id="operation-1",
        workflow_type="proof.durable-counter",
        workflow_version="1.0.0",
    )


def test_canonical_identifier_is_deterministic_and_workspace_derived() -> None:
    first = canonical_workflow_id(context())
    assert first == canonical_workflow_id(context())
    assert first != canonical_workflow_id(context("workspace-b"))
    assert first.startswith("rj-proof.durable-counter-")


@pytest.mark.asyncio
async def test_temporal_adapter_maps_provider_neutral_contract() -> None:
    handle = SimpleNamespace(
        describe=AsyncMock(return_value=SimpleNamespace(status=WorkflowExecutionStatus.RUNNING)),
        signal=AsyncMock(),
        cancel=AsyncMock(),
        result=AsyncMock(return_value={"state": "completed"}),
    )
    client = SimpleNamespace(
        start_workflow=AsyncMock(),
        get_workflow_handle=lambda _workflow_id: handle,
    )
    engine: DurableWorkflowEngine = TemporalWorkflowEngine(cast(Client, client), "proof-queue")
    ref = await engine.start(context(), {"value": 1})

    assert ref.workspace_id == "workspace-a"
    assert (await engine.status("workspace-a", ref)).value == "running"
    await engine.signal("workspace-a", ref, "resume", {})
    assert (await engine.result("workspace-a", ref)).value == {"state": "completed"}
    await engine.cancel("workspace-a", ref)
    client.start_workflow.assert_awaited_once()
    handle.signal.assert_awaited_once_with("resume", {})
    handle.cancel.assert_awaited_once_with(reason="rightjob-requested")


@pytest.mark.asyncio
async def test_cross_workspace_operations_fail_before_temporal_call() -> None:
    client = SimpleNamespace(get_workflow_handle=lambda _workflow_id: pytest.fail("called"))
    engine = TemporalWorkflowEngine(cast(Client, client), "proof-queue")
    ref = WorkflowRef("workflow-1", "workspace-a")

    with pytest.raises(WorkflowScopeError):
        await engine.status("workspace-b", ref)
    with pytest.raises(WorkflowScopeError):
        await engine.signal("workspace-b", ref, "approve", {})
    with pytest.raises(WorkflowScopeError):
        await engine.cancel("workspace-b", ref)
    with pytest.raises(WorkflowScopeError):
        await engine.result("workspace-b", ref)


def test_fake_external_effect_is_idempotent_and_preserves_unknown(tmp_path: Path) -> None:
    effects = FakeExternalEffects(tmp_path / "effects.sqlite3")
    request: dict[str, Any] = {"idempotency_key": "effect-1"}
    assert effects.apply(request) == {"outcome": "succeeded", "effect_count": 1}
    assert effects.apply(request) == {"outcome": "succeeded", "effect_count": 1}

    unknown = {"idempotency_key": "effect-2", "simulate_unknown": True}
    assert effects.apply(unknown) == {"outcome": "unknown", "effect_count": 1}
    assert effects.apply({"idempotency_key": "effect-2"}) == {
        "outcome": "unknown",
        "effect_count": 1,
    }


def test_only_approved_synthetic_workflows_are_registered() -> None:
    assert {
        getattr(definition, "__temporal_workflow_definition").name for definition in PROOF_WORKFLOWS
    } == {
        "proof.durable-counter",
        "proof.retry",
        "proof.approval",
        "proof.cancellation",
        "proof.timeout",
        "proof.idempotent-effect",
        "proof.unknown-outcome",
        "proof.versioned",
    }


def test_temporal_settings_are_proof_scoped_and_local_by_default() -> None:
    settings = TemporalSettings.load({})
    assert settings.target == "127.0.0.1:7233"
    assert settings.namespace == "default"
    assert settings.task_queue == "rightjob-phase25-proof"
    assert settings.credential is None
    assert settings.tls is False
