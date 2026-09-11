from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from itertools import count
from uuid import UUID

import pytest
from rightjob.audit.infrastructure.repositories import (
    SqlAlchemyAuditEvidenceRepository,
    SqlAlchemyOutboxRepository,
)
from rightjob.contracts.review import (
    ArtifactReference,
    CapabilityResult,
    EvidenceReference,
    ResultProvenance,
    ResultValidationEvidence,
    ResultValidationOutcome,
    ResultValidationReason,
    ValidationCriteriaReference,
    canonical_result_payload,
    result_digest,
)
from rightjob.contracts.revision import QualityGateStatus
from rightjob.contracts.revision_execution import (
    RevisionArtifactSubmission,
    RevisionCompletionCommand,
    RevisionExecutionContractError,
    RevisionExecutionStatus,
    RevisionLifecycleCommand,
    RevisionLifecycleReason,
    revision_workflow_id,
)
from rightjob.identity.infrastructure import models as _identity_models  # noqa: F401
from rightjob.orchestration.application.revision_execution import (
    DurableRevisionExecutionClaimService,
    DurableRevisionLifecycleService,
    RevisionExecutionClaimService,
)
from rightjob.orchestration.infrastructure.repositories import (
    SqlAlchemyQualityGateDecisionRepository,
    SqlAlchemyQualityGateStateRepository,
    SqlAlchemyRevisionActivityAuthority,
)
from rightjob.orchestration.infrastructure.unit_of_work import SqlAlchemyExecutionUnitOfWork
from rightjob.policy.infrastructure.repositories import SqlAlchemyAuthorizationEvidenceRepository
from rightjob.registry.catalog import BuiltInCapabilityRegistry
from rightjob.registry.departments import BuiltInDepartmentRegistry
from rightjob_worker.revision_runtime import _request
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from tests.unit.test_revision_execution import (
    ARTIFACT,
    CAPABILITY,
    CORRELATION,
    GATE,
    NOW,
    RUN,
    SOURCE,
    STEP,
    WORKSPACE,
    authorized_command,
    gate,
)

OWNER_URL = os.environ.get("RIGHTJOB_DATABASE_URL")
APP_URL = os.environ.get("RIGHTJOB_PHASE220_RLS_DATABASE_URL")
APP_ROLE = "rightjob_phase220_verifier"
WORKSPACE_B = UUID("00000000-0000-4000-8000-000000000299")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not OWNER_URL or not APP_URL, reason="isolated Phase 2.20 URLs required"),
]


class _UnusedAuthorization:
    pass


class _FailingOutbox:
    def add(self, workspace_id: UUID, event: object) -> None:
        raise RuntimeError("forced outbox failure")


def _uow_factory(app: Engine, *, fail_outbox: bool = False):
    sessions = sessionmaker(app, expire_on_commit=False)

    def factory() -> SqlAlchemyExecutionUnitOfWork:
        return SqlAlchemyExecutionUnitOfWork(
            sessions,
            lambda session: SqlAlchemyAuditEvidenceRepository(session),
            (lambda session: _FailingOutbox())
            if fail_outbox
            else (lambda session: SqlAlchemyOutboxRepository(session)),
            lambda session: _UnusedAuthorization(),  # type: ignore[arg-type]
        )

    return factory


def _service(app: Engine, *, fail_outbox: bool = False) -> DurableRevisionExecutionClaimService:
    capabilities = BuiltInCapabilityRegistry()
    return DurableRevisionExecutionClaimService(
        RevisionExecutionClaimService(
            capabilities,
            BuiltInDepartmentRegistry(capabilities),
        ),
        _uow_factory(app, fail_outbox=fail_outbox),
        id_factory=lambda: UUID(int=9900),
    )


@contextmanager
def _context(engine: Engine, workspace_id: UUID | None) -> Iterator[Connection]:
    with engine.begin() as connection:
        if workspace_id is not None:
            connection.execute(
                text("SELECT set_config('app.current_workspace_id', :workspace, true)"),
                {"workspace": str(workspace_id)},
            )
        yield connection


@pytest.fixture(scope="module")
def engines() -> Iterator[tuple[Engine, Engine]]:
    assert OWNER_URL and APP_URL
    owner, app = create_engine(OWNER_URL), create_engine(APP_URL)
    command, authorization = authorized_command()
    decision, state = gate()
    with owner.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260827_0006"
        connection.execute(
            text(
                "INSERT INTO workspaces (id,name,slug) VALUES "
                "(:a,'Revision A','phase220-revision-a'),(:b,'Revision B','phase220-revision-b')"
            ),
            {"a": WORKSPACE, "b": WORKSPACE_B},
        )
        connection.execute(text("SET session_replication_role = replica"))
        connection.execute(
            text(
                "INSERT INTO execution_steps "
                "(id,run_id,workspace_id,step_type,sequence,status,attempt_count,max_attempts,"
                "input_ref,version) VALUES (:step,:run,:workspace,'fake.verify',0,'succeeded',"
                "1,1,'quality-gate',1)"
            ),
            {"step": STEP, "run": RUN, "workspace": WORKSPACE},
        )
        connection.execute(text("SET session_replication_role = origin"))
        connection.execute(text(f"CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOBYPASSRLS"))
        connection.execute(text(f"GRANT CONNECT ON DATABASE rightjob_phase220 TO {APP_ROLE}"))
        connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
        connection.execute(
            text(
                f"GRANT SELECT ON authorization_evidence,approval_requests,approval_decisions,"
                f"quality_gate_decisions,execution_steps TO {APP_ROLE}"
            )
        )
        connection.execute(
            text(
                f"GRANT SELECT,UPDATE ON quality_gate_states TO {APP_ROLE}; "
                f"GRANT SELECT,INSERT,UPDATE ON revision_execution_claims,execution_runs,"
                f"execution_steps TO {APP_ROLE}; "
                f"GRANT SELECT,INSERT ON execution_requests,audit_entries,outbox_events "
                f"TO {APP_ROLE}"
            )
        )
    with Session(owner) as session:
        states = SqlAlchemyQualityGateStateRepository(session)
        decisions = SqlAlchemyQualityGateDecisionRepository(session)
        states.add(WORKSPACE, state, decision.evidence.minimum_score)
        session.flush()
        decisions.append(WORKSPACE, decision, None)
        SqlAlchemyAuthorizationEvidenceRepository(session).add(WORKSPACE, authorization)
        session.commit()
    try:
        yield owner, app
    finally:
        app.dispose()
        with owner.begin() as connection:
            connection.execute(text("SET session_replication_role = replica"))
            for table in (
                "revision_execution_claims",
                "execution_steps",
                "execution_runs",
                "execution_requests",
                "quality_gate_decisions",
                "quality_gate_states",
                "authorization_evidence",
                "audit_entries",
                "outbox_events",
            ):
                connection.execute(text(f"DELETE FROM {table}"))
            connection.execute(text("SET session_replication_role = origin"))
            connection.execute(
                text("DELETE FROM workspaces WHERE id IN (:a,:b)"),
                {"a": WORKSPACE, "b": WORKSPACE_B},
            )
            connection.execute(text(f"DROP OWNED BY {APP_ROLE}"))
            connection.execute(text(f"DROP ROLE {APP_ROLE}"))
        owner.dispose()


def test_schema_rls_and_cross_workspace_denial(engines: tuple[Engine, Engine]) -> None:
    owner, app = engines
    with owner.connect() as connection:
        assert connection.execute(
            text(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                "WHERE relname='revision_execution_claims'"
            )
        ).one() == (True, True)
    with _context(app, WORKSPACE_B) as connection:
        assert connection.execute(text("SELECT id FROM revision_execution_claims")).all() == []
    with pytest.raises(DBAPIError), _context(app, WORKSPACE_B) as connection:
        connection.execute(
            text(
                "INSERT INTO revision_execution_claims "
                "(id,workspace_id,command_id,quality_gate_id,quality_decision_id,reserved_cycle) "
                "VALUES (:id,:workspace,:id,:id,:id,1)"
            ),
            {"id": UUID(int=999), "workspace": WORKSPACE},
        )


def test_claim_linkage_idempotency_safe_evidence_and_constraints(
    engines: tuple[Engine, Engine],
) -> None:
    owner, app = engines
    command, authorization = authorized_command()
    service = _service(app)
    claim = service.claim(command, authorization)
    assert service.claim(command, authorization) == claim
    with owner.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM revision_execution_claims),"
                "(SELECT count(*) FROM execution_requests),"
                "(SELECT count(*) FROM execution_runs),"
                "(SELECT count(*) FROM execution_steps WHERE id<>:source),"
                "(SELECT count(*) FROM audit_entries),(SELECT count(*) FROM outbox_events)"
            ),
            {"source": STEP},
        ).one()
        assert counts == (1, 1, 1, 1, 1, 1)
        durable = connection.execute(
            text(
                "SELECT row_to_json(c)::text FROM revision_execution_claims c UNION ALL "
                "SELECT row_to_json(a)::text FROM audit_entries a UNION ALL "
                "SELECT row_to_json(o)::text FROM outbox_events o"
            )
        ).scalars()
        assert all(
            "reviewer" not in value and "prompt" not in value and "provider" not in value
            for value in durable
        )
        assert (
            connection.scalar(
                text("SELECT revision_authorization_evidence_id FROM execution_requests")
            )
            == authorization.authorization_evidence_id
        )
    with pytest.raises(IntegrityError), owner.begin() as connection:
        connection.execute(text("UPDATE revision_execution_claims SET reserved_cycle=3"))


def test_reconciliation_terminal_constraint_matrix(engines: tuple[Engine, Engine]) -> None:
    owner, _ = engines
    command, _ = authorized_command()
    statement = text(
        "UPDATE revision_execution_claims SET status=:status,lifecycle_reason=:reason,"
        "workflow_id=:workflow,"
        "launch_pending_at=:launch,running_at=:running,completed_at=:completed,"
        "failed_at=:failed,cancelled_at=:cancelled,"
        "reconciliation_required_at=:reconciliation,result_artifact_id=:artifact,"
        "result_artifact_version=:artifact_version,result_artifact_sha256=:sha,"
        "result_validation_evidence_id=:validation WHERE command_id=:command"
    )
    base = {
        "command": command.command_id,
        "workflow": revision_workflow_id(command.action),
        "launch": NOW,
        "running": None,
        "completed": None,
        "failed": None,
        "cancelled": None,
        "reconciliation": None,
        "artifact": None,
        "artifact_version": None,
        "sha": None,
        "validation": None,
    }
    result = {
        "artifact": ARTIFACT,
        "artifact_version": 2,
        "sha": "f" * 64,
        "validation": UUID(int=88001),
    }
    valid = [
        {"status": "running", "reason": None, "running": NOW},
        {"status": "completed", "reason": None, "running": NOW, "completed": NOW, **result},
        {
            "status": "failed",
            "reason": "execution_failed",
            "running": NOW,
            "failed": NOW,
        },
        {
            "status": "cancelled",
            "reason": "cancelled_by_request",
            "running": NOW,
            "cancelled": NOW,
        },
        {"status": "failed", "reason": "launch_rejected", "failed": NOW},
        {
            "status": "failed",
            "reason": "workflow_failed",
            "failed": NOW,
            "reconciliation": NOW,
        },
        {
            "status": "cancelled",
            "reason": "workflow_cancelled",
            "cancelled": NOW,
            "reconciliation": NOW,
        },
        {
            "status": "failed",
            "reason": "workflow_terminated",
            "failed": NOW,
            "reconciliation": NOW,
        },
        {
            "status": "failed",
            "reason": "workflow_timed_out",
            "failed": NOW,
            "reconciliation": NOW,
        },
        {
            "status": "completed",
            "reason": None,
            "completed": NOW,
            "reconciliation": NOW,
            **result,
        },
    ]
    invalid = [
        {"status": "running", "reason": None},
        {"status": "completed", "reason": None, "completed": NOW, **result},
        {"status": "failed", "reason": "execution_failed", "failed": NOW},
        {"status": "cancelled", "reason": "cancelled_by_request", "cancelled": NOW},
        {
            "status": "failed",
            "reason": "launch_rejected",
            "running": NOW,
            "failed": NOW,
        },
        {
            "status": "cancelled",
            "reason": "workflow_failed",
            "cancelled": NOW,
            "reconciliation": NOW,
        },
        {"status": "failed", "reason": "unknown", "failed": NOW},
        {
            "status": "failed",
            "reason": "workflow_failed",
            "reconciliation": NOW,
        },
    ]
    with owner.connect() as connection:
        for values in valid:
            savepoint = connection.begin_nested()
            connection.execute(statement, {**base, **values})
            savepoint.rollback()
        for values in invalid:
            savepoint = connection.begin_nested()
            with pytest.raises(IntegrityError):
                connection.execute(statement, {**base, **values})
            savepoint.rollback()


def test_forced_outbox_failure_rolls_back_everything(engines: tuple[Engine, Engine]) -> None:
    owner, app = engines
    with owner.begin() as connection:
        connection.execute(text("SET session_replication_role = replica"))
        for table in (
            "revision_execution_claims",
            "execution_steps",
            "execution_runs",
            "execution_requests",
            "audit_entries",
            "outbox_events",
        ):
            condition = " WHERE id<>:source" if table == "execution_steps" else ""
            connection.execute(text(f"DELETE FROM {table}{condition}"), {"source": STEP})
        connection.execute(text("SET session_replication_role = origin"))
    command, authorization = authorized_command(command_id=UUID(int=12345))
    with pytest.raises(RuntimeError, match="forced outbox"):
        _service(app, fail_outbox=True).claim(command, authorization)
    with owner.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM revision_execution_claims WHERE command_id=:command"),
                {"command": UUID(int=12345)},
            )
            == 0
        )
    accepted_command, accepted_authorization = authorized_command(command_id=UUID(int=13000))
    claim = _service(app).claim(accepted_command, accepted_authorization)
    lifecycle_ids = count(13001)
    lifecycle = DurableRevisionLifecycleService(
        _uow_factory(app), id_factory=lambda: UUID(int=next(lifecycle_ids))
    )
    workflow_id = revision_workflow_id(accepted_command.action)
    launched = lifecycle.transition(
        accepted_command,
        RevisionLifecycleCommand(
            UUID(int=13010),
            WORKSPACE,
            claim.claim_id,
            claim.version,
            RevisionExecutionStatus.LAUNCH_PENDING,
            workflow_id,
            NOW + timedelta(minutes=2),
        ),
    )
    rejection = RevisionLifecycleCommand(
        UUID(int=13011),
        WORKSPACE,
        claim.claim_id,
        launched.version,
        RevisionExecutionStatus.FAILED,
        workflow_id,
        NOW + timedelta(minutes=3),
        RevisionLifecycleReason.LAUNCH_REJECTED,
    )
    for operation, fragment in (
        ("run", "UPDATE execution_runs"),
        ("step", "UPDATE execution_steps"),
        ("audit", "INSERT INTO audit_entries"),
        ("outbox", "INSERT INTO outbox_events"),
    ):

        def fail_operation(
            connection: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
            *,
            expected: str = fragment,
            name: str = operation,
        ) -> None:
            if expected in statement:
                raise RuntimeError(f"forced {name} failure")

        event.listen(app, "before_cursor_execute", fail_operation)
        try:
            with pytest.raises(RuntimeError, match=f"forced {operation}"):
                lifecycle.transition(accepted_command, rejection)
        finally:
            event.remove(app, "before_cursor_execute", fail_operation)
        with owner.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT status FROM revision_execution_claims WHERE id=:claim"),
                    {"claim": claim.claim_id},
                )
                == RevisionExecutionStatus.LAUNCH_PENDING.value
            )
            assert connection.execute(
                text(
                    "SELECT r.status,s.status FROM execution_runs r "
                    "JOIN execution_steps s ON s.workspace_id=r.workspace_id "
                    "AND s.run_id=r.id WHERE r.id=:run"
                ),
                {"run": claim.execution_run_id},
            ).one() == ("queued", "pending")
    failed = lifecycle.transition(accepted_command, rejection)
    assert lifecycle.transition(accepted_command, rejection) == failed
    with owner.connect() as connection:
        assert connection.execute(
            text(
                "SELECT status,launch_pending_at IS NOT NULL,running_at,failed_at IS NOT NULL,"
                "lifecycle_reason FROM revision_execution_claims WHERE id=:claim"
            ),
            {"claim": claim.claim_id},
        ).one() == ("failed", True, None, True, "launch_rejected")
        assert connection.execute(
            text(
                "SELECT r.status,r.started_at,s.status,s.started_at "
                "FROM execution_runs r JOIN execution_steps s ON "
                "s.workspace_id=r.workspace_id AND s.run_id=r.id WHERE r.id=:run"
            ),
            {"run": claim.execution_run_id},
        ).one() == ("failed", None, "failed", None)
        assert (
            connection.scalar(
                text("SELECT automated_revision_count FROM quality_gate_states WHERE id=:gate"),
                {"gate": GATE},
            )
            == 1
        )
    with owner.begin() as connection:
        connection.execute(text("SET session_replication_role = replica"))
        for table in (
            "revision_execution_claims",
            "execution_steps",
            "execution_runs",
            "execution_requests",
            "audit_entries",
            "outbox_events",
        ):
            condition = " WHERE id<>:source" if table == "execution_steps" else ""
            connection.execute(text(f"DELETE FROM {table}{condition}"), {"source": STEP})
        connection.execute(text("SET session_replication_role = origin"))


def test_durable_lifecycle_completion_and_reservation_preservation(
    engines: tuple[Engine, Engine],
) -> None:
    owner, app = engines
    command, authorization = authorized_command(command_id=UUID(int=14000))
    claim = _service(app).claim(command, authorization)
    lifecycle_ids = count(14001)
    lifecycle = DurableRevisionLifecycleService(
        _uow_factory(app), id_factory=lambda: UUID(int=next(lifecycle_ids))
    )
    workflow_id = revision_workflow_id(command.action)
    launched = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            UUID(int=14002),
            WORKSPACE,
            claim.claim_id,
            claim.version,
            RevisionExecutionStatus.LAUNCH_PENDING,
            workflow_id,
            NOW + timedelta(minutes=2),
        ),
    )
    reconciled = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            UUID(int=14003),
            WORKSPACE,
            claim.claim_id,
            launched.version,
            RevisionExecutionStatus.RECONCILIATION_REQUIRED,
            workflow_id,
            NOW + timedelta(minutes=3),
            RevisionLifecycleReason.LAUNCH_OUTCOME_UNKNOWN,
        ),
    )
    running = lifecycle.transition(
        command,
        RevisionLifecycleCommand(
            UUID(int=14004),
            WORKSPACE,
            claim.claim_id,
            reconciled.version,
            RevisionExecutionStatus.RUNNING,
            workflow_id,
            NOW + timedelta(minutes=4),
        ),
    )
    activity_authority = SqlAlchemyRevisionActivityAuthority(sessionmaker(app))
    activity_request = _request(running)
    activity_authority.verify(activity_request, workflow_id)
    tampered = {**activity_request, "action_digest": "f" * 64}
    with pytest.raises(RevisionExecutionContractError, match="attestation does not match"):
        activity_authority.verify(tampered, workflow_id)
    payload = canonical_result_payload({"verified": True})
    artifact = ArtifactReference(ARTIFACT, 2, result_digest(payload))
    provenance = ResultProvenance(
        WORKSPACE,
        claim.execution_run_id,
        claim.execution_step_id,
        CORRELATION,
        None,
        CAPABILITY.reference,
        CAPABILITY.output_contract,
        artifact,
        NOW + timedelta(minutes=5),
    )
    validation = ResultValidationEvidence(
        UUID(int=14005),
        CapabilityResult(provenance, payload),
        ValidationCriteriaReference("result.contract", CAPABILITY.reference.semantic_version),
        ResultValidationOutcome.PASSED,
        (ResultValidationReason.ACCEPTED,),
        (EvidenceReference("result.contract", "validation:passed"),),
        NOW + timedelta(minutes=6),
    )
    submission = RevisionArtifactSubmission(
        claim.claim_id,
        WORKSPACE,
        GATE,
        claim.execution_run_id,
        claim.execution_step_id,
        CAPABILITY.reference,
        SOURCE,
        artifact,
        validation.validation_id,
        NOW + timedelta(minutes=5),
    )
    completion = RevisionCompletionCommand(
        UUID(int=14006),
        WORKSPACE,
        claim.claim_id,
        running.version,
        workflow_id,
        submission,
        validation,
        NOW + timedelta(minutes=7),
    )
    for failing_table in ("audit_entries", "outbox_events"):

        def fail_insert(
            connection: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
            *,
            table: str = failing_table,
        ) -> None:
            if f"INSERT INTO {table}" in statement:
                raise RuntimeError(f"forced {table} failure")

        event.listen(app, "before_cursor_execute", fail_insert)
        try:
            with pytest.raises(RuntimeError, match=failing_table):
                lifecycle.complete(command, completion)
        finally:
            event.remove(app, "before_cursor_execute", fail_insert)
        with owner.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT status,result_artifact_id FROM revision_execution_claims "
                    "WHERE id=:claim"
                ),
                {"claim": claim.claim_id},
            ).one() == ("running", None)
            assert (
                connection.scalar(
                    text("SELECT status FROM quality_gate_states WHERE id=:gate"),
                    {"gate": GATE},
                )
                == QualityGateStatus.REVISION_REQUIRED.value
            )
    completed = lifecycle.complete(command, completion)
    assert completed.status is RevisionExecutionStatus.COMPLETED
    assert lifecycle.complete(command, completion) == completed
    with owner.connect() as connection:
        row = connection.execute(
            text(
                "SELECT status,workflow_id,result_artifact_version,"
                "result_validation_evidence_id FROM revision_execution_claims "
                "WHERE id=:claim"
            ),
            {"claim": claim.claim_id},
        ).one()
        assert row == ("completed", workflow_id, 2, validation.validation_id)
        gate_row = connection.execute(
            text("SELECT status,automated_revision_count FROM quality_gate_states WHERE id=:gate"),
            {"gate": GATE},
        ).one()
        assert gate_row == (QualityGateStatus.AWAITING_REVIEW.value, 1)
