"""Canonical orchestration commands and Audit/Outbox transaction coordination."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

from rightjob.contracts.events import (
    AuditEvidence,
    AuditOutcome,
    DataSensitivity,
    IntegrationEvent,
    JsonValue,
)
from rightjob.orchestration.application.compiler import WorkflowCompiler
from rightjob.orchestration.application.registry import WorkflowRegistry
from rightjob.orchestration.application.repositories import ExecutionUnitOfWork
from rightjob.orchestration.domain import (
    CompiledExecution,
    ExecutionRequest,
    ExecutionRun,
    ExecutionStep,
    FailureClassification,
    ReconciliationState,
    RunStatus,
    StepStatus,
)
from rightjob.orchestration.engine import DurableWorkflowEngine, WorkflowContext, WorkflowRef
from rightjob.shared.clock import Clock

UnitOfWorkFactory = Callable[[], ExecutionUnitOfWork]
IdFactory = Callable[[], UUID]


class ExecutionNotFoundError(LookupError):
    """An execution is absent from the authorized Workspace scope."""


class OrchestrationApplicationService:
    def __init__(
        self,
        registry: WorkflowRegistry,
        compiler: WorkflowCompiler,
        engine: DurableWorkflowEngine,
        unit_of_work: UnitOfWorkFactory,
        clock: Clock,
        id_factory: IdFactory = uuid4,
    ) -> None:
        self._registry = registry
        self._compiler = compiler
        self._engine = engine
        self._unit_of_work = unit_of_work
        self._clock = clock
        self._id = id_factory

    def create_execution(self, request: ExecutionRequest) -> CompiledExecution:
        definition = self._registry.get_enabled(request.workflow_type, request.workflow_version)
        compiled = self._compiler.compile(request, definition)
        run = ExecutionRun(
            id=request.execution_id,
            execution_request_id=request.execution_id,
            workspace_id=request.workspace_id,
            workflow_definition_id=definition.id,
            workflow_type=definition.workflow_type,
            workflow_version=definition.version,
            status=RunStatus.QUEUED,
            correlation_id=request.correlation_id,
            causation_id=request.causation_id,
            actor=request.actor,
            initiator_type=request.initiator_type,
            created_at=request.created_at,
        )
        steps = tuple(
            ExecutionStep(
                id=step.id,
                run_id=run.id,
                workspace_id=run.workspace_id,
                step_type=step.step_type,
                sequence=step.sequence,
                status=StepStatus.PENDING,
                attempt_count=0,
                max_attempts=step.max_attempts,
                input_ref=step.input_ref,
            )
            for step in request.steps
        )
        with self._unit_of_work() as uow:
            uow.authorizations.consume(
                request.authorization,
                request.execution_id,
                request.workflow_definition_id,
                request.workflow_type,
                request.workflow_version,
                tuple(step.id for step in request.steps),
                request.created_at,
            )
            uow.requests.add(request.workspace_id, request)
            uow.runs.add(request.workspace_id, run)
            uow.steps.add_all(request.workspace_id, steps)
            self._record(uow, run, "run.created", "execution.run.created.v1")
            uow.commit()
        return compiled

    async def launch_execution(self, compiled: CompiledExecution) -> WorkflowRef:
        context = compiled.context
        workflow_context = WorkflowContext(
            workspace_id=str(context.workspace_id),
            correlation_id=str(context.correlation_id),
            causation_id=str(context.causation_id) if context.causation_id else None,
            logical_operation_id=str(context.execution_id),
            workflow_type=compiled.workflow_type,
            workflow_version=compiled.workflow_version,
        )
        try:
            ref = await self._engine.start(workflow_context, self._engine_payload(compiled))
        except Exception:
            self.transition_run(
                context.workspace_id,
                context.execution_id,
                RunStatus.RECONCILIATION_REQUIRED,
            )
            raise
        self.transition_run(context.workspace_id, context.execution_id, RunStatus.RUNNING)
        return ref

    def reconcile_run(
        self, workspace_id: UUID, run_id: UUID, resolved_status: RunStatus
    ) -> ExecutionRun:
        with self._unit_of_work() as uow:
            run = self._get_run(uow, workspace_id, run_id)
            if run.status is not RunStatus.RECONCILIATION_REQUIRED:
                raise ValueError("run does not require reconciliation")
        return self.transition_run(workspace_id, run_id, resolved_status)

    def transition_run(self, workspace_id: UUID, run_id: UUID, status: RunStatus) -> ExecutionRun:
        with self._unit_of_work() as uow:
            run = self._get_run(uow, workspace_id, run_id)
            updated = run.transition(status, self._clock.now())
            uow.runs.save(workspace_id, updated, run.version)
            self._record(uow, updated, f"run.{status.value}", f"execution.run.{status.value}.v1")
            uow.commit()
            return updated

    def transition_step(
        self,
        workspace_id: UUID,
        step_id: UUID,
        status: StepStatus,
        *,
        failure: FailureClassification | None = None,
        evidence_ref: str | None = None,
    ) -> ExecutionStep:
        with self._unit_of_work() as uow:
            step = uow.steps.get(workspace_id, step_id)
            if step is None:
                raise ExecutionNotFoundError("execution step not found")
            updated = step.transition(
                status, self._clock.now(), failure=failure, evidence_ref=evidence_ref
            )
            uow.steps.save(workspace_id, updated, step.version)
            run = self._get_run(uow, workspace_id, step.run_id)
            self._record(
                uow,
                run,
                f"step.{status.value}",
                f"execution.step.{status.value}.v1",
                resource_type="execution_step",
                resource_id=step.id,
                payload={
                    "run_id": str(run.id),
                    "step_id": str(step.id),
                    "status": status.value,
                    "failure_classification": failure.value if failure else None,
                    "evidence_ref": evidence_ref,
                },
            )
            uow.commit()
            return updated

    async def request_cancellation(self, workspace_id: UUID, run_id: UUID) -> ExecutionRun:
        with self._unit_of_work() as uow:
            run = self._get_run(uow, workspace_id, run_id)
            requested = run.request_cancellation(self._clock.now())
            if requested is run:
                return run
            uow.runs.save(workspace_id, requested, run.version)
            self._record(
                uow,
                requested,
                "run.cancellation_requested",
                "execution.run.cancellation_requested.v1",
            )
            uow.commit()
        if requested.status is RunStatus.QUEUED:
            return self.transition_run(workspace_id, run_id, RunStatus.CANCELLED)
        try:
            await self._engine.cancel(str(workspace_id), self._workflow_ref(requested))
        except Exception:
            return self.transition_run(workspace_id, run_id, RunStatus.RECONCILIATION_REQUIRED)
        return self.transition_run(workspace_id, run_id, RunStatus.CANCELLED)

    def _workflow_ref(self, run: ExecutionRun) -> WorkflowRef:
        definition = self._registry.get_enabled(run.workflow_type, run.workflow_version)
        context = WorkflowContext(
            workspace_id=str(run.workspace_id),
            correlation_id=str(run.correlation_id),
            causation_id=str(run.causation_id) if run.causation_id else None,
            logical_operation_id=str(run.id),
            workflow_type=definition.handler,
            workflow_version=run.workflow_version,
        )
        return WorkflowRef(context.canonical_id(), str(run.workspace_id))

    @staticmethod
    def _get_run(uow: ExecutionUnitOfWork, workspace_id: UUID, run_id: UUID) -> ExecutionRun:
        run = uow.runs.get(workspace_id, run_id)
        if run is None:
            raise ExecutionNotFoundError("execution run not found")
        return run

    @staticmethod
    def _engine_payload(compiled: CompiledExecution) -> dict[str, JsonValue]:
        return {
            "workflow_definition_id": str(compiled.workflow_definition_id),
            "steps": [
                {
                    "id": str(step.id),
                    "type": step.step_type,
                    "sequence": step.sequence,
                    "input_ref": step.input_ref,
                    "max_attempts": step.max_attempts,
                }
                for step in compiled.steps
            ],
            "input": compiled.input,
        }

    def _record(
        self,
        uow: ExecutionUnitOfWork,
        run: ExecutionRun,
        action: str,
        event_type: str,
        *,
        resource_type: str = "execution_run",
        resource_id: UUID | None = None,
        payload: dict[str, JsonValue] | None = None,
    ) -> None:
        occurred_at = self._clock.now()
        record_id = resource_id or run.id
        safe_payload = payload or {"run_id": str(run.id), "status": run.status.value}
        if run.reconciliation_state is not ReconciliationState.NOT_REQUIRED:
            safe_payload["reconciliation_state"] = run.reconciliation_state.value
        audit_id = self._id()
        event_id = self._id()
        uow.audit_evidence.append(
            run.workspace_id,
            AuditEvidence(
                id=audit_id,
                workspace_id=run.workspace_id,
                actor=run.actor,
                action=action,
                resource_type=resource_type,
                resource_id=str(record_id),
                outcome=AuditOutcome.SUCCEEDED,
                correlation_id=run.correlation_id,
                causation_id=run.causation_id,
                occurred_at=occurred_at,
                after=safe_payload,
            ),
        )
        uow.outbox.add(
            run.workspace_id,
            IntegrationEvent(
                event_id=event_id,
                event_type=event_type,
                event_version=1,
                schema_version=1,
                occurred_at=occurred_at,
                workspace_id=run.workspace_id,
                actor=run.actor,
                correlation_id=run.correlation_id,
                causation_id=run.causation_id,
                producer="orchestration",
                sensitivity=DataSensitivity.INTERNAL,
                payload=safe_payload,
                idempotency_key=f"{run.id}:{action}:{run.version}",
            ),
        )
