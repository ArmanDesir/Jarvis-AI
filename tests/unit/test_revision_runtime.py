from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest
from rightjob.contracts.review import (
    ResultValidationEvidence,
    ResultValidationOutcome,
    ResultValidationReason,
    ValidationCriteriaReference,
)
from rightjob.contracts.revision import QualityGateStatus
from rightjob.contracts.revision_execution import (
    RevisionExecutionContractError,
    RevisionExecutionStatus,
    RevisionLifecycleReason,
)
from rightjob.orchestration.application.revision_execution import (
    DurableRevisionExecutionClaimService,
    DurableRevisionLifecycleService,
)
from rightjob.registry.catalog import BuiltInCapabilityRegistry
from rightjob.registry.departments import BuiltInDepartmentRegistry
from rightjob.validation import CapabilityResultValidator
from rightjob_worker.revision_activities import regenerate_artifact_result
from rightjob_worker.revision_runtime import (
    RevisionLaunchAmbiguous,
    RevisionLaunchRejected,
    RevisionRuntimeService,
    RevisionWorkflowExistence,
    RevisionWorkflowInspection,
    RevisionWorkflowMismatch,
    TemporalRevisionWorkflow,
    _identity,
    _request,
)
from temporalio.client import Client, WorkflowExecutionStatus, WorkflowFailureError
from temporalio.exceptions import WorkflowAlreadyStartedError

from tests.unit.test_revision_execution import (
    NOW,
    VERSION_1,
    U,
    _claimed_runtime,
    _lifecycle_uow,
    _Uow,
    action,
    authorized_command,
    gate,
    service,
)


class _Clock:
    def __init__(self) -> None:
        self.value = NOW + timedelta(minutes=2)

    def __call__(self):  # type: ignore[no-untyped-def]
        value = self.value
        self.value += timedelta(seconds=1)
        return value


class _Temporal:
    def __init__(self) -> None:
        self.request: dict[str, Any] | None = None
        self.start_error: Exception | None = None
        self.inspection = RevisionWorkflowInspection(
            RevisionWorkflowExistence.MATCHING, WorkflowExecutionStatus.RUNNING
        )
        self.cancelled = 0
        self.inspected = 0
        self.results = 0
        self.cancel_error: Exception | None = None
        self.cancel_status = WorkflowExecutionStatus.CANCELED
        self.result_error: Exception | None = None

    async def start(self, workflow_id: str, request: dict[str, Any]) -> None:
        self.request = request
        if self.start_error:
            raise self.start_error

    async def inspect(
        self, workflow_id: str, identity: dict[str, Any]
    ) -> RevisionWorkflowInspection:
        self.inspected += 1
        return self.inspection

    async def result(self, workflow_id: str) -> dict[str, Any]:
        self.results += 1
        if self.result_error:
            raise self.result_error
        assert self.request is not None
        return regenerate_artifact_result(self.request)

    async def cancel_and_confirm(
        self, workflow_id: str, identity: dict[str, Any]
    ) -> RevisionWorkflowInspection:
        self.cancelled += 1
        if self.cancel_error:
            raise self.cancel_error
        return RevisionWorkflowInspection(RevisionWorkflowExistence.MATCHING, self.cancel_status)


class _FailValidator:
    def validate(self, result, context):  # type: ignore[no-untyped-def]
        return ResultValidationEvidence(
            U(301),
            result,
            ValidationCriteriaReference("result.contract", VERSION_1),
            ResultValidationOutcome.FAILED,
            (ResultValidationReason.ARTIFACT_MISMATCH,),
            (),
            NOW + timedelta(minutes=10),
        )


def _runtime(temporal: _Temporal, cycle: int = 1):  # type: ignore[no-untyped-def]
    item = action(cycle=cycle)
    command, authorization = authorized_command(item)
    decision, state = gate(item)
    claimed_uow = _Uow(decision, state)
    claim = DurableRevisionExecutionClaimService(service(), lambda: claimed_uow).claim(
        command, authorization
    )
    uow = _lifecycle_uow(decision, state, claimed_uow, claim)
    clock = _Clock()
    capabilities = BuiltInCapabilityRegistry()
    return (
        command,
        claim,
        uow,
        RevisionRuntimeService(
            DurableRevisionLifecycleService(lambda: uow),
            cast(TemporalRevisionWorkflow, temporal),
            capabilities,
            BuiltInDepartmentRegistry(capabilities),
            CapabilityResultValidator(capabilities, lambda: U(300), clock),
            clock,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("cycle", [1, 2])
async def test_runtime_completes_one_safe_idempotent_artifact_and_stops_for_review(
    cycle: int,
) -> None:
    temporal = _Temporal()
    command, claim, uow, runtime = _runtime(temporal, cycle)
    completed = await runtime.execute(command, claim)

    assert completed.status is RevisionExecutionStatus.COMPLETED
    assert completed.result_artifact is not None
    assert completed.result_artifact.artifact_id == command.action.source_artifact.artifact_id
    assert completed.result_artifact.version == command.action.source_artifact.version + 1
    assert completed.result_artifact.sha256 != command.action.source_artifact.sha256
    assert uow.quality_gate_states.value.status is QualityGateStatus.AWAITING_REVIEW
    assert uow.quality_gate_states.value.automated_revision_count == cycle
    assert temporal.request is not None
    assert "prompt" not in temporal.request and "instructions" not in temporal.request
    assert regenerate_artifact_result(temporal.request) == regenerate_artifact_result(
        temporal.request
    )


@pytest.mark.asyncio
async def test_launch_outcomes_preserve_exact_truth() -> None:
    rejected = _Temporal()
    rejected.start_error = RevisionLaunchRejected()
    command, claim, uow, runtime = _runtime(rejected)
    failed = await runtime.launch(command, claim)
    assert failed.status is RevisionExecutionStatus.FAILED
    assert failed.lifecycle_reason is RevisionLifecycleReason.LAUNCH_REJECTED
    assert failed.running_at is None
    assert uow.runs.value.status.value == uow.steps.value.status.value == "failed"

    ambiguous = _Temporal()
    ambiguous.start_error = RevisionLaunchAmbiguous()
    command, claim, _, runtime = _runtime(ambiguous)
    unknown = await runtime.launch(command, claim)
    assert unknown.status is RevisionExecutionStatus.RECONCILIATION_REQUIRED
    assert unknown.running_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("existence", "starts", "running"),
    [
        (RevisionWorkflowExistence.MATCHING, 0, True),
        (RevisionWorkflowExistence.ABSENT, 1, True),
        (RevisionWorkflowExistence.UNKNOWN, 0, False),
    ],
)
async def test_reconciliation_adopts_relaunches_or_waits(
    existence: RevisionWorkflowExistence, starts: int, running: bool
) -> None:
    temporal = _Temporal()
    temporal.start_error = RevisionLaunchAmbiguous()
    command, claim, _, runtime = _runtime(temporal)
    unknown = await runtime.launch(command, claim)
    temporal.start_error = None
    temporal.request = None
    temporal.inspection = RevisionWorkflowInspection(
        existence,
        WorkflowExecutionStatus.RUNNING
        if existence is RevisionWorkflowExistence.MATCHING
        else None,
    )
    reconciled = await runtime.reconcile(command, unknown)
    assert (temporal.request is not None) is bool(starts)
    assert (reconciled.status is RevisionExecutionStatus.RUNNING) is running


@pytest.mark.asyncio
async def test_reconciliation_mismatch_fails_closed() -> None:
    temporal = _Temporal()
    temporal.start_error = RevisionLaunchAmbiguous()
    command, claim, _, runtime = _runtime(temporal)
    unknown = await runtime.launch(command, claim)
    temporal.inspection = RevisionWorkflowInspection(RevisionWorkflowExistence.MISMATCH)
    with pytest.raises(RevisionWorkflowMismatch):
        await runtime.reconcile(command, unknown)


@pytest.mark.asyncio
async def test_permanent_failure_and_confirmed_cancellation_are_terminal() -> None:
    temporal = _Temporal()
    temporal.result_error = WorkflowFailureError(cause=RuntimeError("permanent"))
    command, claim, uow, runtime = _runtime(temporal)
    failed = await runtime.execute(command, claim)
    assert failed.status is RevisionExecutionStatus.FAILED
    assert uow.quality_gate_states.value.automated_revision_count == 1

    temporal = _Temporal()
    command, claim, _, runtime = _runtime(temporal)
    running = await runtime.launch(command, claim)
    cancelled = await runtime.cancel(command, running)
    assert cancelled.status is RevisionExecutionStatus.CANCELLED
    assert await runtime.cancel(command, cancelled) is cancelled
    assert temporal.cancelled == 1


@pytest.mark.asyncio
async def test_validation_failure_fails_without_completion_or_review() -> None:
    temporal = _Temporal()
    command, claim, uow, runtime = _runtime(temporal)
    runtime._validator = cast(CapabilityResultValidator, _FailValidator())
    failed = await runtime.execute(command, claim)
    assert failed.status is RevisionExecutionStatus.FAILED
    assert failed.lifecycle_reason is RevisionLifecycleReason.VALIDATION_FAILED
    assert uow.quality_gate_states.value.status is QualityGateStatus.REVISION_REQUIRED
    assert uow.quality_gate_states.value.automated_revision_count == 1


@pytest.mark.asyncio
async def test_stale_prelaunch_request_blocks_temporal_contact() -> None:
    temporal = _Temporal()
    command, claim, uow, runtime = _runtime(temporal)
    uow.requests.items[0].input["action_type"] = "tampered"
    with pytest.raises(RevisionExecutionContractError, match="launch authority is stale"):
        await runtime.launch(command, claim)
    assert temporal.request is None
    assert uow.revision_execution_claims.value.status is RevisionExecutionStatus.CLAIMED


@pytest.mark.asyncio
async def test_ambiguous_cancellation_does_not_fabricate_cancelled() -> None:
    temporal = _Temporal()
    command, claim, uow, runtime = _runtime(temporal)
    running = await runtime.launch(command, claim)
    temporal.cancel_error = RuntimeError("unknown cancellation outcome")
    with pytest.raises(RuntimeError, match="unknown cancellation"):
        await runtime.cancel(command, running)
    assert uow.revision_execution_claims.value.status is RevisionExecutionStatus.RUNNING


@pytest.mark.asyncio
async def test_cancellation_acknowledgement_without_terminal_status_is_not_confirmed() -> None:
    temporal = _Temporal()
    command, claim, uow, runtime = _runtime(temporal)
    running = await runtime.launch(command, claim)
    temporal.inspection = RevisionWorkflowInspection(
        RevisionWorkflowExistence.MATCHING, WorkflowExecutionStatus.RUNNING
    )
    temporal.cancel_status = WorkflowExecutionStatus.RUNNING
    returned = await runtime.cancel(command, running)
    assert returned.status is RevisionExecutionStatus.RUNNING
    assert uow.revision_execution_claims.value.status is RevisionExecutionStatus.RUNNING


@pytest.mark.asyncio
async def test_untrusted_claims_fail_before_every_temporal_contact() -> None:
    temporal = _Temporal()
    temporal.start_error = RevisionLaunchAmbiguous()
    command, claim, _, runtime = _runtime(temporal)
    reconciliation = await runtime.launch(command, claim)
    temporal.start_error = None
    temporal.request = None
    forged_reconciliation = replace(reconciliation, version=reconciliation.version + 1)
    with pytest.raises(RevisionExecutionContractError, match="version is stale"):
        await runtime.reconcile(command, forged_reconciliation)
    assert temporal.inspected == 0 and temporal.request is None

    temporal = _Temporal()
    command, claim, _, runtime = _runtime(temporal)
    running = await runtime.launch(command, claim)
    forged_running = replace(running, version=running.version + 1)
    with pytest.raises(RevisionExecutionContractError, match="version is stale"):
        await runtime.complete(command, forged_running)
    with pytest.raises(RevisionExecutionContractError, match="version is stale"):
        await runtime.cancel(command, forged_running)
    assert temporal.results == temporal.cancelled == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("temporal_status", "durable_status", "reason"),
    [
        (
            WorkflowExecutionStatus.FAILED,
            RevisionExecutionStatus.FAILED,
            RevisionLifecycleReason.WORKFLOW_FAILED,
        ),
        (
            WorkflowExecutionStatus.CANCELED,
            RevisionExecutionStatus.CANCELLED,
            RevisionLifecycleReason.WORKFLOW_CANCELLED,
        ),
        (
            WorkflowExecutionStatus.TERMINATED,
            RevisionExecutionStatus.FAILED,
            RevisionLifecycleReason.WORKFLOW_TERMINATED,
        ),
        (
            WorkflowExecutionStatus.TIMED_OUT,
            RevisionExecutionStatus.FAILED,
            RevisionLifecycleReason.WORKFLOW_TIMED_OUT,
        ),
    ],
)
async def test_reconciliation_terminal_statuses_do_not_fabricate_running(
    temporal_status: WorkflowExecutionStatus,
    durable_status: RevisionExecutionStatus,
    reason: RevisionLifecycleReason,
) -> None:
    temporal = _Temporal()
    temporal.start_error = RevisionLaunchAmbiguous()
    command, claim, uow, runtime = _runtime(temporal)
    reconciliation = await runtime.launch(command, claim)
    temporal.start_error = None
    temporal.inspection = RevisionWorkflowInspection(
        RevisionWorkflowExistence.MATCHING, temporal_status
    )
    terminal = await runtime.reconcile(command, reconciliation)
    assert terminal.status is durable_status and terminal.lifecycle_reason is reason
    assert terminal.running_at is None
    assert uow.runs.value.status.value == durable_status.value
    assert uow.steps.value.status.value == durable_status.value


@pytest.mark.asyncio
async def test_reconciliation_completed_validates_without_fabricating_running() -> None:
    temporal = _Temporal()
    temporal.start_error = RevisionLaunchAmbiguous()
    command, claim, uow, runtime = _runtime(temporal)
    reconciliation = await runtime.launch(command, claim)
    temporal.start_error = None
    temporal.inspection = RevisionWorkflowInspection(
        RevisionWorkflowExistence.MATCHING, WorkflowExecutionStatus.COMPLETED
    )
    completed = await runtime.reconcile(command, reconciliation)
    assert completed.status is RevisionExecutionStatus.COMPLETED
    assert completed.running_at is None
    assert completed.reconciliation_required_at is not None
    assert uow.quality_gate_states.value.status is QualityGateStatus.AWAITING_REVIEW


@pytest.mark.asyncio
async def test_duplicate_completion_returns_durable_result_without_temporal_contact() -> None:
    temporal = _Temporal()
    command, claim, _, runtime = _runtime(temporal)
    running = await runtime.launch(command, claim)
    completed = await runtime.complete(command, running)
    result_calls = temporal.results
    assert await runtime.complete(command, running) == completed
    assert temporal.results == result_calls


@pytest.mark.asyncio
async def test_temporal_duplicate_is_adopted_only_for_exact_identity() -> None:
    command, _, _, _, claim = _claimed_runtime()
    request = _request(claim)
    description = SimpleNamespace(
        id="workflow-id",
        workflow_type="rightjob.revision.regenerate_artifact",
        status=WorkflowExecutionStatus.RUNNING,
        memo=lambda: _async_value({"rightjob_revision_identity": _identity(request)}),
    )
    handle = SimpleNamespace(describe=lambda: _async_value(description))
    client = SimpleNamespace(
        start_workflow=lambda *args, **kwargs: _async_error(
            WorkflowAlreadyStartedError(workflow_id="workflow-id", workflow_type="type")
        ),
        get_workflow_handle=lambda workflow_id: handle,
    )
    temporal = TemporalRevisionWorkflow(cast(Client, client), "queue")
    await temporal.start("workflow-id", request)

    description.memo = lambda: _async_value({"rightjob_revision_identity": {}})
    with pytest.raises(RevisionWorkflowMismatch):
        await temporal.start("workflow-id", request)
    assert command.action.reserved_cycle == 1


async def _async_value(value: Any) -> Any:
    return value


async def _async_error(error: Exception) -> None:
    raise error
