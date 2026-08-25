from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from rightjob.audit.infrastructure.models import AuditEntryRecord, OutboxEventRecord
from rightjob.audit.infrastructure.repositories import (
    SqlAlchemyAuditEvidenceRepository,
    SqlAlchemyOutboxRepository,
)
from rightjob.contracts.approval import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRequest,
    ApprovalStatus,
    decide_request,
)
from rightjob.contracts.authorization import (
    AuthorizationError,
    AuthorizedWorkflow,
    AuthorizedWorkflowStep,
)
from rightjob.contracts.capabilities import ContractReference, EffectClassification
from rightjob.contracts.departments import WorkCategory
from rightjob.contracts.events import Actor, ActorType
from rightjob.contracts.planning import (
    ExecutionPlan,
    PlannerIdentity,
    PlanStep,
    StructuredInput,
    SyntheticStepObjective,
)
from rightjob.contracts.policy import (
    MembershipFacts,
    PolicyAction,
    PolicyContext,
    PolicyDecision,
    PolicyEvaluation,
    PolicyOperation,
    PolicySubject,
)
from rightjob.database import register_sqlalchemy_mappings
from rightjob.orchestration.infrastructure.models import ExecutionRequestRecord
from rightjob.policy.application import GovernanceRecorder
from rightjob.policy.authorization import DurableAuthorizationService
from rightjob.policy.evaluator import SYNTHETIC_POLICY_SET, SyntheticPolicyEvaluator
from rightjob.policy.infrastructure.models import (
    ApprovalDecisionRecord,
    ApprovalRequestRecord,
    AuthorizationEvidenceRecord,
    ExecutionAuthorizationRecord,
    ExecutionAuthorizationStepRecord,
)
from rightjob.policy.infrastructure.repositories import SqlAlchemyApprovalRequestRepository
from rightjob.policy.infrastructure.unit_of_work import SqlAlchemyPolicyApprovalUnitOfWork
from rightjob.policy.repositories import ConcurrentApprovalUpdateError, IdempotencyConflictError
from rightjob.registry import (
    BUILT_IN_CAPABILITIES,
    BUILT_IN_DEPARTMENTS,
    BuiltInCapabilityRegistry,
    BuiltInDepartmentRegistry,
)
from sqlalchemy import create_engine, delete, func, insert, select, text, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

OWNER_URL = os.environ.get("RIGHTJOB_DATABASE_URL")
APP_URL = os.environ.get("RIGHTJOB_PHASE212_RLS_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not OWNER_URL or not APP_URL,
        reason="explicit Phase 2.12 owner and verifier database URLs required",
    ),
]

APP_ROLE = "rightjob_phase212_rls_verifier"
REVISION = "20260812_0004"
NOW = datetime(2026, 8, 13, 8, tzinfo=timezone.utc)
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64

# Owner-approved Phase 2.12 PostgreSQL fixture inventory. No generated UUIDs are allowed.
WORKSPACE_A = UUID("21200000-0000-4000-8000-000000000001")
WORKSPACE_B = UUID("21200000-0000-4000-8000-000000000002")
OWNER_USER_A = UUID("21200000-0000-4000-8000-000000000011")
ADMIN_USER_A = UUID("21200000-0000-4000-8000-000000000012")
MEMBER_USER_A = UUID("21200000-0000-4000-8000-000000000013")
INACTIVE_OWNER_USER_A = UUID("21200000-0000-4000-8000-000000000014")
INACTIVE_ADMIN_USER_A = UUID("21200000-0000-4000-8000-000000000015")
OWNER_USER_B = UUID("21200000-0000-4000-8000-000000000016")
OWNER_MEMBERSHIP_A = UUID("21200000-0000-4000-8000-000000000021")
ADMIN_MEMBERSHIP_A = UUID("21200000-0000-4000-8000-000000000022")
MEMBER_MEMBERSHIP_A = UUID("21200000-0000-4000-8000-000000000023")
INACTIVE_OWNER_MEMBERSHIP_A = UUID("21200000-0000-4000-8000-000000000024")
INACTIVE_ADMIN_MEMBERSHIP_A = UUID("21200000-0000-4000-8000-000000000025")
OWNER_MEMBERSHIP_B = UUID("21200000-0000-4000-8000-000000000026")

PLANNING_REQUEST_A = UUID("21200000-0000-4000-8000-000000000031")
PLANNING_REQUEST_B = UUID("21200000-0000-4000-8000-000000000032")
ALLOW_PLAN = UUID("21200000-0000-4000-8000-000000000041")
APPROVAL_PLAN = UUID("21200000-0000-4000-8000-000000000042")
DENY_PLAN = UUID("21200000-0000-4000-8000-000000000043")
MIXED_PLAN = UUID("21200000-0000-4000-8000-000000000044")
EQUAL_DIGEST_PLAN_A = UUID("21200000-0000-4000-8000-000000000045")
EQUAL_DIGEST_PLAN_B = UUID("21200000-0000-4000-8000-000000000046")
ROLLBACK_PLAN = UUID("21200000-0000-4000-8000-000000000047")

PLAN_STEPS = tuple(
    UUID(value)
    for value in (
        "21200000-0000-4000-8000-000000000051",
        "21200000-0000-4000-8000-000000000052",
        "21200000-0000-4000-8000-000000000053",
        "21200000-0000-4000-8000-000000000054",
        "21200000-0000-4000-8000-000000000055",
        "21200000-0000-4000-8000-000000000056",
        "21200000-0000-4000-8000-000000000057",
        "21200000-0000-4000-8000-000000000058",
        "21200000-0000-4000-8000-000000000059",
        "21200000-0000-4000-8000-000000000060",
        "21200000-0000-4000-8000-000000000061",
        "21200000-0000-4000-8000-000000000062",
    )
)
POLICY_EVALUATIONS = tuple(
    UUID(value)
    for value in (
        "21200000-0000-4000-8000-000000000101",
        "21200000-0000-4000-8000-000000000102",
        "21200000-0000-4000-8000-000000000103",
        "21200000-0000-4000-8000-000000000104",
        "21200000-0000-4000-8000-000000000105",
        "21200000-0000-4000-8000-000000000106",
        "21200000-0000-4000-8000-000000000107",
        "21200000-0000-4000-8000-000000000108",
        "21200000-0000-4000-8000-000000000109",
        "21200000-0000-4000-8000-000000000110",
        "21200000-0000-4000-8000-000000000111",
        "21200000-0000-4000-8000-000000000112",
    )
)
EVIDENCE_IDS = tuple(
    UUID(value)
    for value in (
        "21200000-0000-4000-8000-000000000201",
        "21200000-0000-4000-8000-000000000202",
        "21200000-0000-4000-8000-000000000203",
        "21200000-0000-4000-8000-000000000204",
        "21200000-0000-4000-8000-000000000205",
        "21200000-0000-4000-8000-000000000206",
        "21200000-0000-4000-8000-000000000207",
        "21200000-0000-4000-8000-000000000208",
        "21200000-0000-4000-8000-000000000209",
        "21200000-0000-4000-8000-000000000210",
        "21200000-0000-4000-8000-000000000211",
        "21200000-0000-4000-8000-000000000212",
    )
)
APPROVAL_REQUEST_IDS = tuple(
    UUID(value)
    for value in (
        "21200000-0000-4000-8000-000000000301",
        "21200000-0000-4000-8000-000000000302",
        "21200000-0000-4000-8000-000000000303",
        "21200000-0000-4000-8000-000000000304",
        "21200000-0000-4000-8000-000000000305",
        "21200000-0000-4000-8000-000000000306",
        "21200000-0000-4000-8000-000000000307",
        "21200000-0000-4000-8000-000000000308",
    )
)
APPROVAL_DECISION_IDS = tuple(
    UUID(value)
    for value in (
        "21200000-0000-4000-8000-000000000401",
        "21200000-0000-4000-8000-000000000402",
        "21200000-0000-4000-8000-000000000403",
        "21200000-0000-4000-8000-000000000404",
        "21200000-0000-4000-8000-000000000405",
        "21200000-0000-4000-8000-000000000406",
        "21200000-0000-4000-8000-000000000407",
        "21200000-0000-4000-8000-000000000408",
    )
)
EXECUTION_AUTHORIZATION_IDS = tuple(
    UUID(value)
    for value in (
        "21200000-0000-4000-8000-000000000501",
        "21200000-0000-4000-8000-000000000502",
        "21200000-0000-4000-8000-000000000503",
        "21200000-0000-4000-8000-000000000504",
        "21200000-0000-4000-8000-000000000505",
    )
)
EXECUTION_AUTHORIZATION_STEP_IDS = tuple(
    UUID(value)
    for value in (
        "21200000-0000-4000-8000-000000000601",
        "21200000-0000-4000-8000-000000000602",
        "21200000-0000-4000-8000-000000000603",
        "21200000-0000-4000-8000-000000000604",
        "21200000-0000-4000-8000-000000000605",
        "21200000-0000-4000-8000-000000000606",
        "21200000-0000-4000-8000-000000000607",
        "21200000-0000-4000-8000-000000000608",
        "21200000-0000-4000-8000-000000000609",
        "21200000-0000-4000-8000-000000000610",
    )
)
EXECUTION_REQUEST_A = UUID("21200000-0000-4000-8000-000000000701")
DUPLICATE_EXECUTION_REQUEST = UUID("21200000-0000-4000-8000-000000000702")
ROLLBACK_EXECUTION_REQUEST = UUID("21200000-0000-4000-8000-000000000703")
EXECUTION_RUN_A = UUID("21200000-0000-4000-8000-000000000801")
DUPLICATE_EXECUTION_RUN = UUID("21200000-0000-4000-8000-000000000802")
EXECUTION_STEP_IDS = tuple(
    UUID(value)
    for value in (
        "21200000-0000-4000-8000-000000000811",
        "21200000-0000-4000-8000-000000000812",
        "21200000-0000-4000-8000-000000000813",
        "21200000-0000-4000-8000-000000000814",
    )
)
AUDIT_IDS = tuple(
    UUID(value)
    for value in (
        "21200000-0000-4000-8000-000000000901",
        "21200000-0000-4000-8000-000000000902",
        "21200000-0000-4000-8000-000000000903",
        "21200000-0000-4000-8000-000000000904",
        "21200000-0000-4000-8000-000000000905",
        "21200000-0000-4000-8000-000000000906",
        "21200000-0000-4000-8000-000000000907",
        "21200000-0000-4000-8000-000000000908",
        "21200000-0000-4000-8000-000000000909",
        "21200000-0000-4000-8000-000000000910",
    )
)
OUTBOX_IDS = tuple(
    UUID(value)
    for value in (
        "21200000-0000-4000-8000-000000000a01",
        "21200000-0000-4000-8000-000000000a02",
        "21200000-0000-4000-8000-000000000a03",
        "21200000-0000-4000-8000-000000000a04",
        "21200000-0000-4000-8000-000000000a05",
        "21200000-0000-4000-8000-000000000a06",
        "21200000-0000-4000-8000-000000000a07",
        "21200000-0000-4000-8000-000000000a08",
        "21200000-0000-4000-8000-000000000a09",
        "21200000-0000-4000-8000-000000000a10",
    )
)
WORKFLOW_DEFINITION = UUID("21200000-0000-4000-8000-000000000b01")
CORRELATION_A = UUID("21200000-0000-4000-8000-000000000c01")
CAUSATION_A = UUID("21200000-0000-4000-8000-000000000c02")
CORRELATION_B = UUID("21200000-0000-4000-8000-000000000c03")
CAUSATION_B = UUID("21200000-0000-4000-8000-000000000c04")

IDENTITY_IDS = (
    WORKSPACE_A,
    WORKSPACE_B,
    OWNER_USER_A,
    ADMIN_USER_A,
    MEMBER_USER_A,
    INACTIVE_OWNER_USER_A,
    INACTIVE_ADMIN_USER_A,
    OWNER_USER_B,
    OWNER_MEMBERSHIP_A,
    ADMIN_MEMBERSHIP_A,
    MEMBER_MEMBERSHIP_A,
    INACTIVE_OWNER_MEMBERSHIP_A,
    INACTIVE_ADMIN_MEMBERSHIP_A,
    OWNER_MEMBERSHIP_B,
)
ALL_APPROVED_IDS = (
    *IDENTITY_IDS,
    PLANNING_REQUEST_A,
    PLANNING_REQUEST_B,
    ALLOW_PLAN,
    APPROVAL_PLAN,
    DENY_PLAN,
    MIXED_PLAN,
    EQUAL_DIGEST_PLAN_A,
    EQUAL_DIGEST_PLAN_B,
    ROLLBACK_PLAN,
    *PLAN_STEPS,
    *POLICY_EVALUATIONS,
    *EVIDENCE_IDS,
    *APPROVAL_REQUEST_IDS,
    *APPROVAL_DECISION_IDS,
    *EXECUTION_AUTHORIZATION_IDS,
    *EXECUTION_AUTHORIZATION_STEP_IDS,
    EXECUTION_REQUEST_A,
    DUPLICATE_EXECUTION_REQUEST,
    ROLLBACK_EXECUTION_REQUEST,
    EXECUTION_RUN_A,
    DUPLICATE_EXECUTION_RUN,
    *EXECUTION_STEP_IDS,
    *AUDIT_IDS,
    *OUTBOX_IDS,
    WORKFLOW_DEFINITION,
    CORRELATION_A,
    CAUSATION_A,
    CORRELATION_B,
    CAUSATION_B,
)

APPLICATION_TABLES = (
    "workspaces",
    "users",
    "memberships",
    "audit_entries",
    "outbox_events",
    "execution_requests",
    "execution_runs",
    "execution_steps",
    "authorization_evidence",
    "approval_requests",
    "approval_decisions",
    "execution_authorizations",
    "execution_authorization_steps",
)
GOVERNANCE_TABLES = (
    "authorization_evidence",
    "approval_requests",
    "approval_decisions",
    "execution_authorizations",
    "execution_authorization_steps",
)


class FixedIds:
    def __init__(self, values: tuple[UUID, ...]) -> None:
        self._values = iter(values)

    def __call__(self) -> UUID:
        return next(self._values)


def _membership(
    user_id: UUID,
    membership_id: UUID,
    role: str,
    *,
    workspace_id: UUID = WORKSPACE_A,
    active: bool = True,
    version: int = 1,
) -> MembershipFacts:
    return MembershipFacts(
        membership_id,
        user_id,
        workspace_id,
        active,
        (role,),
        (),
        version,
    )


def _domain_plan(
    plan_id: UUID,
    steps: tuple[tuple[UUID, int, EffectClassification], ...],
) -> tuple[ExecutionPlan, BuiltInCapabilityRegistry, BuiltInDepartmentRegistry]:
    definitions = list(BUILT_IN_CAPABILITIES)
    if any(effect is EffectClassification.CONSEQUENTIAL for _, _, effect in steps):
        definitions[1] = replace(
            definitions[1], effect_classification=EffectClassification.CONSEQUENTIAL
        )
    capabilities = BuiltInCapabilityRegistry(tuple(definitions))
    departments = BuiltInDepartmentRegistry(capabilities, BUILT_IN_DEPARTMENTS)
    plan_steps: list[PlanStep] = []
    for step_id, sequence, effect in steps:
        if effect is EffectClassification.CONSEQUENTIAL:
            capability = capabilities.get_enabled("fake.transform", definitions[1].semantic_version)
            department = departments.get_enabled(
                "foundation.content", BUILT_IN_DEPARTMENTS[1].semantic_version
            )
            objective, category = SyntheticStepObjective.TRANSFORM, WorkCategory.TRANSFORM
        else:
            capability = capabilities.get_enabled("fake.prepare", definitions[0].semantic_version)
            department = departments.get_enabled(
                "foundation.operations", BUILT_IN_DEPARTMENTS[0].semantic_version
            )
            objective, category = SyntheticStepObjective.PREPARE, WorkCategory.PREPARE
        plan_steps.append(
            PlanStep(
                step_id,
                sequence,
                objective,
                category,
                department.reference,
                capability.reference,
                StructuredInput((("value", f"fixture-{sequence}"),)),
                () if sequence == 0 else (steps[sequence - 1][0],),
                ContractReference(
                    f"{capability.capability_key}.output", capability.semantic_version, 4096
                ),
                effect,
            )
        )
    return (
        ExecutionPlan(
            plan_id,
            WORKSPACE_A,
            PLANNING_REQUEST_A,
            CORRELATION_A,
            CAUSATION_A,
            PlannerIdentity("synthetic.planner", definitions[0].semantic_version),
            definitions[0].semantic_version,
            tuple(plan_steps),
            NOW,
        ),
        capabilities,
        departments,
    )


def _evaluate_plan(
    plan: ExecutionPlan,
    capabilities: BuiltInCapabilityRegistry,
    departments: BuiltInDepartmentRegistry,
    evaluation_ids: tuple[UUID, ...],
) -> tuple[PolicyEvaluation, ...]:
    subject = PolicySubject(
        Actor(ActorType.USER, str(OWNER_USER_A)),
        WORKSPACE_A,
        _membership(OWNER_USER_A, OWNER_MEMBERSHIP_A, "owner"),
    )
    context = PolicyContext(
        WORKSPACE_A,
        CORRELATION_A,
        CAUSATION_A,
        PLANNING_REQUEST_A,
        plan.plan_id,
    )
    evaluator = SyntheticPolicyEvaluator(
        capabilities,
        departments,
        FixedIds(evaluation_ids),
        lambda: NOW,
    )
    return tuple(
        evaluator.evaluate(
            subject,
            PolicyAction(
                PolicyOperation.EXECUTE_CAPABILITY,
                plan.plan_id,
                step.step_id,
                step.department,
                step.capability,
                step.work_category,
                step.effect_classification,
            ),
            context,
        )
        for step in plan.steps
    )


def _scope(connection: Connection, workspace_id: UUID) -> None:
    connection.execute(
        text("SELECT set_config('app.current_workspace_id', :workspace, true)"),
        {"workspace": str(workspace_id)},
    )


def _evidence_values(
    evidence_id: UUID,
    evaluation_id: UUID,
    plan_id: UUID,
    step_id: UUID,
    decision: str,
    *,
    workspace_id: UUID = WORKSPACE_A,
    planning_request_id: UUID = PLANNING_REQUEST_A,
    digest: str = DIGEST_A,
    expires_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "id": evidence_id,
        "workspace_id": workspace_id,
        "policy_evaluation_id": evaluation_id,
        "planning_request_id": planning_request_id,
        "plan_id": plan_id,
        "step_id": step_id,
        "subject_actor_type": "user",
        "subject_actor_id": str(OWNER_USER_A if workspace_id == WORKSPACE_A else OWNER_USER_B),
        "subject_user_id": OWNER_USER_A if workspace_id == WORKSPACE_A else OWNER_USER_B,
        "subject_membership_id": (
            OWNER_MEMBERSHIP_A if workspace_id == WORKSPACE_A else OWNER_MEMBERSHIP_B
        ),
        "subject_membership_version": 1,
        "subject_membership_active": True,
        "subject_roles_json": ["owner"],
        "subject_permissions_json": [],
        "operation": "execute_capability",
        "department_definition_id": WORKFLOW_DEFINITION,
        "department_key": "foundation.operations",
        "department_version": "1.0.0",
        "capability_definition_id": WORKFLOW_DEFINITION,
        "capability_key": "fake.prepare",
        "capability_version": "1.0.0",
        "work_category": "prepare",
        "effect_classification": (
            "consequential" if decision == "require_approval" else "read_only"
        ),
        "action_snapshot_json": {"schema_version": 1, "fixture": str(evidence_id)},
        "action_digest": digest,
        "digest_algorithm": "sha256",
        "snapshot_schema_version": 1,
        "policy_decision": decision,
        "reason_codes_json": ["synthetic_fixture"],
        "policy_set_id": WORKFLOW_DEFINITION,
        "policy_set_key": "synthetic.foundation.policy",
        "policy_set_version": "1.0.0",
        "matched_rules_json": [{"key": "synthetic.effect", "version": "1.0.0"}],
        "evaluated_at": NOW,
        "expires_at": expires_at or NOW + timedelta(minutes=5),
        "correlation_id": CORRELATION_A if workspace_id == WORKSPACE_A else CORRELATION_B,
        "causation_id": CAUSATION_A if workspace_id == WORKSPACE_A else CAUSATION_B,
    }


def _request_values(
    request_id: UUID,
    evidence: dict[str, object],
    *,
    idempotency: str,
    status: str = "pending",
    version: int = 1,
    resolved_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "id": request_id,
        "workspace_id": evidence["workspace_id"],
        "authorization_evidence_id": evidence["id"],
        "planning_request_id": evidence["planning_request_id"],
        "plan_id": evidence["plan_id"],
        "step_id": evidence["step_id"],
        "action_digest": evidence["action_digest"],
        "requester_actor_type": "user",
        "requester_actor_id": evidence["subject_actor_id"],
        "status": status,
        "requested_at": NOW + timedelta(seconds=1),
        "expires_at": evidence["expires_at"],
        "resolved_at": resolved_at,
        "correlation_id": evidence["correlation_id"],
        "causation_id": evidence["causation_id"],
        "idempotency_key": idempotency,
        "version": version,
    }


def _decision_values(
    decision_id: UUID,
    request: dict[str, object],
    *,
    outcome: str = "approved",
    user_id: UUID = OWNER_USER_A,
    membership_id: UUID = OWNER_MEMBERSHIP_A,
    role: str = "owner",
    idempotency: str,
) -> dict[str, object]:
    return {
        "id": decision_id,
        "workspace_id": request["workspace_id"],
        "approval_request_id": request["id"],
        "action_digest": request["action_digest"],
        "outcome": outcome,
        "approver_actor_type": "user",
        "approver_actor_id": str(user_id),
        "approver_user_id": user_id,
        "approver_membership_id": membership_id,
        "approver_membership_version": 1,
        "approver_roles_json": [role],
        "approver_permissions_json": [],
        "authority_rule_key": "synthetic.owner_admin",
        "authority_rule_version": "1.0.0",
        "decided_at": NOW + timedelta(seconds=2),
        "correlation_id": request["correlation_id"],
        "causation_id": request["causation_id"],
        "idempotency_key": idempotency,
    }


def _authorization_values(
    authorization_id: UUID,
    plan_id: UUID,
    *,
    workspace_id: UUID = WORKSPACE_A,
    idempotency: str,
    expires_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "id": authorization_id,
        "workspace_id": workspace_id,
        "planning_request_id": (
            PLANNING_REQUEST_A if workspace_id == WORKSPACE_A else PLANNING_REQUEST_B
        ),
        "plan_id": plan_id,
        "workflow_definition_id": WORKFLOW_DEFINITION,
        "workflow_type": "synthetic.foundation",
        "workflow_version": "1.0.0",
        "plan_digest": DIGEST_B,
        "digest_algorithm": "sha256",
        "authorization_version": 1,
        "issued_at": NOW + timedelta(seconds=3),
        "expires_at": expires_at or NOW + timedelta(minutes=5),
        "correlation_id": CORRELATION_A if workspace_id == WORKSPACE_A else CORRELATION_B,
        "causation_id": CAUSATION_A if workspace_id == WORKSPACE_A else CAUSATION_B,
        "idempotency_key": idempotency,
    }


def _audit_values(audit_id: UUID, workspace_id: UUID, resource_id: UUID) -> dict[str, object]:
    return {
        "id": audit_id,
        "workspace_id": workspace_id,
        "actor_type": "user",
        "actor_id": str(OWNER_USER_A),
        "action": "policy.authorization_evidence.recorded",
        "resource_type": "authorization_evidence",
        "resource_id": str(resource_id),
        "outcome": "succeeded",
        "correlation_id": CORRELATION_A,
        "causation_id": CAUSATION_A,
        "policy_ref": "synthetic.foundation.policy@1.0.0",
        "approval_ref": None,
        "before_json": None,
        "after_json": {"fixture": True},
        "evidence_ref": str(resource_id),
        "sensitivity": "internal",
        "occurred_at": NOW,
        "created_at": NOW,
    }


def _outbox_values(event_id: UUID, workspace_id: UUID, resource_id: UUID) -> dict[str, object]:
    return {
        "id": event_id,
        "workspace_id": workspace_id,
        "event_type": "policy.authorization_evidence.recorded.v1",
        "event_version": 1,
        "schema_version": 1,
        "occurred_at": NOW,
        "actor_type": "user",
        "actor_id": str(OWNER_USER_A),
        "correlation_id": CORRELATION_A,
        "causation_id": CAUSATION_A,
        "producer": "rightjob.policy",
        "sensitivity": "internal",
        "payload_json": {"resource_id": str(resource_id)},
        "idempotency_key": f"policy-evidence:{resource_id}",
        "published_at": None,
        "attempts": 0,
        "created_at": NOW,
    }


def _assert_pristine(connection: Connection) -> None:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == REVISION
    counts = tuple(
        connection.scalar(text(f"SELECT count(*) FROM {table}")) for table in APPLICATION_TABLES
    )
    assert counts == (0,) * len(APPLICATION_TABLES)
    assert not connection.scalar(
        text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:role)"),
        {"role": APP_ROLE},
    )
    assert (
        connection.scalar(
            text(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind IN ('r','p')"
            )
        )
        == 14
    )
    assert (
        connection.scalar(
            text("SELECT count(*) FROM pg_constraint WHERE connamespace='public'::regnamespace")
        )
        == 129
    )
    assert (
        connection.scalar(text("SELECT count(*) FROM pg_indexes WHERE schemaname='public'")) == 62
    )
    assert (
        connection.scalar(
            text(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity "
                "AND c.relforcerowsecurity"
            )
        )
        == 11
    )
    assert (
        connection.scalar(
            text("SELECT count(*) FROM pg_policies WHERE schemaname='public' AND cmd='ALL'")
        )
        == 11
    )


def _insert_identity(connection: Connection) -> None:
    connection.execute(
        text(
            "INSERT INTO workspaces "
            "(id,name,slug,status,timezone,locale,settings,created_at,updated_at,version) VALUES "
            "(:a,'Phase 212 A','phase-212-a','active','UTC','en','{}',:now,:now,1),"
            "(:b,'Phase 212 B','phase-212-b','active','UTC','en','{}',:now,:now,1)"
        ),
        {"a": WORKSPACE_A, "b": WORKSPACE_B, "now": NOW},
    )
    users = (
        (OWNER_USER_A, "owner-a", "owner-a@example.test", "Owner A", "active"),
        (ADMIN_USER_A, "admin-a", "admin-a@example.test", "Admin A", "active"),
        (MEMBER_USER_A, "member-a", "member-a@example.test", "Member A", "active"),
        (
            INACTIVE_OWNER_USER_A,
            "inactive-owner-a",
            "inactive-owner-a@example.test",
            "Inactive Owner A",
            "active",
        ),
        (
            INACTIVE_ADMIN_USER_A,
            "inactive-admin-a",
            "inactive-admin-a@example.test",
            "Inactive Admin A",
            "active",
        ),
        (OWNER_USER_B, "owner-b", "owner-b@example.test", "Owner B", "active"),
    )
    connection.execute(
        text(
            "INSERT INTO users "
            "(id,external_identity_provider,external_subject,email,display_name,status,"
            "created_at,updated_at,version) VALUES "
            "(:id,'phase212',:subject,:email,:name,:status,:now,:now,1)"
        ),
        [
            {
                "id": user_id,
                "subject": subject,
                "email": email,
                "name": name,
                "status": status,
                "now": NOW,
            }
            for user_id, subject, email, name, status in users
        ],
    )
    memberships = (
        (OWNER_MEMBERSHIP_A, WORKSPACE_A, OWNER_USER_A, "owner", "active"),
        (ADMIN_MEMBERSHIP_A, WORKSPACE_A, ADMIN_USER_A, "admin", "active"),
        (MEMBER_MEMBERSHIP_A, WORKSPACE_A, MEMBER_USER_A, "member", "active"),
        (
            INACTIVE_OWNER_MEMBERSHIP_A,
            WORKSPACE_A,
            INACTIVE_OWNER_USER_A,
            "owner",
            "suspended",
        ),
        (
            INACTIVE_ADMIN_MEMBERSHIP_A,
            WORKSPACE_A,
            INACTIVE_ADMIN_USER_A,
            "admin",
            "suspended",
        ),
        (OWNER_MEMBERSHIP_B, WORKSPACE_B, OWNER_USER_B, "owner", "active"),
    )
    connection.execute(
        text(
            "INSERT INTO memberships "
            "(id,workspace_id,user_id,role,status,created_at,updated_at,version) "
            "VALUES (:id,:workspace,:user_id,:role,:status,:now,:now,1)"
        ),
        [
            {
                "id": membership_id,
                "workspace": workspace_id,
                "user_id": user_id,
                "role": role,
                "status": status,
                "now": NOW,
            }
            for membership_id, workspace_id, user_id, role, status in memberships
        ],
    )


def _create_role_and_grants(connection: Connection) -> None:
    connection.execute(
        text(
            f"CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    connection.execute(text(f"GRANT CONNECT ON DATABASE rightjob_phase16 TO {APP_ROLE}"))
    connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
    for table in (
        "authorization_evidence",
        "approval_requests",
        "approval_decisions",
        "execution_authorizations",
        "execution_authorization_steps",
        "execution_requests",
        "execution_runs",
        "execution_steps",
        "audit_entries",
        "outbox_events",
    ):
        connection.execute(text(f"GRANT SELECT, INSERT ON {table} TO {APP_ROLE}"))
    connection.execute(
        text(f"GRANT UPDATE (status, resolved_at, version) ON approval_requests TO {APP_ROLE}")
    )


def _cleanup_exact(connection: Connection) -> None:
    for table, ids in (
        ("execution_steps", EXECUTION_STEP_IDS),
        ("execution_runs", (EXECUTION_RUN_A, DUPLICATE_EXECUTION_RUN)),
        (
            "execution_requests",
            (EXECUTION_REQUEST_A, DUPLICATE_EXECUTION_REQUEST, ROLLBACK_EXECUTION_REQUEST),
        ),
        ("execution_authorization_steps", EXECUTION_AUTHORIZATION_STEP_IDS),
        ("execution_authorizations", EXECUTION_AUTHORIZATION_IDS),
        ("approval_decisions", APPROVAL_DECISION_IDS),
        ("approval_requests", APPROVAL_REQUEST_IDS),
        ("authorization_evidence", EVIDENCE_IDS),
        ("outbox_events", OUTBOX_IDS),
        ("audit_entries", AUDIT_IDS),
        (
            "memberships",
            (
                OWNER_MEMBERSHIP_A,
                ADMIN_MEMBERSHIP_A,
                MEMBER_MEMBERSHIP_A,
                INACTIVE_OWNER_MEMBERSHIP_A,
                INACTIVE_ADMIN_MEMBERSHIP_A,
                OWNER_MEMBERSHIP_B,
            ),
        ),
        (
            "users",
            (
                OWNER_USER_A,
                ADMIN_USER_A,
                MEMBER_USER_A,
                INACTIVE_OWNER_USER_A,
                INACTIVE_ADMIN_USER_A,
                OWNER_USER_B,
            ),
        ),
        ("workspaces", (WORKSPACE_A, WORKSPACE_B)),
    ):
        connection.execute(text(f"DELETE FROM {table} WHERE id = ANY(:ids)"), {"ids": list(ids)})


def _drop_role(connection: Connection) -> None:
    exists = connection.scalar(
        text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:role)"), {"role": APP_ROLE}
    )
    if not exists:
        return
    for table in (
        "authorization_evidence",
        "approval_requests",
        "approval_decisions",
        "execution_authorizations",
        "execution_authorization_steps",
        "execution_requests",
        "execution_runs",
        "execution_steps",
        "audit_entries",
        "outbox_events",
    ):
        connection.execute(text(f"REVOKE ALL ON {table} FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE ALL ON SCHEMA public FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE CONNECT ON DATABASE rightjob_phase16 FROM {APP_ROLE}"))
    connection.execute(text(f"DROP ROLE {APP_ROLE}"))


@pytest.fixture(scope="module")
def phase212_engines() -> Iterator[tuple[Engine, Engine]]:
    assert OWNER_URL and APP_URL
    register_sqlalchemy_mappings()
    owner = create_engine(OWNER_URL)
    verifier = create_engine(APP_URL)
    try:
        with owner.begin() as connection:
            _assert_pristine(connection)
            assert len(ALL_APPROVED_IDS) == len(set(ALL_APPROVED_IDS))
            _create_role_and_grants(connection)
            _insert_identity(connection)
        yield owner, verifier
    finally:
        verifier.dispose()
        with owner.begin() as connection:
            _cleanup_exact(connection)
            _drop_role(connection)
            _assert_pristine(connection)
        owner.dispose()


@pytest.fixture(autouse=True)
def exact_governance_cleanup(phase212_engines: tuple[Engine, Engine]) -> Iterator[None]:
    owner, _ = phase212_engines
    yield
    with owner.begin() as connection:
        for table, ids in (
            ("execution_steps", EXECUTION_STEP_IDS),
            ("execution_runs", (EXECUTION_RUN_A, DUPLICATE_EXECUTION_RUN)),
            (
                "execution_requests",
                (EXECUTION_REQUEST_A, DUPLICATE_EXECUTION_REQUEST, ROLLBACK_EXECUTION_REQUEST),
            ),
            ("execution_authorization_steps", EXECUTION_AUTHORIZATION_STEP_IDS),
            ("execution_authorizations", EXECUTION_AUTHORIZATION_IDS),
            ("approval_decisions", APPROVAL_DECISION_IDS),
            ("approval_requests", APPROVAL_REQUEST_IDS),
            ("authorization_evidence", EVIDENCE_IDS),
            ("outbox_events", OUTBOX_IDS),
            ("audit_entries", AUDIT_IDS),
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE id = ANY(:ids)"), {"ids": list(ids)}
            )


def test_atomic_governance_audit_outbox_commit_and_rollback(
    phase212_engines: tuple[Engine, Engine],
) -> None:
    owner, _ = phase212_engines
    evidence = _evidence_values(
        EVIDENCE_IDS[0], POLICY_EVALUATIONS[0], ALLOW_PLAN, PLAN_STEPS[0], "allow"
    )
    with owner.begin() as connection:
        session = Session(bind=connection)
        session.add(AuthorizationEvidenceRecord(**evidence))
        session.add(AuditEntryRecord(**_audit_values(AUDIT_IDS[0], WORKSPACE_A, EVIDENCE_IDS[0])))
        session.add(
            OutboxEventRecord(**_outbox_values(OUTBOX_IDS[0], WORKSPACE_A, EVIDENCE_IDS[0]))
        )
        session.flush()
    with owner.connect() as connection:
        assert (
            connection.scalar(
                select(AuthorizationEvidenceRecord.id).where(
                    AuthorizationEvidenceRecord.id == EVIDENCE_IDS[0]
                )
            )
            == EVIDENCE_IDS[0]
        )
        assert connection.scalar(
            select(AuditEntryRecord.id).where(AuditEntryRecord.id == AUDIT_IDS[0])
        )
        assert connection.scalar(
            select(OutboxEventRecord.id).where(OutboxEventRecord.id == OUTBOX_IDS[0])
        )

    rollback = _evidence_values(
        EVIDENCE_IDS[7], POLICY_EVALUATIONS[7], ROLLBACK_PLAN, PLAN_STEPS[7], "allow"
    )
    with (
        pytest.raises(RuntimeError, match="intentional pre-commit failure"),
        owner.begin() as connection,
    ):
        session = Session(bind=connection)
        session.add(AuthorizationEvidenceRecord(**rollback))
        session.add(AuditEntryRecord(**_audit_values(AUDIT_IDS[7], WORKSPACE_A, EVIDENCE_IDS[7])))
        session.add(
            OutboxEventRecord(**_outbox_values(OUTBOX_IDS[7], WORKSPACE_A, EVIDENCE_IDS[7]))
        )
        session.flush()
        raise RuntimeError("intentional pre-commit failure")
    with owner.connect() as connection:
        assert not connection.scalar(
            select(AuthorizationEvidenceRecord.id).where(
                AuthorizationEvidenceRecord.id == EVIDENCE_IDS[7]
            )
        )
        assert not connection.scalar(
            select(AuditEntryRecord.id).where(AuditEntryRecord.id == AUDIT_IDS[7])
        )
        assert not connection.scalar(
            select(OutboxEventRecord.id).where(OutboxEventRecord.id == OUTBOX_IDS[7])
        )


def test_rls_isolation_and_missing_context_fail_closed(
    phase212_engines: tuple[Engine, Engine],
) -> None:
    owner, verifier = phase212_engines
    evidence_a = _evidence_values(
        EVIDENCE_IDS[0], POLICY_EVALUATIONS[0], ALLOW_PLAN, PLAN_STEPS[0], "allow"
    )
    evidence_b = _evidence_values(
        EVIDENCE_IDS[6],
        POLICY_EVALUATIONS[6],
        EQUAL_DIGEST_PLAN_B,
        PLAN_STEPS[6],
        "allow",
        workspace_id=WORKSPACE_B,
        planning_request_id=PLANNING_REQUEST_B,
    )
    with owner.begin() as connection:
        connection.execute(insert(AuthorizationEvidenceRecord), [evidence_a, evidence_b])
    with verifier.begin() as connection:
        _scope(connection, WORKSPACE_A)
        assert connection.scalars(select(AuthorizationEvidenceRecord.id)).all() == [EVIDENCE_IDS[0]]
    with verifier.begin() as connection:
        _scope(connection, WORKSPACE_B)
        assert connection.scalars(select(AuthorizationEvidenceRecord.id)).all() == [EVIDENCE_IDS[6]]
    with verifier.begin() as connection:
        assert connection.scalars(select(AuthorizationEvidenceRecord.id)).all() == []
        with pytest.raises(DBAPIError):
            connection.execute(insert(AuthorizationEvidenceRecord), evidence_a)


def test_append_only_privileges_and_narrow_approval_update(
    phase212_engines: tuple[Engine, Engine],
) -> None:
    owner, verifier = phase212_engines
    evidence = _evidence_values(
        EVIDENCE_IDS[1],
        POLICY_EVALUATIONS[1],
        APPROVAL_PLAN,
        PLAN_STEPS[1],
        "require_approval",
    )
    request = _request_values(APPROVAL_REQUEST_IDS[0], evidence, idempotency="request-primary")
    decision = _decision_values(APPROVAL_DECISION_IDS[0], request, idempotency="decision-primary")
    authorization = _authorization_values(
        EXECUTION_AUTHORIZATION_IDS[0], ALLOW_PLAN, idempotency="authorization-allow"
    )
    step = {
        "id": EXECUTION_AUTHORIZATION_STEP_IDS[0],
        "workspace_id": WORKSPACE_A,
        "execution_authorization_id": EXECUTION_AUTHORIZATION_IDS[0],
        "step_id": PLAN_STEPS[1],
        "sequence": 0,
        "action_digest": DIGEST_A,
        "authorization_evidence_id": EVIDENCE_IDS[1],
        "approval_request_id": APPROVAL_REQUEST_IDS[0],
        "approval_decision_id": APPROVAL_DECISION_IDS[0],
    }
    with verifier.begin() as connection:
        _scope(connection, WORKSPACE_A)
        connection.execute(insert(AuthorizationEvidenceRecord), evidence)
        connection.execute(insert(ApprovalRequestRecord), request)
        connection.execute(insert(ApprovalDecisionRecord), decision)
        connection.execute(insert(ExecutionAuthorizationRecord), authorization)
        connection.execute(insert(ExecutionAuthorizationStepRecord), step)
        connection.execute(
            update(ApprovalRequestRecord)
            .where(ApprovalRequestRecord.id == APPROVAL_REQUEST_IDS[0])
            .values(status="approved", resolved_at=NOW + timedelta(seconds=2), version=2)
        )
    for record in (
        AuthorizationEvidenceRecord,
        ApprovalDecisionRecord,
        ExecutionAuthorizationRecord,
        ExecutionAuthorizationStepRecord,
    ):
        with verifier.begin() as connection:
            _scope(connection, WORKSPACE_A)
            with pytest.raises(ProgrammingError):
                connection.execute(update(record).values(workspace_id=WORKSPACE_B))
        with verifier.begin() as connection:
            _scope(connection, WORKSPACE_A)
            with pytest.raises(ProgrammingError):
                connection.execute(delete(record))
    with verifier.begin() as connection:
        _scope(connection, WORKSPACE_A)
        with pytest.raises(ProgrammingError):
            connection.execute(
                update(ApprovalRequestRecord)
                .where(ApprovalRequestRecord.id == APPROVAL_REQUEST_IDS[0])
                .values(action_digest=DIGEST_B)
            )


def test_exact_equal_digest_binding_and_uniqueness(
    phase212_engines: tuple[Engine, Engine],
) -> None:
    owner, _ = phase212_engines
    evidence_a = _evidence_values(
        EVIDENCE_IDS[4],
        POLICY_EVALUATIONS[4],
        EQUAL_DIGEST_PLAN_A,
        PLAN_STEPS[4],
        "require_approval",
        digest=DIGEST_A,
    )
    evidence_b = _evidence_values(
        EVIDENCE_IDS[5],
        POLICY_EVALUATIONS[5],
        EQUAL_DIGEST_PLAN_B,
        PLAN_STEPS[5],
        "require_approval",
        digest=DIGEST_A,
    )
    request_a = _request_values(APPROVAL_REQUEST_IDS[1], evidence_a, idempotency="equal-request-a")
    request_b = _request_values(APPROVAL_REQUEST_IDS[2], evidence_b, idempotency="equal-request-b")
    decision_a = _decision_values(
        APPROVAL_DECISION_IDS[2], request_a, idempotency="equal-decision-a"
    )
    decision_b = _decision_values(
        APPROVAL_DECISION_IDS[3], request_b, idempotency="equal-decision-b"
    )
    authorization = _authorization_values(
        EXECUTION_AUTHORIZATION_IDS[1], MIXED_PLAN, idempotency="authorization-mixed"
    )
    with owner.begin() as connection:
        connection.execute(insert(AuthorizationEvidenceRecord), [evidence_a, evidence_b])
        connection.execute(insert(ApprovalRequestRecord), [request_a, request_b])
        connection.execute(insert(ApprovalDecisionRecord), [decision_a, decision_b])
        connection.execute(insert(ExecutionAuthorizationRecord), authorization)
    invalid = {
        "id": EXECUTION_AUTHORIZATION_STEP_IDS[1],
        "workspace_id": WORKSPACE_A,
        "execution_authorization_id": EXECUTION_AUTHORIZATION_IDS[1],
        "step_id": PLAN_STEPS[4],
        "sequence": 0,
        "action_digest": DIGEST_A,
        "authorization_evidence_id": EVIDENCE_IDS[4],
        "approval_request_id": APPROVAL_REQUEST_IDS[2],
        "approval_decision_id": APPROVAL_DECISION_IDS[3],
    }
    with pytest.raises(IntegrityError), owner.begin() as connection:
        connection.execute(insert(ExecutionAuthorizationStepRecord), invalid)


def test_request_optimistic_concurrency_and_terminal_races(
    phase212_engines: tuple[Engine, Engine],
) -> None:
    owner, _ = phase212_engines
    evidence = _evidence_values(
        EVIDENCE_IDS[1],
        POLICY_EVALUATIONS[1],
        APPROVAL_PLAN,
        PLAN_STEPS[1],
        "require_approval",
    )
    request = _request_values(APPROVAL_REQUEST_IDS[3], evidence, idempotency="approve-reject-race")
    with owner.begin() as connection:
        connection.execute(insert(AuthorizationEvidenceRecord), evidence)
        connection.execute(insert(ApprovalRequestRecord), request)
    first = Session(owner)
    second = Session(owner)
    try:
        repository_a = SqlAlchemyApprovalRequestRepository(first)
        repository_b = SqlAlchemyApprovalRequestRepository(second)
        current_a = repository_a.get(WORKSPACE_A, APPROVAL_REQUEST_IDS[3])
        current_b = repository_b.get(WORKSPACE_A, APPROVAL_REQUEST_IDS[3])
        assert current_a and current_b
        repository_a.save(
            WORKSPACE_A,
            current_a.transition(
                ApprovalStatus.APPROVED,
                NOW + timedelta(seconds=2),
            ),
            1,
        )
        first.commit()
        with pytest.raises(ConcurrentApprovalUpdateError):
            repository_b.save(
                WORKSPACE_A,
                current_b.transition(
                    ApprovalStatus.REJECTED,
                    NOW + timedelta(seconds=2),
                ),
                1,
            )
    finally:
        first.rollback()
        second.rollback()
        first.close()
        second.close()


@pytest.mark.parametrize(
    ("user_id", "membership_id", "role", "active", "workspace_id", "allowed"),
    (
        (OWNER_USER_A, OWNER_MEMBERSHIP_A, "owner", True, WORKSPACE_A, True),
        (ADMIN_USER_A, ADMIN_MEMBERSHIP_A, "admin", True, WORKSPACE_A, True),
        (MEMBER_USER_A, MEMBER_MEMBERSHIP_A, "member", True, WORKSPACE_A, False),
        (
            INACTIVE_OWNER_USER_A,
            INACTIVE_OWNER_MEMBERSHIP_A,
            "owner",
            False,
            WORKSPACE_A,
            False,
        ),
        (
            INACTIVE_ADMIN_USER_A,
            INACTIVE_ADMIN_MEMBERSHIP_A,
            "admin",
            False,
            WORKSPACE_A,
            False,
        ),
        (OWNER_USER_B, OWNER_MEMBERSHIP_B, "owner", True, WORKSPACE_B, False),
    ),
)
def test_synthetic_approver_authority_is_identity_fact_driven(
    user_id: UUID,
    membership_id: UUID,
    role: str,
    active: bool,
    workspace_id: UUID,
    allowed: bool,
) -> None:
    arguments = (
        APPROVAL_DECISION_IDS[0],
        APPROVAL_REQUEST_IDS[0],
        WORKSPACE_A,
        DIGEST_A,
        ApprovalOutcome.APPROVED,
        Actor(ActorType.USER, str(user_id)),
        _membership(
            user_id,
            membership_id,
            role,
            workspace_id=workspace_id,
            active=active,
        ),
        NOW + timedelta(seconds=2),
        CORRELATION_A,
        CAUSATION_A,
    )
    if allowed:
        assert ApprovalDecision(*arguments).membership.roles == (role,)
    else:
        with pytest.raises(AuthorizationError):
            ApprovalDecision(*arguments)


def test_application_idempotency_reuses_canonical_governance_aggregates(
    phase212_engines: tuple[Engine, Engine],
) -> None:
    owner, _ = phase212_engines
    plan, capabilities, departments = _domain_plan(
        APPROVAL_PLAN,
        ((PLAN_STEPS[1], 0, EffectClassification.CONSEQUENTIAL),),
    )
    evaluation = _evaluate_plan(plan, capabilities, departments, (POLICY_EVALUATIONS[1],))[0]
    durable = DurableAuthorizationService(
        capabilities,
        departments,
        SYNTHETIC_POLICY_SET,
        FixedIds((EVIDENCE_IDS[1],)),
    )
    evidence = durable.record_evidence(plan, evaluation)
    request = ApprovalRequest.create(APPROVAL_REQUEST_IDS[0], evidence, NOW + timedelta(seconds=1))
    approved = ApprovalDecision(
        APPROVAL_DECISION_IDS[0],
        request.approval_request_id,
        WORKSPACE_A,
        request.action_digest,
        ApprovalOutcome.APPROVED,
        Actor(ActorType.USER, str(OWNER_USER_A)),
        _membership(OWNER_USER_A, OWNER_MEMBERSHIP_A, "owner"),
        NOW + timedelta(seconds=2),
        CORRELATION_A,
        CAUSATION_A,
    )
    resolved = decide_request(request, approved)
    workflow = AuthorizedWorkflow(
        WORKFLOW_DEFINITION,
        "synthetic.approval",
        "1.0.0",
        True,
        (AuthorizedWorkflowStep(plan.steps[0].department, plan.steps[0].capability),),
    )
    issuer = DurableAuthorizationService(
        capabilities,
        departments,
        SYNTHETIC_POLICY_SET,
        FixedIds((EXECUTION_AUTHORIZATION_STEP_IDS[0], EXECUTION_AUTHORIZATION_IDS[0])),
    )
    authorization = issuer.issue(
        plan,
        workflow,
        {plan.steps[0].step_id: evidence},
        {plan.steps[0].step_id: (resolved, approved)},
        {plan.steps[0].step_id: _membership(OWNER_USER_A, OWNER_MEMBERSHIP_A, "owner")},
        {plan.steps[0].step_id: _membership(OWNER_USER_A, OWNER_MEMBERSHIP_A, "owner")},
        NOW + timedelta(seconds=3),
    )
    factory = sessionmaker(owner, expire_on_commit=False)
    recorder = GovernanceRecorder(
        lambda: SqlAlchemyPolicyApprovalUnitOfWork(
            factory,
            SqlAlchemyAuditEvidenceRepository,
            SqlAlchemyOutboxRepository,
        ),
        FixedIds(
            tuple(item for pair in zip(AUDIT_IDS[:4], OUTBOX_IDS[:4], strict=True) for item in pair)
        ),
    )

    assert recorder.record_evidence(evidence) == evidence
    assert (
        recorder.record_evidence(replace(evidence, authorization_evidence_id=EVIDENCE_IDS[2]))
        == evidence
    )
    with pytest.raises(IdempotencyConflictError):
        recorder.record_evidence(
            replace(
                evidence,
                authorization_evidence_id=EVIDENCE_IDS[2],
                policy_evaluation=replace(
                    evidence.policy_evaluation,
                    expires_at=evidence.expires_at - timedelta(seconds=1),
                ),
            )
        )

    assert recorder.create_approval_request(request, "approval-request-idempotency") == request
    assert recorder.record_decision(resolved, approved, "approval-decision-idempotency") == approved
    replayed_request = recorder.create_approval_request(
        replace(request, approval_request_id=APPROVAL_REQUEST_IDS[1]),
        "approval-request-idempotency",
    )
    assert replayed_request.status is ApprovalStatus.APPROVED
    assert replayed_request.version == 2
    with pytest.raises(IdempotencyConflictError):
        recorder.record_decision(
            resolved,
            replace(
                approved,
                approval_decision_id=APPROVAL_DECISION_IDS[1],
                outcome=ApprovalOutcome.REJECTED,
            ),
            "approval-decision-idempotency",
        )

    policy_actor = Actor(ActorType.SYSTEM, "policy")
    assert (
        recorder.issue_authorization(authorization, policy_actor, "authorization-idempotency")
        == authorization
    )
    replayed_authorization = replace(
        authorization,
        execution_authorization_id=EXECUTION_AUTHORIZATION_IDS[1],
        steps=(
            replace(
                authorization.steps[0],
                execution_authorization_step_id=EXECUTION_AUTHORIZATION_STEP_IDS[1],
            ),
        ),
    )
    assert (
        recorder.issue_authorization(
            replayed_authorization, policy_actor, "authorization-idempotency"
        )
        == authorization
    )
    with pytest.raises(IdempotencyConflictError):
        recorder.issue_authorization(
            replace(
                replayed_authorization,
                steps=(replace(replayed_authorization.steps[0], action_digest="f" * 64),),
            ),
            policy_actor,
            "authorization-idempotency",
        )

    with owner.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(AuthorizationEvidenceRecord)) == 1
        assert connection.scalar(select(func.count()).select_from(ApprovalRequestRecord)) == 1
        assert connection.scalar(select(func.count()).select_from(ApprovalDecisionRecord)) == 1
        assert (
            connection.scalar(select(func.count()).select_from(ExecutionAuthorizationRecord)) == 1
        )
        assert connection.scalar(select(func.count()).select_from(AuditEntryRecord)) == 4
        assert connection.scalar(select(func.count()).select_from(OutboxEventRecord)) == 4


def test_multistep_authorization_is_atomic_and_requires_exact_approval() -> None:
    plan, capabilities, departments = _domain_plan(
        MIXED_PLAN,
        (
            (PLAN_STEPS[8], 0, EffectClassification.READ_ONLY),
            (PLAN_STEPS[9], 1, EffectClassification.READ_ONLY),
            (PLAN_STEPS[10], 2, EffectClassification.CONSEQUENTIAL),
            (PLAN_STEPS[11], 3, EffectClassification.READ_ONLY),
        ),
    )
    evaluations = _evaluate_plan(plan, capabilities, departments, POLICY_EVALUATIONS[8:12])
    evidence_ids = EVIDENCE_IDS[8:12]
    evidence_service = DurableAuthorizationService(
        capabilities,
        departments,
        SYNTHETIC_POLICY_SET,
        FixedIds(evidence_ids),
    )
    evidence = tuple(
        evidence_service.record_evidence(plan, evaluation) for evaluation in evaluations
    )
    workflow = AuthorizedWorkflow(
        WORKFLOW_DEFINITION,
        "synthetic.mixed",
        "1.0.0",
        True,
        tuple(AuthorizedWorkflowStep(step.department, step.capability) for step in plan.steps),
    )
    current_subject = {
        step.step_id: _membership(OWNER_USER_A, OWNER_MEMBERSHIP_A, "owner") for step in plan.steps
    }
    issue_service = DurableAuthorizationService(
        capabilities,
        departments,
        SYNTHETIC_POLICY_SET,
        FixedIds(
            (
                EXECUTION_AUTHORIZATION_STEP_IDS[3],
                EXECUTION_AUTHORIZATION_STEP_IDS[4],
                EXECUTION_AUTHORIZATION_STEP_IDS[5],
                EXECUTION_AUTHORIZATION_STEP_IDS[6],
                EXECUTION_AUTHORIZATION_IDS[1],
            )
        ),
    )
    evidence_by_step = dict(zip((step.step_id for step in plan.steps), evidence, strict=True))
    with pytest.raises(AuthorizationError, match="unresolved"):
        issue_service.issue(
            plan,
            workflow,
            evidence_by_step,
            {},
            current_subject,
            {},
            NOW + timedelta(seconds=3),
        )
    issue_service = DurableAuthorizationService(
        capabilities,
        departments,
        SYNTHETIC_POLICY_SET,
        FixedIds(
            (
                EXECUTION_AUTHORIZATION_STEP_IDS[3],
                EXECUTION_AUTHORIZATION_STEP_IDS[4],
                EXECUTION_AUTHORIZATION_STEP_IDS[5],
                EXECUTION_AUTHORIZATION_STEP_IDS[6],
                EXECUTION_AUTHORIZATION_IDS[1],
            )
        ),
    )
    consequential_step = plan.steps[2]
    consequential_evidence = evidence[2]
    request = ApprovalRequest.create(
        APPROVAL_REQUEST_IDS[0], consequential_evidence, NOW + timedelta(seconds=1)
    )
    approved = ApprovalDecision(
        APPROVAL_DECISION_IDS[0],
        request.approval_request_id,
        WORKSPACE_A,
        request.action_digest,
        ApprovalOutcome.APPROVED,
        Actor(ActorType.USER, str(OWNER_USER_A)),
        _membership(OWNER_USER_A, OWNER_MEMBERSHIP_A, "owner"),
        NOW + timedelta(seconds=2),
        CORRELATION_A,
        CAUSATION_A,
    )
    resolved = decide_request(request, approved)
    authorization = issue_service.issue(
        plan,
        workflow,
        evidence_by_step,
        {consequential_step.step_id: (resolved, approved)},
        current_subject,
        {consequential_step.step_id: _membership(OWNER_USER_A, OWNER_MEMBERSHIP_A, "owner")},
        NOW + timedelta(seconds=3),
    )
    assert len(authorization.steps) == 4
    assert authorization.steps[2].approval_decision_id == APPROVAL_DECISION_IDS[0]
    assert all(
        step.approval_decision_id is None
        for index, step in enumerate(authorization.steps)
        if index != 2
    )

    denied_evaluation = replace(evaluations[0], decision=PolicyDecision.DENY)
    denied_service = DurableAuthorizationService(
        capabilities,
        departments,
        SYNTHETIC_POLICY_SET,
        FixedIds((EVIDENCE_IDS[0],)),
    )
    denied = denied_service.record_evidence(plan, denied_evaluation)
    with pytest.raises(AuthorizationError, match="DENY"):
        issue_service.issue(
            plan,
            workflow,
            {**evidence_by_step, plan.steps[0].step_id: denied},
            {consequential_step.step_id: (resolved, approved)},
            current_subject,
            {consequential_step.step_id: _membership(OWNER_USER_A, OWNER_MEMBERSHIP_A, "owner")},
            NOW + timedelta(seconds=3),
        )


def test_execution_authorization_single_use_and_one_request_one_run(
    phase212_engines: tuple[Engine, Engine],
) -> None:
    owner, _ = phase212_engines
    evidence = _evidence_values(
        EVIDENCE_IDS[0], POLICY_EVALUATIONS[0], ALLOW_PLAN, PLAN_STEPS[0], "allow"
    )
    authorization = _authorization_values(
        EXECUTION_AUTHORIZATION_IDS[2], ALLOW_PLAN, idempotency="authorization-single-use"
    )
    auth_step = {
        "id": EXECUTION_AUTHORIZATION_STEP_IDS[2],
        "workspace_id": WORKSPACE_A,
        "execution_authorization_id": EXECUTION_AUTHORIZATION_IDS[2],
        "step_id": PLAN_STEPS[0],
        "sequence": 0,
        "action_digest": DIGEST_A,
        "authorization_evidence_id": EVIDENCE_IDS[0],
        "approval_request_id": None,
        "approval_decision_id": None,
    }
    request = {
        "id": EXECUTION_REQUEST_A,
        "workspace_id": WORKSPACE_A,
        "correlation_id": CORRELATION_A,
        "causation_id": CAUSATION_A,
        "actor_type": "user",
        "actor_id": str(OWNER_USER_A),
        "initiator_type": "user",
        "execution_authorization_id": EXECUTION_AUTHORIZATION_IDS[2],
        "workflow_definition_id": WORKFLOW_DEFINITION,
        "workflow_type": "synthetic.foundation",
        "workflow_version": "1.0.0",
        "input_json": {},
        "created_at": NOW + timedelta(seconds=4),
    }
    with owner.begin() as connection:
        connection.execute(insert(AuthorizationEvidenceRecord), evidence)
        connection.execute(insert(ExecutionAuthorizationRecord), authorization)
        connection.execute(insert(ExecutionAuthorizationStepRecord), auth_step)
        connection.execute(insert(ExecutionRequestRecord), request)
    duplicate = dict(request, id=DUPLICATE_EXECUTION_REQUEST)
    with pytest.raises(IntegrityError), owner.begin() as connection:
        connection.execute(insert(ExecutionRequestRecord), duplicate)
    run = {
        "id": EXECUTION_RUN_A,
        "workspace_id": WORKSPACE_A,
        "execution_request_id": EXECUTION_REQUEST_A,
        "workflow_definition_id": WORKFLOW_DEFINITION,
        "workflow_type": "synthetic.foundation",
        "workflow_version": "1.0.0",
        "status": "queued",
        "correlation_id": CORRELATION_A,
        "causation_id": CAUSATION_A,
        "actor_type": "user",
        "actor_id": str(OWNER_USER_A),
        "initiator_type": "user",
        "created_at": NOW + timedelta(seconds=4),
        "started_at": None,
        "completed_at": None,
        "cancellation_requested_at": None,
        "cancelled_at": None,
        "reconciliation_state": "not_required",
        "version": 1,
    }
    with owner.begin() as connection:
        columns = ",".join(run)
        values = ",".join(f":{key}" for key in run)
        connection.execute(text(f"INSERT INTO execution_runs ({columns}) VALUES ({values})"), run)
    with pytest.raises(IntegrityError), owner.begin() as connection:
        duplicate_run = dict(run, id=DUPLICATE_EXECUTION_RUN)
        columns = ",".join(duplicate_run)
        values = ",".join(f":{key}" for key in duplicate_run)
        connection.execute(
            text(f"INSERT INTO execution_runs ({columns}) VALUES ({values})"), duplicate_run
        )


def test_schema_and_grant_contract_is_exact(phase212_engines: tuple[Engine, Engine]) -> None:
    owner, _ = phase212_engines
    with owner.connect() as connection:
        attributes = connection.execute(
            text(
                "SELECT rolsuper,rolcreatedb,rolcreaterole,rolinherit,rolbypassrls "
                "FROM pg_roles WHERE rolname=:role"
            ),
            {"role": APP_ROLE},
        ).one()
        assert attributes == (False, False, False, False, False)
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.role_table_grants "
                    "WHERE grantee=:role AND privilege_type IN "
                    "('DELETE','TRUNCATE','REFERENCES','TRIGGER')"
                ),
                {"role": APP_ROLE},
            )
            == 0
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.role_column_grants "
                    "WHERE grantee=:role AND table_name='approval_requests' "
                    "AND privilege_type='UPDATE' "
                    "AND column_name IN ('status','resolved_at','version')"
                ),
                {"role": APP_ROLE},
            )
            == 3
        )
