"""Durable Policy evidence and exact-plan authorization semantics."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from uuid import UUID

from rightjob.contracts.approval import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRequest,
    ApprovalStatus,
)
from rightjob.contracts.authorization import (
    AuthorizationError,
    AuthorizationEvidence,
    AuthorizedWorkflow,
    ExecutionAuthorization,
    ExecutionAuthorizationStep,
    action_digest,
    action_snapshot,
    reject_deny,
    require_evidence_current,
)
from rightjob.contracts.capabilities import CapabilityCatalog
from rightjob.contracts.departments import DepartmentCatalog
from rightjob.contracts.events import JsonValue
from rightjob.contracts.planning import ExecutionPlan
from rightjob.contracts.policy import (
    MembershipFacts,
    PolicyDecision,
    PolicyEvaluation,
    PolicySetReference,
)


class DurableAuthorizationService:
    def __init__(
        self,
        capabilities: CapabilityCatalog,
        departments: DepartmentCatalog,
        current_policy_set: PolicySetReference,
        id_factory: Callable[[], UUID],
    ) -> None:
        self._capabilities = capabilities
        self._departments = departments
        self._policy_set = current_policy_set
        self._id = id_factory

    def record_evidence(
        self, plan: ExecutionPlan, evaluation: PolicyEvaluation
    ) -> AuthorizationEvidence:
        step = next(
            (item for item in plan.steps if item.step_id == evaluation.action.step_id), None
        )
        if step is None or evaluation.context.workspace_id != plan.workspace_id:
            raise AuthorizationError("Policy evaluation does not belong to plan")
        if evaluation.policy_set != self._policy_set:
            raise AuthorizationError("Policy reference is stale")
        try:
            department = self._departments.get_enabled(
                step.department.department_key, step.department.semantic_version
            )
            capability = self._capabilities.get_enabled(
                step.capability.capability_key, step.capability.semantic_version
            )
        except LookupError as error:
            raise AuthorizationError("Department or Capability reference is stale") from error
        if department.reference != step.department or capability.reference != step.capability:
            raise AuthorizationError("definition identity is stale")
        if step.capability not in department.capability_references:
            raise AuthorizationError("Capability no longer belongs to Department")
        if capability.effect_classification is not step.effect_classification:
            raise AuthorizationError("Capability effect metadata is stale")
        snapshot = action_snapshot(plan, step, evaluation)
        return AuthorizationEvidence(self._id(), evaluation, snapshot, action_digest(snapshot))

    def issue(
        self,
        plan: ExecutionPlan,
        workflow: AuthorizedWorkflow,
        evidence_by_step: Mapping[UUID, AuthorizationEvidence],
        approvals_by_step: Mapping[UUID, tuple[ApprovalRequest, ApprovalDecision]],
        current_subject_by_step: Mapping[UUID, MembershipFacts],
        current_approver_by_step: Mapping[UUID, MembershipFacts],
        issued_at: datetime,
    ) -> ExecutionAuthorization:
        if not workflow.enabled:
            raise AuthorizationError("workflow is disabled")
        if len(plan.steps) != len(workflow.steps):
            raise AuthorizationError("workflow does not match exact plan")
        bindings: list[ExecutionAuthorizationStep] = []
        expiries: list[datetime] = []
        for step, workflow_step in zip(plan.steps, workflow.steps, strict=True):
            if (
                workflow_step.department != step.department
                or workflow_step.capability != step.capability
            ):
                raise AuthorizationError("workflow does not match exact plan")
            evidence = evidence_by_step.get(step.step_id)
            if evidence is None:
                raise AuthorizationError("every plan step requires durable Policy evidence")
            reject_deny(evidence)
            require_evidence_current(evidence, issued_at)
            original_subject = evidence.policy_evaluation.subject.membership
            if (
                original_subject is None
                or current_subject_by_step.get(step.step_id) != original_subject
            ):
                raise AuthorizationError("subject membership authority is stale")
            expected_snapshot = action_snapshot(plan, step, evidence.policy_evaluation)
            if action_digest(expected_snapshot) != evidence.action_digest:
                raise AuthorizationError("action changed after Policy evaluation")
            request_id: UUID | None = None
            decision_id: UUID | None = None
            if evidence.policy_evaluation.decision is PolicyDecision.REQUIRE_APPROVAL:
                approved = approvals_by_step.get(step.step_id)
                if approved is None:
                    raise AuthorizationError("required human approval is unresolved")
                request, decision = approved
                if (
                    request.authorization_evidence_id != evidence.authorization_evidence_id
                    or request.status is not ApprovalStatus.APPROVED
                    or request.action_digest != evidence.action_digest
                    or decision.outcome is not ApprovalOutcome.APPROVED
                    or decision.approval_request_id != request.approval_request_id
                    or decision.action_digest != evidence.action_digest
                ):
                    raise AuthorizationError("approval does not authorize exact evidence")
                if issued_at >= request.expires_at:
                    raise AuthorizationError("approval request has expired")
                if current_approver_by_step.get(step.step_id) != decision.membership:
                    raise AuthorizationError("approver membership authority is stale")
                request_id, decision_id = request.approval_request_id, decision.approval_decision_id
            elif step.step_id in approvals_by_step:
                raise AuthorizationError("ALLOW must not fabricate human approval")
            bindings.append(
                ExecutionAuthorizationStep(
                    self._id(),
                    step.step_id,
                    step.sequence,
                    evidence.action_digest,
                    evidence.authorization_evidence_id,
                    request_id,
                    decision_id,
                )
            )
            expiries.append(evidence.expires_at)
        manifest: dict[str, JsonValue] = {
            "schema_version": 1,
            "workspace_id": str(plan.workspace_id),
            "planning_request_id": str(plan.planning_request_id),
            "plan_id": str(plan.plan_id),
            "workflow": {
                "id": str(workflow.workflow_definition_id),
                "type": workflow.workflow_type,
                "version": workflow.workflow_version,
            },
            "steps": [
                {
                    "id": str(item.step_id),
                    "sequence": item.sequence,
                    "action_digest": item.action_digest,
                }
                for item in bindings
            ],
        }
        return ExecutionAuthorization(
            self._id(),
            plan.workspace_id,
            plan.planning_request_id,
            plan.plan_id,
            workflow.workflow_definition_id,
            workflow.workflow_type,
            workflow.workflow_version,
            action_digest(manifest),
            tuple(bindings),
            issued_at,
            min(expiries),
            plan.correlation_id,
            plan.causation_id,
        )
