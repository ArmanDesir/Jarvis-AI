from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from rightjob.contracts.revision import QualityGateStatus
from rightjob.contracts.revision_execution import RevisionExecutionStatus, revision_workflow_id
from rightjob.orchestration.application.revision_execution import DurableRevisionLifecycleService
from rightjob.registry.catalog import BuiltInCapabilityRegistry
from rightjob.registry.departments import BuiltInDepartmentRegistry
from rightjob.validation import CapabilityResultValidator
from rightjob_worker.revision_runtime import (
    WORKFLOW_TYPE,
    RevisionRuntimeService,
    TemporalRevisionWorkflow,
    _identity,
    _request,
)
from sqlalchemy import text
from temporalio.client import Client, WorkflowFailureError

from tests.integration.test_revision_execution_transactions import (
    WORKSPACE,
    _service,
    _uow_factory,
)
from tests.integration.test_revision_execution_transactions import (
    engines as _revision_engines,
)
from tests.integration.test_temporal_proof import stop_process, worker_process
from tests.unit.test_revision_execution import GATE, authorized_command

TARGET = os.environ.get("RIGHTJOB_TEMPORAL_TEST_TARGET")
QUEUE = "rightjob-phase220-revision"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TARGET, reason="isolated Stage C2 Temporal runtime required"),
]


@pytest.fixture
def engines():  # type: ignore[no-untyped-def]
    yield from _revision_engines.__wrapped__()


class _Clock:
    def __init__(self) -> None:
        self.value = datetime.now(UTC)

    def __call__(self) -> datetime:
        self.value += timedelta(milliseconds=1)
        return self.value


@pytest.mark.asyncio
async def test_real_temporal_revision_reaches_awaiting_review(
    engines,
    tmp_path,  # type: ignore[no-untyped-def]
):
    assert TARGET is not None
    owner, app = engines
    command, authorization = authorized_command()
    claim = _service(app).claim(command, authorization)
    capabilities = BuiltInCapabilityRegistry()
    clock = _Clock()
    client = await Client.connect(TARGET)
    temporal = TemporalRevisionWorkflow(client, QUEUE)
    runtime = RevisionRuntimeService(
        DurableRevisionLifecycleService(_uow_factory(app)),
        temporal,
        capabilities,
        BuiltInDepartmentRegistry(capabilities),
        CapabilityResultValidator(
            capabilities,
            lambda: UUID("00000000-0000-4000-8000-000000022001"),
            clock,
        ),
        clock,
    )

    # Launch is committed and accepted while no worker is running.
    launches = await asyncio.gather(
        runtime.launch(command, claim),
        runtime.launch(command, claim),
        return_exceptions=True,
    )
    accepted = [item for item in launches if not isinstance(item, BaseException)]
    assert len(accepted) == 1
    running = accepted[0]
    assert not isinstance(running, BaseException)
    assert running.status is RevisionExecutionStatus.RUNNING
    assert running.workflow_id == revision_workflow_id(command.action)
    assert (
        await temporal.inspect(
            running.workflow_id,
            _identity(_request(running)),
        )
    ).existence.value == "matching"

    # The actual worker composition starts later and safely resumes the durable workflow.
    worker = worker_process(tmp_path / "effects.sqlite3", task_queue=QUEUE)
    try:
        completed = await runtime.complete(command, running)
    finally:
        worker_log = await stop_process(worker)

    assert completed.status is RevisionExecutionStatus.COMPLETED
    assert completed.result_artifact is not None
    assert completed.result_artifact.version == command.action.source_artifact.version + 1
    assert completed.result_artifact.sha256 != command.action.source_artifact.sha256
    assert "worker.started" in worker_log and "worker.stopped" in worker_log
    with owner.connect() as connection:
        assert connection.execute(
            text(
                "SELECT status,automated_revision_count FROM quality_gate_states "
                "WHERE workspace_id=:workspace AND id=:gate"
            ),
            {"workspace": WORKSPACE, "gate": GATE},
        ).one() == (QualityGateStatus.AWAITING_REVIEW.value, 1)


@pytest.mark.asyncio
async def test_direct_temporal_launch_cannot_bypass_durable_claim(
    engines,
    tmp_path,  # type: ignore[no-untyped-def]
):
    assert TARGET is not None
    owner, app = engines
    command, authorization = authorized_command()
    claim = _service(app).claim(command, authorization)
    client = await Client.connect(TARGET)
    worker = worker_process(tmp_path / "direct-effects.sqlite3", task_queue=QUEUE)
    try:
        handle = await client.start_workflow(
            WORKFLOW_TYPE,
            _request(claim),
            id=f"fabricated:{revision_workflow_id(command.action)}",
            task_queue=QUEUE,
        )
        with pytest.raises(WorkflowFailureError):
            await handle.result()
    finally:
        await stop_process(worker)
    with owner.connect() as connection:
        assert connection.execute(
            text(
                "SELECT status,workflow_id FROM revision_execution_claims "
                "WHERE workspace_id=:workspace AND id=:claim"
            ),
            {"workspace": WORKSPACE, "claim": claim.claim_id},
        ).one() == (RevisionExecutionStatus.CLAIMED.value, None)
