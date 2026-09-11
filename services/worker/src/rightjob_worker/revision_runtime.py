"""Revision-only Temporal launch, reconciliation, validation, and completion."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable, Mapping
from uuid import NAMESPACE_URL, UUID, uuid5

from rightjob.contracts.capabilities import CapabilityCatalog
from rightjob.contracts.departments import DepartmentCatalog
from rightjob.contracts.review import (
    ArtifactReference,
    CapabilityResult,
    ResultProvenance,
    ResultValidationContext,
    ResultValidationOutcome,
    canonical_result_payload,
)
from rightjob.contracts.revision_execution import (
    RevisionArtifactSubmission,
    RevisionCompletionCommand,
    RevisionExecutionClaim,
    RevisionExecutionCommand,
    RevisionExecutionContractError,
    RevisionExecutionStatus,
    RevisionLifecycleCommand,
    RevisionLifecycleReason,
    revision_workflow_id,
)
from rightjob.orchestration.application.revision_execution import DurableRevisionLifecycleService
from rightjob.validation import CapabilityResultValidator
from temporalio.client import Client, WorkflowExecutionStatus, WorkflowFailureError
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode

WORKFLOW_TYPE = "rightjob.revision.regenerate_artifact"
MEMO_KEY = "rightjob_revision_identity"


class RevisionLaunchRejected(RuntimeError):
    """Temporal definitely rejected a launch before execution."""


class RevisionLaunchAmbiguous(RuntimeError):
    """Temporal launch outcome cannot be proven."""


class RevisionWorkflowMismatch(PermissionError):
    """The persisted ID belongs to a different logical claim."""


class RevisionWorkflowExistence(StrEnum):
    MATCHING = "matching"
    ABSENT = "absent"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RevisionWorkflowInspection:
    existence: RevisionWorkflowExistence
    status: WorkflowExecutionStatus | None = None


class TemporalRevisionWorkflow:
    def __init__(self, client: Client, task_queue: str) -> None:
        self._client = client
        self._task_queue = task_queue

    async def start(self, workflow_id: str, request: dict[str, Any]) -> None:
        identity = _identity(request)
        try:
            await self._client.start_workflow(
                WORKFLOW_TYPE,
                request,
                id=workflow_id,
                task_queue=self._task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
                memo={MEMO_KEY: identity},
            )
        except WorkflowAlreadyStartedError:
            inspection = await self.inspect(workflow_id, identity)
            if (
                inspection.existence is RevisionWorkflowExistence.MATCHING
                and inspection.status is WorkflowExecutionStatus.RUNNING
            ):
                return
            if inspection.existence is RevisionWorkflowExistence.MISMATCH:
                raise RevisionWorkflowMismatch("workflow ID belongs to a different claim") from None
            raise RevisionLaunchAmbiguous("workflow conflict could not be reconciled") from None
        except RPCError as error:
            if error.status in {
                RPCStatusCode.INVALID_ARGUMENT,
                RPCStatusCode.PERMISSION_DENIED,
                RPCStatusCode.FAILED_PRECONDITION,
                RPCStatusCode.UNAUTHENTICATED,
            }:
                raise RevisionLaunchRejected("Temporal definitely rejected launch") from error
            raise RevisionLaunchAmbiguous("Temporal launch outcome is unknown") from error
        except Exception as error:
            raise RevisionLaunchAmbiguous("Temporal launch outcome is unknown") from error

    async def inspect(
        self, workflow_id: str, identity: dict[str, Any]
    ) -> RevisionWorkflowInspection:
        try:
            description = await self._client.get_workflow_handle(workflow_id).describe()
            memo = await description.memo()
        except RPCError as error:
            if error.status is RPCStatusCode.NOT_FOUND:
                return RevisionWorkflowInspection(RevisionWorkflowExistence.ABSENT)
            return RevisionWorkflowInspection(RevisionWorkflowExistence.UNKNOWN)
        except Exception:
            return RevisionWorkflowInspection(RevisionWorkflowExistence.UNKNOWN)
        if (
            description.id != workflow_id
            or description.workflow_type != WORKFLOW_TYPE
            or memo.get(MEMO_KEY) != identity
        ):
            return RevisionWorkflowInspection(RevisionWorkflowExistence.MISMATCH)
        return RevisionWorkflowInspection(RevisionWorkflowExistence.MATCHING, description.status)

    async def result(self, workflow_id: str) -> dict[str, Any]:
        value = await self._client.get_workflow_handle(workflow_id).result()
        if type(value) is not dict:
            raise RevisionExecutionContractError("revision workflow result must be an object")
        return value

    async def cancel_and_confirm(
        self, workflow_id: str, identity: dict[str, Any]
    ) -> RevisionWorkflowInspection:
        await self._client.get_workflow_handle(workflow_id).cancel(
            reason="rightjob-revision-cancelled"
        )
        for _ in range(50):
            inspection = await self.inspect(workflow_id, identity)
            if inspection.existence is not RevisionWorkflowExistence.MATCHING:
                return inspection
            if inspection.status is not WorkflowExecutionStatus.RUNNING:
                return inspection
            await asyncio.sleep(0.1)
        return RevisionWorkflowInspection(RevisionWorkflowExistence.UNKNOWN)


class RevisionRuntimeService:
    def __init__(
        self,
        lifecycle: DurableRevisionLifecycleService,
        temporal: TemporalRevisionWorkflow,
        capabilities: CapabilityCatalog,
        departments: DepartmentCatalog,
        validator: CapabilityResultValidator,
        clock: Callable[[], datetime],
    ) -> None:
        self._lifecycle = lifecycle
        self._temporal = temporal
        self._capabilities = capabilities
        self._departments = departments
        self._validator = validator
        self._clock = clock

    async def execute(
        self, command: RevisionExecutionCommand, claim: RevisionExecutionClaim
    ) -> RevisionExecutionClaim:
        running = await self.launch(command, claim)
        if running.status is not RevisionExecutionStatus.RUNNING:
            return running
        return await self.complete(command, running)

    async def complete(
        self, command: RevisionExecutionCommand, running: RevisionExecutionClaim
    ) -> RevisionExecutionClaim:
        running = self._verify(
            command,
            running,
            frozenset(
                {
                    RevisionExecutionStatus.RUNNING,
                    RevisionExecutionStatus.RECONCILIATION_REQUIRED,
                    RevisionExecutionStatus.COMPLETED,
                }
            ),
        )
        if running.status is RevisionExecutionStatus.COMPLETED:
            return running
        try:
            value = await self._temporal.result(running.workflow_id or "")
        except WorkflowFailureError:
            if running.status is RevisionExecutionStatus.RECONCILIATION_REQUIRED:
                return running
            return self._transition(
                command,
                running,
                RevisionExecutionStatus.FAILED,
                RevisionLifecycleReason.EXECUTION_FAILED,
            )
        result = self._result(command, running, value)
        action = command.action
        capability = self._capabilities.get_enabled(
            action.capability.capability_key, action.capability.semantic_version
        )
        validation = self._validator.validate(
            result,
            ResultValidationContext(
                action.workspace_id,
                running.execution_run_id,
                running.execution_step_id,
                action.correlation_id,
                action.causation_id,
                action.capability,
                capability.output_contract,
                result.provenance.artifact,
            ),
        )
        if validation.outcome is not ResultValidationOutcome.PASSED:
            return self._transition(
                command,
                running,
                RevisionExecutionStatus.FAILED,
                RevisionLifecycleReason.VALIDATION_FAILED,
            )
        completed_at = self._clock()
        submission = RevisionArtifactSubmission(
            running.claim_id,
            action.workspace_id,
            action.quality_gate_id,
            running.execution_run_id,
            running.execution_step_id,
            action.capability,
            action.source_artifact,
            result.provenance.artifact,
            validation.validation_id,
            result.provenance.produced_at,
        )
        return self._lifecycle.complete(
            command,
            RevisionCompletionCommand(
                _command_id(running.claim_id, "completed"),
                action.workspace_id,
                running.claim_id,
                running.version,
                running.workflow_id or "",
                submission,
                validation,
                completed_at,
            ),
        )

    async def launch(
        self, command: RevisionExecutionCommand, claim: RevisionExecutionClaim
    ) -> RevisionExecutionClaim:
        self._validate_authority(command, claim)
        workflow_id = revision_workflow_id(command.action)
        pending = self._lifecycle.prepare_launch(
            command,
            RevisionLifecycleCommand(
                _command_id(claim.claim_id, "launch-pending"),
                command.action.workspace_id,
                claim.claim_id,
                claim.version,
                RevisionExecutionStatus.LAUNCH_PENDING,
                workflow_id,
                self._clock(),
            ),
            self._capabilities,
            self._departments,
        )
        request = _request(pending)
        try:
            await self._temporal.start(workflow_id, request)
        except RevisionLaunchRejected:
            return self._transition(
                command,
                pending,
                RevisionExecutionStatus.FAILED,
                RevisionLifecycleReason.LAUNCH_REJECTED,
            )
        except (RevisionLaunchAmbiguous, RevisionWorkflowMismatch):
            return self._transition(
                command,
                pending,
                RevisionExecutionStatus.RECONCILIATION_REQUIRED,
                RevisionLifecycleReason.LAUNCH_OUTCOME_UNKNOWN,
            )
        return self._transition(command, pending, RevisionExecutionStatus.RUNNING)

    async def reconcile(
        self, command: RevisionExecutionCommand, claim: RevisionExecutionClaim
    ) -> RevisionExecutionClaim:
        claim = self._verify(
            command, claim, frozenset({RevisionExecutionStatus.RECONCILIATION_REQUIRED})
        )
        request = _request(claim)
        inspection = await self._temporal.inspect(claim.workflow_id or "", _identity(request))
        if inspection.existence is RevisionWorkflowExistence.MATCHING:
            if inspection.status is WorkflowExecutionStatus.RUNNING:
                return self._transition(command, claim, RevisionExecutionStatus.RUNNING)
            if inspection.status is WorkflowExecutionStatus.COMPLETED:
                return await self.complete(command, claim)
            terminal_states: Mapping[
                WorkflowExecutionStatus,
                tuple[RevisionExecutionStatus, RevisionLifecycleReason],
            ] = {
                WorkflowExecutionStatus.FAILED: (
                    RevisionExecutionStatus.FAILED,
                    RevisionLifecycleReason.WORKFLOW_FAILED,
                ),
                WorkflowExecutionStatus.CANCELED: (
                    RevisionExecutionStatus.CANCELLED,
                    RevisionLifecycleReason.WORKFLOW_CANCELLED,
                ),
                WorkflowExecutionStatus.TERMINATED: (
                    RevisionExecutionStatus.FAILED,
                    RevisionLifecycleReason.WORKFLOW_TERMINATED,
                ),
                WorkflowExecutionStatus.TIMED_OUT: (
                    RevisionExecutionStatus.FAILED,
                    RevisionLifecycleReason.WORKFLOW_TIMED_OUT,
                ),
            }
            terminal = (
                terminal_states.get(inspection.status) if inspection.status is not None else None
            )
            if terminal is None:
                return claim
            return self._transition(command, claim, *terminal)
        if inspection.existence is RevisionWorkflowExistence.MISMATCH:
            raise RevisionWorkflowMismatch("workflow does not bind the exact claim")
        if inspection.existence is RevisionWorkflowExistence.UNKNOWN:
            return claim
        try:
            await self._temporal.start(claim.workflow_id or "", request)
        except RevisionLaunchAmbiguous:
            return claim
        except (RevisionLaunchRejected, RevisionWorkflowMismatch):
            raise
        return self._transition(command, claim, RevisionExecutionStatus.RUNNING)

    async def cancel(
        self, command: RevisionExecutionCommand, claim: RevisionExecutionClaim
    ) -> RevisionExecutionClaim:
        claim = self._verify(
            command,
            claim,
            frozenset({RevisionExecutionStatus.RUNNING, RevisionExecutionStatus.CANCELLED}),
        )
        if claim.status is RevisionExecutionStatus.CANCELLED:
            return claim
        request = _request(claim)
        inspection = await self._temporal.cancel_and_confirm(
            claim.workflow_id or "", _identity(request)
        )
        if (
            inspection.existence is not RevisionWorkflowExistence.MATCHING
            or inspection.status is not WorkflowExecutionStatus.CANCELED
        ):
            return claim
        return self._transition(
            command,
            claim,
            RevisionExecutionStatus.CANCELLED,
            RevisionLifecycleReason.CANCELLED_BY_REQUEST,
        )

    def _verify(
        self,
        command: RevisionExecutionCommand,
        claim: RevisionExecutionClaim,
        statuses: frozenset[RevisionExecutionStatus],
    ) -> RevisionExecutionClaim:
        return self._lifecycle.verify_runtime_authority(
            command, claim, statuses, self._capabilities, self._departments
        )

    def _validate_authority(
        self, command: RevisionExecutionCommand, claim: RevisionExecutionClaim
    ) -> None:
        if claim.command != command or claim.status is not RevisionExecutionStatus.CLAIMED:
            raise RevisionExecutionContractError("exact durable CLAIMED authority is required")
        action = command.action
        capability = self._capabilities.get_enabled(
            action.capability.capability_key, action.capability.semantic_version
        )
        department = self._departments.get_enabled(
            action.department.department_key, action.department.semantic_version
        )
        if (
            capability.reference != action.capability
            or department.reference != action.department
            or action.capability not in department.capability_references
            or action.target_artifact_id != action.source_artifact.artifact_id
            or action.target_artifact_version != action.source_artifact.version + 1
        ):
            raise RevisionExecutionContractError("revision runtime authority is stale")

    def _transition(
        self,
        command: RevisionExecutionCommand,
        claim: RevisionExecutionClaim,
        target: RevisionExecutionStatus,
        reason: RevisionLifecycleReason | None = None,
    ) -> RevisionExecutionClaim:
        return self._lifecycle.transition(
            command,
            RevisionLifecycleCommand(
                _command_id(claim.claim_id, target.value),
                command.action.workspace_id,
                claim.claim_id,
                claim.version,
                target,
                claim.workflow_id or revision_workflow_id(command.action),
                self._clock(),
                reason,
            ),
        )

    def _result(
        self,
        command: RevisionExecutionCommand,
        claim: RevisionExecutionClaim,
        value: dict[str, Any],
    ) -> CapabilityResult:
        expected = _request(claim)
        if any(value.get(key) != item for key, item in expected.items()):
            raise RevisionExecutionContractError("workflow result provenance does not match claim")
        payload = canonical_result_payload(json_value(value.get("payload_json")))
        artifact = ArtifactReference(
            command.action.target_artifact_id,
            command.action.target_artifact_version,
            str(value.get("sha256")),
        )
        capability = self._capabilities.get_enabled(
            command.action.capability.capability_key,
            command.action.capability.semantic_version,
        )
        return CapabilityResult(
            ResultProvenance(
                command.action.workspace_id,
                claim.execution_run_id,
                claim.execution_step_id,
                command.action.correlation_id,
                command.action.causation_id,
                command.action.capability,
                capability.output_contract,
                artifact,
                self._clock(),
            ),
            payload,
        )


def _request(claim: RevisionExecutionClaim) -> dict[str, Any]:
    action = claim.command.action
    return {
        "action_type": action.action_type.value,
        "claim_id": str(claim.claim_id),
        "workspace_id": str(action.workspace_id),
        "quality_gate_id": str(action.quality_gate_id),
        "quality_decision_id": str(action.quality_decision_id),
        "cycle": action.reserved_cycle,
        "run_id": str(claim.execution_run_id),
        "step_id": str(claim.execution_step_id),
        "correlation_id": str(action.correlation_id),
        "causation_id": str(action.causation_id) if action.causation_id else None,
        "capability_id": str(action.capability.capability_definition_id),
        "capability_key": action.capability.capability_key,
        "capability_version": str(action.capability.semantic_version),
        "artifact_id": str(action.source_artifact.artifact_id),
        "source_version": action.source_artifact.version,
        "source_sha256": action.source_artifact.sha256,
        "target_version": action.target_artifact_version,
        "workflow_id": claim.workflow_id or revision_workflow_id(action),
        "request_id": str(claim.execution_request_id),
        "department_id": str(action.department.department_definition_id),
        "department_key": action.department.department_key,
        "department_version": str(action.department.semantic_version),
        "quality_policy_key": action.quality_policy_key,
        "quality_policy_version": str(action.quality_policy_version),
        "action_digest": claim.action_digest,
        "authorization_id": str(claim.command.authorization.authorization_evidence_id),
        "approval_request_id": (
            str(claim.command.authorization.approval_request_id)
            if claim.command.authorization.approval_request_id
            else None
        ),
        "approval_decision_id": (
            str(claim.command.authorization.approval_decision_id)
            if claim.command.authorization.approval_decision_id
            else None
        ),
        "expected_gate_version": claim.command.expected_quality_gate_state_version,
    }


def _identity(request: dict[str, Any]) -> dict[str, Any]:
    return dict(request)


def _command_id(claim_id: UUID, operation: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"rightjob:revision-runtime:{claim_id}:{operation}")


def json_value(value: object) -> Any:
    if type(value) is not str:
        raise RevisionExecutionContractError("workflow payload must be canonical JSON text")
    return json.loads(value)
