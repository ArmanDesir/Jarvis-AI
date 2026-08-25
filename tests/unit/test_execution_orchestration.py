from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import TracebackType
from typing import Sequence
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from rightjob.contracts.authorization import ExecutionAuthorizationReference
from rightjob.contracts.events import Actor, ActorType, AuditEvidence, IntegrationEvent
from rightjob.database import register_sqlalchemy_mappings
from rightjob.orchestration.application.compiler import (
    SyntheticWorkflowCompiler,
    WorkflowCompilationError,
)
from rightjob.orchestration.application.registry import (
    BUILT_IN_WORKFLOWS,
    WorkflowDefinition,
    WorkflowDefinitionStatus,
    WorkflowNotAvailableError,
    WorkflowRegistry,
)
from rightjob.orchestration.application.service import (
    ExecutionNotFoundError,
    OrchestrationApplicationService,
)
from rightjob.orchestration.domain import (
    ExecutionRequest,
    ExecutionRun,
    ExecutionStep,
    FailureClassification,
    InitiatorType,
    ReconciliationState,
    RequestedStep,
    RunStatus,
    StepStatus,
)
from rightjob.orchestration.domain.models import InvalidExecutionTransition
from rightjob.orchestration.infrastructure.models import (
    ExecutionRequestRecord,
    ExecutionRunRecord,
    ExecutionStepRecord,
)
from rightjob.registry import (
    BUILT_IN_DEPARTMENTS,
    BuiltInCapabilityRegistry,
    BuiltInDepartmentRegistry,
)
from rightjob.shared.clock import Clock

NOW = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
WORKSPACE = UUID("02700000-0000-4000-8000-000000000010")
OTHER_WORKSPACE = UUID("02700000-0000-4000-8000-000000000011")
RUN_ID = UUID("02700000-0000-4000-8000-000000000020")
STEP_IDS = tuple(UUID(f"02700000-0000-4000-8000-{number:012d}") for number in range(30, 33))


class FixedClock(Clock):
    def now(self) -> datetime:
        return NOW


def execution_request(workspace_id: UUID = WORKSPACE) -> ExecutionRequest:
    definition = BUILT_IN_WORKFLOWS[0]
    return ExecutionRequest(
        execution_id=RUN_ID,
        workspace_id=workspace_id,
        correlation_id=UUID("02700000-0000-4000-8000-000000000040"),
        causation_id=UUID("02700000-0000-4000-8000-000000000041"),
        actor=Actor(ActorType.USER, "user-1"),
        initiator_type=InitiatorType.USER,
        authorization=ExecutionAuthorizationReference(
            UUID(int=88), workspace_id, UUID(int=89), "0" * 64
        ),
        workflow_definition_id=definition.id,
        workflow_type=definition.workflow_type,
        workflow_version=definition.version,
        steps=tuple(
            RequestedStep(
                id=STEP_IDS[index],
                step_type=step.step_type,
                sequence=index,
                input_ref=f"request:{RUN_ID}:step:{index}",
                max_attempts=step.max_attempts,
            )
            for index, step in enumerate(definition.steps)
        ),
        input={"value": "safe synthetic input"},
        created_at=NOW,
    )


def execution_run(status: RunStatus = RunStatus.QUEUED) -> ExecutionRun:
    request = execution_request()
    return ExecutionRun(
        id=request.execution_id,
        execution_request_id=request.execution_id,
        workspace_id=request.workspace_id,
        workflow_definition_id=request.workflow_definition_id,
        workflow_type=request.workflow_type,
        workflow_version=request.workflow_version,
        status=status,
        correlation_id=request.correlation_id,
        causation_id=request.causation_id,
        actor=request.actor,
        initiator_type=request.initiator_type,
        created_at=NOW,
    )


def execution_step(status: StepStatus = StepStatus.PENDING) -> ExecutionStep:
    return ExecutionStep(
        id=STEP_IDS[0],
        run_id=RUN_ID,
        workspace_id=WORKSPACE,
        step_type="fake.prepare",
        sequence=0,
        status=status,
        attempt_count=0 if status is StepStatus.PENDING else 1,
        max_attempts=1,
        input_ref="request:step:0",
        started_at=NOW if status is not StepStatus.PENDING else None,
    )


def test_execution_request_rejects_unordered_and_unversioned_data() -> None:
    request = execution_request()
    with pytest.raises(ValueError, match="contiguous"):
        replace(request, steps=(request.steps[1], request.steps[0]))
    with pytest.raises(ValueError, match="workflow_version"):
        replace(request, workflow_version=" ")
    with pytest.raises(ValueError, match="secret-bearing"):
        replace(request, input={"nested": {"token": "not-allowed"}})


def test_run_state_machine_allows_declared_path_and_rejects_terminal_transition() -> None:
    running = execution_run().transition(RunStatus.RUNNING, NOW)
    waiting = running.transition(RunStatus.WAITING, NOW)
    resumed = waiting.transition(RunStatus.RUNNING, NOW)
    succeeded = resumed.transition(RunStatus.SUCCEEDED, NOW)
    assert succeeded.started_at == NOW
    assert succeeded.completed_at == NOW
    with pytest.raises(InvalidExecutionTransition):
        succeeded.transition(RunStatus.RUNNING, NOW)


def test_step_state_machine_tracks_attempts_failure_and_unknown_outcome() -> None:
    running = execution_step().transition(StepStatus.RUNNING, NOW)
    assert running.attempt_count == 1
    reconciliate = running.transition(StepStatus.RECONCILIATION_REQUIRED, NOW)
    assert reconciliate.failure_classification is FailureClassification.UNKNOWN_OUTCOME
    failed = reconciliate.transition(
        StepStatus.FAILED, NOW, failure=FailureClassification.INFRASTRUCTURE_EXHAUSTED
    )
    assert failed.failure_classification is FailureClassification.INFRASTRUCTURE_EXHAUSTED
    with pytest.raises(InvalidExecutionTransition):
        failed.transition(StepStatus.RUNNING, NOW)


def test_workflow_registry_selects_exact_enabled_version_and_stable_identity() -> None:
    registry = WorkflowRegistry()
    definition = registry.get_enabled("synthetic.sequence", "1.0.0")
    assert definition.id == UUID("02700000-0000-4000-8000-000000000001")
    with pytest.raises(WorkflowNotAvailableError):
        registry.get_enabled("synthetic.sequence", "2.0.0")
    disabled = WorkflowDefinition(
        id=UUID("02700000-0000-4000-8000-000000000099"),
        workflow_type="synthetic.disabled",
        version="1.0.0",
        input_schema={},
        steps=(),
        handler="rightjob.synthetic.disabled",
        status=WorkflowDefinitionStatus.DISABLED,
    )
    with pytest.raises(WorkflowNotAvailableError):
        WorkflowRegistry((disabled,)).get_enabled(disabled.workflow_type, disabled.version)


def test_compiler_is_deterministic_and_rejects_definition_drift() -> None:
    request = execution_request()
    definition = WorkflowRegistry().get_enabled(request.workflow_type, request.workflow_version)
    capabilities = BuiltInCapabilityRegistry()
    compiler = SyntheticWorkflowCompiler(capabilities, BuiltInDepartmentRegistry(capabilities))
    assert compiler.compile(request, definition) == compiler.compile(request, definition)
    changed = replace(request, workflow_definition_id=UUID(int=1))
    with pytest.raises(WorkflowCompilationError):
        compiler.compile(changed, definition)
    wrong_owner = replace(
        definition,
        steps=(
            replace(definition.steps[0], department=BUILT_IN_DEPARTMENTS[1].reference),
            *definition.steps[1:],
        ),
    )
    with pytest.raises(WorkflowCompilationError, match="not owned"):
        compiler.compile(request, wrong_owner)


class FakeRequests:
    def __init__(self, state: FakeState) -> None:
        self.state = state

    def add(self, workspace_id: UUID, request: ExecutionRequest) -> None:
        assert workspace_id == request.workspace_id
        key = (workspace_id, request.execution_id)
        if key in self.state.requests:
            raise ValueError("duplicate execution")
        self.state.requests[key] = request


class FakeRuns:
    def __init__(self, state: FakeState) -> None:
        self.state = state

    def add(self, workspace_id: UUID, run: ExecutionRun) -> None:
        assert workspace_id == run.workspace_id
        self.state.runs[(workspace_id, run.id)] = run

    def get(self, workspace_id: UUID, run_id: UUID) -> ExecutionRun | None:
        return self.state.runs.get((workspace_id, run_id))

    def save(self, workspace_id: UUID, run: ExecutionRun, expected_version: int) -> None:
        stored = self.state.runs.get((workspace_id, run.id))
        assert stored is not None and stored.version == expected_version
        self.state.runs[(workspace_id, run.id)] = run


class FakeSteps:
    def __init__(self, state: FakeState) -> None:
        self.state = state

    def add_all(self, workspace_id: UUID, steps: Sequence[ExecutionStep]) -> None:
        for step in steps:
            assert workspace_id == step.workspace_id
            self.state.steps[(workspace_id, step.id)] = step

    def get(self, workspace_id: UUID, step_id: UUID) -> ExecutionStep | None:
        return self.state.steps.get((workspace_id, step_id))

    def list_for_run(self, workspace_id: UUID, run_id: UUID) -> Sequence[ExecutionStep]:
        return [
            step
            for (scope, _), step in self.state.steps.items()
            if scope == workspace_id and step.run_id == run_id
        ]

    def save(self, workspace_id: UUID, step: ExecutionStep, expected_version: int) -> None:
        stored = self.state.steps.get((workspace_id, step.id))
        assert stored is not None and stored.version == expected_version
        self.state.steps[(workspace_id, step.id)] = step


class FakeAudit:
    def __init__(self, state: FakeState) -> None:
        self.state = state

    def append(self, workspace_id: UUID, evidence: AuditEvidence) -> None:
        assert workspace_id == evidence.workspace_id
        self.state.audit.append(evidence)


class FakeOutbox:
    def __init__(self, state: FakeState) -> None:
        self.state = state

    def add(self, workspace_id: UUID, event: IntegrationEvent) -> None:
        assert workspace_id == event.workspace_id
        self.state.outbox.append(event)


class FakeAuthorizations:
    def consume(
        self,
        reference: ExecutionAuthorizationReference,
        execution_id: UUID,
        workflow_definition_id: UUID,
        workflow_type: str,
        workflow_version: str,
        ordered_step_ids: tuple[UUID, ...],
        at: datetime,
    ) -> None:
        assert reference.workspace_id == WORKSPACE
        assert execution_id == RUN_ID
        assert at == NOW
        assert workflow_definition_id == BUILT_IN_WORKFLOWS[0].id
        assert workflow_type == "synthetic.sequence"
        assert workflow_version == "1.0.0"
        assert ordered_step_ids == STEP_IDS


@dataclass
class FakeState:
    requests: dict[tuple[UUID, UUID], ExecutionRequest]
    runs: dict[tuple[UUID, UUID], ExecutionRun]
    steps: dict[tuple[UUID, UUID], ExecutionStep]
    audit: list[AuditEvidence]
    outbox: list[IntegrationEvent]
    commits: int = 0


class FakeUnitOfWork:
    def __init__(self, state: FakeState) -> None:
        self.state = state
        self.requests = FakeRequests(state)
        self.runs = FakeRuns(state)
        self.steps = FakeSteps(state)
        self.audit_evidence = FakeAudit(state)
        self.outbox = FakeOutbox(state)
        self.authorizations = FakeAuthorizations()

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exception_type is not None:
            self.rollback()
        self.close()

    def commit(self) -> None:
        self.state.commits += 1

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


def state() -> FakeState:
    return FakeState({}, {}, {}, [], [])


def service(
    fake_state: FakeState, engine: AsyncMock | None = None
) -> OrchestrationApplicationService:
    durable_engine = engine or AsyncMock()
    durable_engine.start.return_value = type(
        "Ref", (), {"workflow_id": "id", "workspace_id": str(WORKSPACE)}
    )()
    capabilities = BuiltInCapabilityRegistry()
    return OrchestrationApplicationService(
        WorkflowRegistry(),
        SyntheticWorkflowCompiler(capabilities, BuiltInDepartmentRegistry(capabilities)),
        durable_engine,
        lambda: FakeUnitOfWork(fake_state),
        FixedClock(),
        id_factory=lambda: UUID(int=len(fake_state.audit) + len(fake_state.outbox) + 1),
    )


@pytest.mark.asyncio
async def test_orchestration_service_commits_canonical_state_with_audit_and_outbox() -> None:
    fake_state = state()
    engine = AsyncMock()
    engine.start.return_value = type(
        "Ref", (), {"workflow_id": "engine-id", "workspace_id": str(WORKSPACE)}
    )()
    application = service(fake_state, engine)
    compiled = application.create_execution(execution_request())
    await application.launch_execution(compiled)

    run = fake_state.runs[(WORKSPACE, RUN_ID)]
    assert run.status is RunStatus.RUNNING
    assert fake_state.commits == 2
    assert [item.action for item in fake_state.audit] == ["run.created", "run.running"]
    assert [item.event_type for item in fake_state.outbox] == [
        "execution.run.created.v1",
        "execution.run.running.v1",
    ]
    assert all(item.correlation_id == run.correlation_id for item in fake_state.outbox)


@pytest.mark.asyncio
async def test_cancellation_is_idempotent_and_cross_workspace_fails_closed() -> None:
    fake_state = state()
    engine = AsyncMock()
    application = service(fake_state, engine)
    application.create_execution(execution_request())
    application.transition_run(WORKSPACE, RUN_ID, RunStatus.RUNNING)

    cancelled = await application.request_cancellation(WORKSPACE, RUN_ID)
    repeated = await application.request_cancellation(WORKSPACE, RUN_ID)
    assert cancelled.status is RunStatus.CANCELLED
    assert repeated == cancelled
    engine.cancel.assert_awaited_once()
    with pytest.raises(ExecutionNotFoundError):
        await application.request_cancellation(OTHER_WORKSPACE, RUN_ID)


@pytest.mark.asyncio
async def test_unknown_cancellation_outcome_requires_reconciliation() -> None:
    fake_state = state()
    engine = AsyncMock()
    engine.cancel.side_effect = TimeoutError
    application = service(fake_state, engine)
    application.create_execution(execution_request())
    application.transition_run(WORKSPACE, RUN_ID, RunStatus.RUNNING)

    run = await application.request_cancellation(WORKSPACE, RUN_ID)
    assert run.status is RunStatus.RECONCILIATION_REQUIRED
    assert run.reconciliation_state is ReconciliationState.REQUIRED
    assert fake_state.audit[-1].action == "run.reconciliation_required"
    assert fake_state.outbox[-1].causation_id == run.causation_id


@pytest.mark.asyncio
async def test_unknown_launch_outcome_preserves_queued_record_for_reconciliation() -> None:
    fake_state = state()
    engine = AsyncMock()
    engine.start.side_effect = TimeoutError
    application = service(fake_state, engine)
    compiled = application.create_execution(execution_request())

    with pytest.raises(TimeoutError):
        await application.launch_execution(compiled)
    run = fake_state.runs[(WORKSPACE, RUN_ID)]
    assert run.status is RunStatus.RECONCILIATION_REQUIRED
    assert run.reconciliation_state is ReconciliationState.REQUIRED


def test_reconciliation_requires_explicit_reconciliation_state() -> None:
    fake_state = state()
    application = service(fake_state)
    application.create_execution(execution_request())
    with pytest.raises(ValueError, match="does not require"):
        application.reconcile_run(WORKSPACE, RUN_ID, RunStatus.RUNNING)


def test_execution_mappings_are_workspace_scoped_and_tenant_indexed() -> None:
    for table in (
        ExecutionRequestRecord.__table__,
        ExecutionRunRecord.__table__,
        ExecutionStepRecord.__table__,
    ):
        assert table.c.workspace_id.nullable is False
        assert any(
            tuple(column.name for column in index.columns)[0] == "workspace_id"
            for index in table.indexes
        )


def test_database_composition_registers_module_owned_mappings() -> None:
    assert set(register_sqlalchemy_mappings().tables) >= {
        "workspaces",
        "users",
        "memberships",
        "audit_entries",
        "outbox_events",
        "execution_requests",
        "execution_runs",
        "execution_steps",
    }


def test_revised_migration_contract_has_exact_keys_constraints_and_indexes() -> None:
    requests = ExecutionRequestRecord.__table__
    runs = ExecutionRunRecord.__table__
    steps = ExecutionStepRecord.__table__

    assert {constraint.name for constraint in requests.constraints} == {
        "pk_execution_requests",
        "uq_execution_requests_workspace_id",
        "uq_execution_requests_workspace_authorization",
        "fk_execution_requests_workspace",
        "fk_execution_requests_workspace_authorization",
        "ck_execution_requests_actor_type",
        "ck_execution_requests_actor_id_nonblank",
        "ck_execution_requests_workflow_type_nonblank",
        "ck_execution_requests_workflow_version_nonblank",
        "ck_execution_requests_input_object",
        "ck_execution_requests_input_size",
    }
    assert {constraint.name for constraint in runs.constraints} == {
        "pk_execution_runs",
        "uq_execution_runs_workspace_id",
        "uq_execution_runs_workspace_request",
        "fk_execution_runs_workspace",
        "fk_execution_runs_workspace_request",
        "ck_execution_runs_actor_type",
        "ck_execution_runs_actor_id_nonblank",
        "ck_execution_runs_workflow_type_nonblank",
        "ck_execution_runs_workflow_version_nonblank",
        "ck_execution_runs_status",
        "ck_execution_runs_reconciliation_state",
        "ck_execution_runs_version",
    }
    assert {constraint.name for constraint in steps.constraints} == {
        "pk_execution_steps",
        "uq_execution_steps_workspace_id",
        "uq_execution_steps_workspace_run_sequence",
        "fk_execution_steps_workspace",
        "fk_execution_steps_workspace_run",
        "ck_execution_steps_status",
        "ck_execution_steps_attempts",
        "ck_execution_steps_failure_classification",
        "ck_execution_steps_sequence",
        "ck_execution_steps_status_failure",
        "ck_execution_steps_step_type_nonblank",
        "ck_execution_steps_input_ref_nonblank",
        "ck_execution_steps_output_evidence_ref_nonblank",
        "ck_execution_steps_version",
    }
    assert {index.name for index in steps.indexes} == {"ix_execution_steps_workspace_status"}


def test_only_user_and_system_initiators_exist() -> None:
    assert set(InitiatorType) == {InitiatorType.USER, InitiatorType.SYSTEM}
