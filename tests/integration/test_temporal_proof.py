from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from rightjob.orchestration import WorkflowContext, WorkflowStatus
from rightjob_worker.proof_activities import (
    FakeExternalEffects,
    retry_activity,
    timeout_activity,
)
from rightjob_worker.proof_workflows import PROOF_WORKFLOWS, VersionedWorkflow
from rightjob_worker.temporal_adapter import TemporalWorkflowEngine, WorkflowScopeError
from temporalio import workflow
from temporalio.api.enums.v1 import TaskQueueType
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
from temporalio.client import Client, WorkflowFailureError
from temporalio.worker import Replayer, Worker

TARGET = os.environ.get("RIGHTJOB_TEMPORAL_TEST_TARGET")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TARGET, reason="Phase 2.5 Temporal runtime is not approved/running"),
]
QUEUE = "rightjob-phase25-proof"
MULTIPROCESS_QUEUE = "rightjob-phase25-proof-multiprocess"


def proof_context(workflow_type: str, operation: str) -> WorkflowContext:
    return WorkflowContext(
        workspace_id="00000000-0000-0000-0000-00000000025a",
        correlation_id=f"phase25-{operation}",
        logical_operation_id=operation,
        workflow_type=workflow_type,
        workflow_version=1,
    )


def worker_process(
    effect_db: Path,
    *,
    task_queue: str = QUEUE,
    worker_id: str = "phase25-worker-restart",
) -> subprocess.Popen[str]:
    environment = os.environ.copy()
    environment.update(
        RIGHTJOB_WORKER_ID=worker_id,
        RIGHTJOB_WORKFLOW_ENABLED="true",
        RIGHTJOB_WORKFLOW_ADAPTER="temporal",
        RIGHTJOB_TEMPORAL_TARGET=str(TARGET),
        RIGHTJOB_TEMPORAL_NAMESPACE="default",
        RIGHTJOB_TEMPORAL_TASK_QUEUE=task_queue,
        RIGHTJOB_TEMPORAL_EFFECT_DB=str(effect_db),
    )
    return subprocess.Popen(
        [sys.executable, "-m", "rightjob_worker.main"],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


async def stop_process(process: subprocess.Popen[str]) -> str:
    process.send_signal(signal.SIGTERM)
    output, _ = await asyncio.to_thread(process.communicate, timeout=15)
    assert process.returncode == 0, output
    return output


async def wait_for_counter(handle: Any) -> dict[str, Any]:
    for _ in range(100):
        try:
            state = await handle.query("state")
            if state["count"] == 1:
                return dict(state)
        except Exception:  # Temporal reports query failure until the first workflow task runs.
            pass
        await asyncio.sleep(0.05)
    raise AssertionError("counter workflow was not processed")


async def wait_for_worker_pollers(client: Client, task_queue: str, pids: set[int]) -> set[str]:
    for _ in range(100):
        response = await client.workflow_service.describe_task_queue(
            DescribeTaskQueueRequest(
                namespace="default",
                task_queue=TaskQueue(name=task_queue),
                task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW,
            )
        )
        identities = {poller.identity for poller in response.pollers}
        if all(any(identity.startswith(f"{pid}@") for identity in identities) for pid in pids):
            return identities
        await asyncio.sleep(0.1)
    raise AssertionError(f"worker PIDs {sorted(pids)} did not poll {task_queue}")


async def workflow_task_identities(client: Client, workflow_id: str) -> set[str]:
    history = await client.get_workflow_handle(workflow_id).fetch_history()
    return {
        event.workflow_task_started_event_attributes.identity
        for event in history.events
        if event.HasField("workflow_task_started_event_attributes")
    }


async def run_attributed_workflows(
    engine: TemporalWorkflowEngine,
    client: Client,
    operation_prefix: str,
    expected_pids: set[int],
    *,
    maximum: int = 24,
) -> tuple[set[int], set[str]]:
    observed_pids: set[int] = set()
    workflow_ids: set[str] = set()
    for index in range(maximum):
        context = proof_context("proof.versioned", f"{operation_prefix}-{index}")
        ref = await engine.start(context, {})
        assert ref.workflow_id not in workflow_ids
        workflow_ids.add(ref.workflow_id)
        result = (await engine.result(ref.workspace_id, ref)).value
        assert result["implementation"] == "v2"
        assert result["workspace_id"] == context.workspace_id
        assert result["correlation_id"] == context.correlation_id
        identities = await workflow_task_identities(client, ref.workflow_id)
        observed_pids.update(
            pid
            for pid in expected_pids
            if any(identity.startswith(f"{pid}@") for identity in identities)
        )
        if observed_pids == expected_pids:
            break
    return observed_pids, workflow_ids


@workflow.defn(name="proof.versioned")
class LegacyVersionedWorkflow:
    @workflow.run
    async def run(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "implementation": "v1",
            "input_version": data["context"]["workflow_version"],
        }


@pytest.mark.asyncio
async def test_phase25_temporal_proof(tmp_path: Path) -> None:
    assert TARGET is not None
    client = await Client.connect(TARGET)
    engine = TemporalWorkflowEngine(client, QUEUE)
    effect_db = tmp_path / "effects.sqlite3"

    # Durable state survives a complete worker process stop and replacement.
    first_worker = worker_process(effect_db)
    counter = await engine.start(proof_context("proof.durable-counter", "restart-counter"), {})
    handle = client.get_workflow_handle(counter.workflow_id)
    assert await wait_for_counter(handle) == {"count": 1, "waiting": True}
    first_log = await stop_process(first_worker)
    assert await engine.status(counter.workspace_id, counter) is WorkflowStatus.RUNNING
    second_worker = worker_process(effect_db)
    try:
        await engine.signal(counter.workspace_id, counter, "resume", {})
        counter_result = await asyncio.wait_for(
            engine.result(counter.workspace_id, counter), timeout=15
        )
        assert counter_result.value["count"] == 2
        assert counter_result.value["correlation_id"] == "phase25-restart-counter"
    finally:
        second_log = await stop_process(second_worker)
    assert "worker.started" in first_log + second_log
    assert "worker.stopped" in first_log + second_log

    effects = FakeExternalEffects(effect_db)
    activities = [retry_activity, timeout_activity, effects.execute]
    async with Worker(
        client,
        task_queue=QUEUE,
        workflows=PROOF_WORKFLOWS,
        activities=activities,
    ):
        retry = await engine.start(
            proof_context("proof.retry", "retry-success"),
            {"fail_attempts": 2, "maximum_attempts": 3},
        )
        assert (await engine.result(retry.workspace_id, retry)).value["attempt"] == 3

        bounded = await engine.start(
            proof_context("proof.retry", "retry-bounded"),
            {"fail_attempts": 3, "maximum_attempts": 2},
        )
        with pytest.raises(WorkflowFailureError):
            await engine.result(bounded.workspace_id, bounded)
        assert await engine.status(bounded.workspace_id, bounded) is WorkflowStatus.FAILED

        approval = await engine.start(proof_context("proof.approval", "approval"), {})
        await engine.signal(approval.workspace_id, approval, "approve", {})
        await engine.signal(approval.workspace_id, approval, "approve", {})
        approval_result = await engine.result(approval.workspace_id, approval)
        assert approval_result.value["accepted_signals"] == 1

        cancellation = await engine.start(proof_context("proof.cancellation", "cancellation"), {})
        await engine.cancel(cancellation.workspace_id, cancellation)
        with pytest.raises(WorkflowFailureError):
            await engine.result(cancellation.workspace_id, cancellation)
        assert (
            await engine.status(cancellation.workspace_id, cancellation) is WorkflowStatus.CANCELLED
        )

        timeout = await engine.start(
            proof_context("proof.timeout", "timeout"),
            {"sleep_seconds": 1, "timeout_seconds": 0.1},
        )
        assert (await engine.result(timeout.workspace_id, timeout)).value["state"] == "timed_out"

        idempotent = await engine.start(
            proof_context("proof.idempotent-effect", "idempotent"),
            {"idempotency_key": "phase25-effect-1"},
        )
        idempotent_result = (await engine.result(idempotent.workspace_id, idempotent)).value
        assert idempotent_result["first"]["effect_count"] == 1
        assert idempotent_result["second"]["effect_count"] == 1
        assert effects.count("phase25-effect-1") == 1

        unknown = await engine.start(
            proof_context("proof.unknown-outcome", "unknown"),
            {"idempotency_key": "phase25-effect-unknown"},
        )
        unknown_result = (await engine.result(unknown.workspace_id, unknown)).value
        assert unknown_result["state"] == "reconciliation_required"
        assert unknown_result["effect"] == {"outcome": "unknown", "effect_count": 1}
        assert effects.count("phase25-effect-unknown") == 1

        with pytest.raises(WorkflowScopeError):
            await engine.status("00000000-0000-0000-0000-00000000025b", unknown)

    # An unpatched v1 history replays deterministically through the patched v2 code.
    legacy_queue = f"{QUEUE}-legacy"
    async with Worker(client, task_queue=legacy_queue, workflows=[LegacyVersionedWorkflow]):
        legacy = await client.start_workflow(
            "proof.versioned",
            {
                "context": proof_context("proof.versioned", "legacy").__dict__,
                "payload": {},
            },
            id="rightjob-phase25-legacy-version",
            task_queue=legacy_queue,
        )
        assert (await legacy.result())["implementation"] == "v1"
        history = await legacy.fetch_history()
    replay = await Replayer(workflows=[VersionedWorkflow]).replay_workflow(history)
    assert replay.replay_failure is None


@pytest.mark.asyncio
async def test_phase25_temporal_multiprocess_proof(tmp_path: Path) -> None:
    assert TARGET is not None
    client = await Client.connect(TARGET)
    effect_db = tmp_path / "effects.sqlite3"

    # Independent worker processes safely share one task queue and survive turnover.
    multiprocess_engine = TemporalWorkflowEngine(client, MULTIPROCESS_QUEUE)
    worker_a = worker_process(
        effect_db,
        task_queue=MULTIPROCESS_QUEUE,
        worker_id="phase25-worker-a",
    )
    worker_b = worker_process(
        effect_db,
        task_queue=MULTIPROCESS_QUEUE,
        worker_id="phase25-worker-b",
    )
    assert worker_a.pid != worker_b.pid
    assert worker_a.pid is not None
    assert worker_b.pid is not None
    worker_a_logs = ""
    worker_b_logs = ""
    restarted_a_logs = ""
    try:
        initial_pids = {worker_a.pid, worker_b.pid}
        initial_pollers = await wait_for_worker_pollers(client, MULTIPROCESS_QUEUE, initial_pids)
        assert all(
            any(identity.startswith(f"{pid}@") for identity in initial_pollers)
            for pid in initial_pids
        )

        initial_observed, initial_ids = await run_attributed_workflows(
            multiprocess_engine,
            client,
            "multiprocess-initial",
            initial_pids,
        )
        assert initial_observed == initial_pids

        worker_a_logs = await stop_process(worker_a)
        assert worker_b.poll() is None
        survivor_observed, survivor_ids = await run_attributed_workflows(
            multiprocess_engine,
            client,
            "multiprocess-survivor-b",
            {worker_b.pid},
            maximum=4,
        )
        assert survivor_observed == {worker_b.pid}

        restarted_a = worker_process(
            effect_db,
            task_queue=MULTIPROCESS_QUEUE,
            worker_id="phase25-worker-a",
        )
        assert restarted_a.pid is not None
        assert restarted_a.pid not in initial_pids
        try:
            resumed_pids = {restarted_a.pid, worker_b.pid}
            resumed_pollers = await wait_for_worker_pollers(
                client, MULTIPROCESS_QUEUE, resumed_pids
            )
            assert all(
                any(identity.startswith(f"{pid}@") for identity in resumed_pollers)
                for pid in resumed_pids
            )
            resumed_observed, resumed_ids = await run_attributed_workflows(
                multiprocess_engine,
                client,
                "multiprocess-resumed",
                resumed_pids,
            )
            assert resumed_observed == resumed_pids
            assert len(initial_ids | survivor_ids | resumed_ids) == (
                len(initial_ids) + len(survivor_ids) + len(resumed_ids)
            )
        finally:
            restarted_a_logs = await stop_process(restarted_a)
    finally:
        if worker_a.poll() is None:
            worker_a_logs = await stop_process(worker_a)
        if worker_b.poll() is None:
            worker_b_logs = await stop_process(worker_b)

    assert '"worker_id":"phase25-worker-a"' in worker_a_logs + restarted_a_logs
    assert '"worker_id":"phase25-worker-b"' in worker_b_logs
    assert "worker.started" in worker_a_logs + worker_b_logs + restarted_a_logs
    assert "worker.stopped" in worker_a_logs + worker_b_logs + restarted_a_logs
