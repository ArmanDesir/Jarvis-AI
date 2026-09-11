from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from rightjob.audit.infrastructure.repositories import (
    SqlAlchemyAuditEvidenceRepository,
    SqlAlchemyOutboxRepository,
)
from rightjob.contracts.authorization import ExecutionAuthorizationReference
from rightjob.contracts.events import (
    Actor,
    ActorType,
    AuditEvidence,
    AuditOutcome,
    DataSensitivity,
    IntegrationEvent,
)
from rightjob.database import register_sqlalchemy_mappings
from rightjob.orchestration.application.repositories import ConcurrentExecutionUpdateError
from rightjob.orchestration.domain import (
    ExecutionRequest,
    ExecutionRun,
    ExecutionStep,
    InitiatorType,
    RequestedStep,
    RunStatus,
    StepStatus,
)
from rightjob.orchestration.infrastructure.repositories import (
    SqlAlchemyExecutionRequestRepository,
    SqlAlchemyExecutionRunRepository,
    SqlAlchemyExecutionStepRepository,
)
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

OWNER_URL = os.environ.get("RIGHTJOB_DATABASE_URL")
APP_URL = os.environ.get("RIGHTJOB_PHASE27_RLS_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not OWNER_URL or not APP_URL, reason="isolated Phase 2.7 URLs required"),
]

WORKSPACE_A = UUID("0198ff00-0000-7000-8000-000000000001")
WORKSPACE_B = UUID("0198ff00-0000-7000-8000-000000000002")
USER_A = UUID("0198ff00-0000-7000-8000-000000000011")
USER_B = UUID("0198ff00-0000-7000-8000-000000000012")
MEMBERSHIP_A = UUID("0198ff00-0000-7000-8000-000000000021")
MEMBERSHIP_B = UUID("0198ff00-0000-7000-8000-000000000022")

REQUEST_A = UUID("02700000-0000-4000-8000-000000000001")
REQUEST_B = UUID("02700000-0000-4000-8000-000000000002")
REQUEST_ROLLBACK = UUID("02700000-0000-4000-8000-000000000003")
REQUEST_DUPLICATE = UUID("02700000-0000-4000-8000-000000000004")
RUN_A = UUID("02700000-0000-4000-8000-000000000011")
RUN_B = UUID("02700000-0000-4000-8000-000000000012")
RUN_ROLLBACK = UUID("02700000-0000-4000-8000-000000000013")
RUN_DUPLICATE = UUID("02700000-0000-4000-8000-000000000014")
STEPS_A = tuple(UUID(f"02700000-0000-4000-8000-00000000002{number}") for number in range(1, 4))
STEPS_B = tuple(UUID(f"02700000-0000-4000-8000-00000000002{number}") for number in range(4, 7))
STEP_ROLLBACK = UUID("02700000-0000-4000-8000-000000000027")

AUDIT_CREATED = UUID("02700000-0000-4000-8000-000000000101")
AUDIT_STEP_STARTED = UUID("02700000-0000-4000-8000-000000000102")
AUDIT_CANCELLED = UUID("02700000-0000-4000-8000-000000000103")
AUDIT_RECONCILIATION = UUID("02700000-0000-4000-8000-000000000104")
AUDIT_ISOLATION_B = UUID("02700000-0000-4000-8000-000000000105")
AUDIT_ROLLBACK = UUID("02700000-0000-4000-8000-000000000106")
OUTBOX_CREATED = UUID("02700000-0000-4000-8000-000000000201")
OUTBOX_STEP_STARTED = UUID("02700000-0000-4000-8000-000000000202")
OUTBOX_CANCELLED = UUID("02700000-0000-4000-8000-000000000203")
OUTBOX_RECONCILIATION = UUID("02700000-0000-4000-8000-000000000204")
OUTBOX_ISOLATION_B = UUID("02700000-0000-4000-8000-000000000205")
OUTBOX_ROLLBACK = UUID("02700000-0000-4000-8000-000000000206")

APP_ROLE = "rightjob_phase27_rls_verifier"
NOW = datetime(2026, 8, 12, 8, tzinfo=timezone.utc)
CORRELATION = UUID("02700000-0000-4000-8000-000000000001")
CAUSATION = UUID("02700000-0000-4000-8000-000000000002")
DEFINITION = UUID("02700000-0000-4000-8000-000000000001")
STEP_TYPES = ("fake.prepare", "fake.transform", "fake.verify")


def _request(request_id: UUID, workspace_id: UUID) -> ExecutionRequest:
    step_ids = STEPS_A if workspace_id == WORKSPACE_A else STEPS_B
    return ExecutionRequest(
        execution_id=request_id,
        workspace_id=workspace_id,
        correlation_id=CORRELATION,
        causation_id=CAUSATION,
        actor=Actor(ActorType.USER, str(USER_A if workspace_id == WORKSPACE_A else USER_B)),
        initiator_type=InitiatorType.USER,
        authorization=ExecutionAuthorizationReference(
            request_id, workspace_id, UUID(int=89), "0" * 64
        ),
        workflow_definition_id=DEFINITION,
        workflow_type="synthetic.sequence",
        workflow_version="1.0.0",
        steps=tuple(
            RequestedStep(step_ids[index], step_type, index, f"request:{request_id}:{index}")
            for index, step_type in enumerate(STEP_TYPES)
        ),
        input={"value": "synthetic"},
        created_at=NOW,
    )


def _run(run_id: UUID, request: ExecutionRequest) -> ExecutionRun:
    return ExecutionRun(
        id=run_id,
        execution_request_id=request.execution_id,
        workspace_id=request.workspace_id,
        workflow_definition_id=request.workflow_definition_id,
        workflow_type=request.workflow_type,
        workflow_version=request.workflow_version,
        status=RunStatus.QUEUED,
        correlation_id=request.correlation_id,
        causation_id=request.causation_id,
        actor=request.actor,
        initiator_type=request.initiator_type,
        created_at=NOW,
    )


def _steps(run: ExecutionRun, ids: Sequence[UUID]) -> tuple[ExecutionStep, ...]:
    return tuple(
        ExecutionStep(
            id=step_id,
            run_id=run.id,
            workspace_id=run.workspace_id,
            step_type=STEP_TYPES[index],
            sequence=index,
            status=StepStatus.PENDING,
            attempt_count=0,
            max_attempts=1,
            input_ref=f"request:{run.execution_request_id}:{index}",
        )
        for index, step_id in enumerate(ids)
    )


def _audit(evidence_id: UUID, workspace_id: UUID, action: str, resource_id: UUID) -> AuditEvidence:
    return AuditEvidence(
        id=evidence_id,
        workspace_id=workspace_id,
        actor=Actor(ActorType.USER, str(USER_A if workspace_id == WORKSPACE_A else USER_B)),
        action=action,
        resource_type="execution_run",
        resource_id=str(resource_id),
        outcome=AuditOutcome.SUCCEEDED,
        correlation_id=CORRELATION,
        causation_id=CAUSATION,
        occurred_at=NOW,
        after={"run_id": str(resource_id)},
    )


def _event(event_id: UUID, workspace_id: UUID, event_type: str, key: str) -> IntegrationEvent:
    return IntegrationEvent(
        event_id=event_id,
        event_type=event_type,
        event_version=1,
        schema_version=1,
        occurred_at=NOW,
        workspace_id=workspace_id,
        actor=Actor(ActorType.USER, str(USER_A if workspace_id == WORKSPACE_A else USER_B)),
        correlation_id=CORRELATION,
        causation_id=CAUSATION,
        producer="orchestration",
        sensitivity=DataSensitivity.INTERNAL,
        payload={"workspace_id": str(workspace_id)},
        idempotency_key=key,
    )


@contextmanager
def _context(engine: Engine, workspace_id: UUID | None) -> Iterator[Connection]:
    with engine.begin() as connection:
        if workspace_id is not None:
            connection.execute(
                text("SELECT set_config('app.current_workspace_id', :workspace_id, true)"),
                {"workspace_id": str(workspace_id)},
            )
        yield connection


def _insert_identity(connection: Connection) -> None:
    connection.execute(
        text(
            "INSERT INTO workspaces (id,name,slug,status,timezone,locale,settings) VALUES "
            "(:wa,'Workspace A','phase27-workspace-a','active','UTC','en','{}'),"
            "(:wb,'Workspace B','phase27-workspace-b','active','UTC','en','{}')"
        ),
        {"wa": WORKSPACE_A, "wb": WORKSPACE_B},
    )
    connection.execute(
        text(
            "INSERT INTO users "
            "(id,external_identity_provider,external_subject,email,display_name,status) VALUES "
            "(:ua,'phase27','a','phase27-a@example.test','A','active'),"
            "(:ub,'phase27','b','phase27-b@example.test','B','active')"
        ),
        {"ua": USER_A, "ub": USER_B},
    )
    connection.execute(
        text(
            "INSERT INTO memberships (id,workspace_id,user_id,role,status) VALUES "
            "(:ma,:wa,:ua,'owner','active'),(:mb,:wb,:ub,'owner','active')"
        ),
        {
            "ma": MEMBERSHIP_A,
            "mb": MEMBERSHIP_B,
            "wa": WORKSPACE_A,
            "wb": WORKSPACE_B,
            "ua": USER_A,
            "ub": USER_B,
        },
    )


def _insert_execution(
    session: Session,
    request: ExecutionRequest,
    run: ExecutionRun,
    steps: Sequence[ExecutionStep],
) -> None:
    SqlAlchemyExecutionRequestRepository(session).add(request.workspace_id, request)
    SqlAlchemyExecutionRunRepository(session).add(run.workspace_id, run)
    SqlAlchemyExecutionStepRepository(session).add_all(run.workspace_id, steps)


def _cleanup(connection: Connection) -> None:
    approved = {
        "step_ids": (*STEPS_A, *STEPS_B, STEP_ROLLBACK),
        "run_ids": (RUN_A, RUN_B, RUN_ROLLBACK, RUN_DUPLICATE),
        "request_ids": (REQUEST_A, REQUEST_B, REQUEST_ROLLBACK, REQUEST_DUPLICATE),
        "audit_ids": (
            AUDIT_CREATED,
            AUDIT_STEP_STARTED,
            AUDIT_CANCELLED,
            AUDIT_RECONCILIATION,
            AUDIT_ISOLATION_B,
            AUDIT_ROLLBACK,
        ),
        "outbox_ids": (
            OUTBOX_CREATED,
            OUTBOX_STEP_STARTED,
            OUTBOX_CANCELLED,
            OUTBOX_RECONCILIATION,
            OUTBOX_ISOLATION_B,
            OUTBOX_ROLLBACK,
        ),
    }
    for table, parameter in (
        ("execution_steps", "step_ids"),
        ("execution_runs", "run_ids"),
        ("execution_requests", "request_ids"),
        ("audit_entries", "audit_ids"),
        ("outbox_events", "outbox_ids"),
    ):
        connection.execute(
            text(f"DELETE FROM {table} WHERE id = ANY(:ids)"), {"ids": list(approved[parameter])}
        )
    connection.execute(
        text("DELETE FROM execution_authorizations WHERE id = ANY(:ids)"),
        {
            "ids": [
                REQUEST_A,
                REQUEST_B,
                REQUEST_ROLLBACK,
                REQUEST_DUPLICATE,
            ]
        },
    )
    connection.execute(
        text("DELETE FROM memberships WHERE id = ANY(:ids)"),
        {"ids": [MEMBERSHIP_A, MEMBERSHIP_B]},
    )
    connection.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": [USER_A, USER_B]})
    connection.execute(
        text("DELETE FROM workspaces WHERE id = ANY(:ids)"),
        {"ids": [WORKSPACE_A, WORKSPACE_B]},
    )


def _drop_role(connection: Connection) -> None:
    for table in (
        "execution_requests",
        "execution_runs",
        "execution_steps",
        "audit_entries",
        "outbox_events",
    ):
        connection.execute(text(f"REVOKE ALL ON {table} FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE ALL ON SCHEMA public FROM {APP_ROLE}"))
    connection.execute(text(f"REVOKE CONNECT ON DATABASE rightjob_phase220 FROM {APP_ROLE}"))
    connection.execute(text(f"DROP ROLE {APP_ROLE}"))


@pytest.fixture(scope="module")
def phase27_engines() -> Iterator[tuple[Engine, Engine]]:
    assert OWNER_URL and APP_URL
    register_sqlalchemy_mappings()
    owner = create_engine(OWNER_URL)
    app = create_engine(APP_URL)
    try:
        with owner.begin() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20260827_0006"
            )
            assert connection.execute(
                text(
                    "SELECT (SELECT count(*) FROM workspaces),(SELECT count(*) FROM users),"
                    "(SELECT count(*) FROM memberships),(SELECT count(*) FROM audit_entries),"
                    "(SELECT count(*) FROM outbox_events),"
                    "(SELECT count(*) FROM execution_requests),"
                    "(SELECT count(*) FROM execution_runs),(SELECT count(*) FROM execution_steps)"
                )
            ).one() == (0, 0, 0, 0, 0, 0, 0, 0)
            assert not connection.scalar(
                text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:role)"),
                {"role": APP_ROLE},
            )
            connection.execute(
                text(
                    f"CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOBYPASSRLS"
                )
            )
            connection.execute(text(f"GRANT CONNECT ON DATABASE rightjob_phase220 TO {APP_ROLE}"))
            connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
            connection.execute(text(f"GRANT SELECT, INSERT ON execution_requests TO {APP_ROLE}"))
            connection.execute(
                text(f"GRANT SELECT, INSERT, UPDATE ON execution_runs TO {APP_ROLE}")
            )
            connection.execute(
                text(f"GRANT SELECT, INSERT, UPDATE ON execution_steps TO {APP_ROLE}")
            )
            connection.execute(text(f"GRANT SELECT, INSERT ON audit_entries TO {APP_ROLE}"))
            connection.execute(text(f"GRANT SELECT, INSERT ON outbox_events TO {APP_ROLE}"))
            _insert_identity(connection)
            authorization_insert = text(
                "INSERT INTO execution_authorizations "
                "(id,workspace_id,planning_request_id,plan_id,workflow_definition_id,"
                "workflow_type,workflow_version,plan_digest,digest_algorithm,"
                "authorization_version,issued_at,expires_at,correlation_id,causation_id,"
                "idempotency_key) VALUES "
                "(:id,:workspace,:planning,:plan,:definition,'synthetic.sequence','1.0.0',"
                ":digest,'sha256',1,:issued,:expires,:correlation,:causation,:key)"
            )
            connection.execute(
                authorization_insert,
                [
                    {
                        "id": request_id,
                        "workspace": workspace_id,
                        "planning": UUID(int=91),
                        "plan": UUID(int=92),
                        "definition": DEFINITION,
                        "digest": "0" * 64,
                        "issued": NOW,
                        "expires": NOW + timedelta(hours=1),
                        "correlation": CORRELATION,
                        "causation": CAUSATION,
                        "key": f"phase27-{request_id}",
                    }
                    for request_id, workspace_id in (
                        (REQUEST_A, WORKSPACE_A),
                        (REQUEST_B, WORKSPACE_B),
                        (REQUEST_ROLLBACK, WORKSPACE_A),
                        (REQUEST_DUPLICATE, WORKSPACE_A),
                    )
                ],
            )
            request_b = _request(REQUEST_B, WORKSPACE_B)
            run_b = _run(RUN_B, request_b)
            session = Session(bind=connection)
            _insert_execution(session, request_b, run_b, _steps(run_b, STEPS_B))
            SqlAlchemyAuditEvidenceRepository(session).append(
                WORKSPACE_B, _audit(AUDIT_ISOLATION_B, WORKSPACE_B, "run.created", RUN_B)
            )
            SqlAlchemyOutboxRepository(session).add(
                WORKSPACE_B,
                _event(
                    OUTBOX_ISOLATION_B,
                    WORKSPACE_B,
                    "execution.run.created.v1",
                    "run-b-created",
                ),
            )
            session.flush()
        yield owner, app
    finally:
        app.dispose()
        with owner.begin() as connection:
            _cleanup(connection)
            _drop_role(connection)
        owner.dispose()


def test_atomic_creation_commits_request_run_steps_audit_outbox_once(
    phase27_engines: tuple[Engine, Engine],
) -> None:
    owner, app = phase27_engines
    commits = 0

    def count_commit(_: Session) -> None:
        nonlocal commits
        commits += 1

    request = _request(REQUEST_A, WORKSPACE_A)
    run = _run(RUN_A, request)
    with Session(app) as session:
        event.listen(session, "after_commit", count_commit)
        _insert_execution(session, request, run, _steps(run, STEPS_A))
        SqlAlchemyAuditEvidenceRepository(session).append(
            WORKSPACE_A, _audit(AUDIT_CREATED, WORKSPACE_A, "run.created", RUN_A)
        )
        SqlAlchemyOutboxRepository(session).add(
            WORKSPACE_A,
            _event(OUTBOX_CREATED, WORKSPACE_A, "execution.run.created.v1", "run-a-created"),
        )
        session.commit()
        event.remove(session, "after_commit", count_commit)
    assert commits == 1
    with owner.connect() as connection:
        assert connection.execute(
            text(
                "SELECT (SELECT count(*) FROM execution_requests WHERE id=:request),"
                "(SELECT count(*) FROM execution_runs WHERE id=:run),"
                "(SELECT count(*) FROM execution_steps WHERE run_id=:run),"
                "(SELECT count(*) FROM audit_entries WHERE id=:audit),"
                "(SELECT count(*) FROM outbox_events WHERE id=:outbox)"
            ),
            {
                "request": REQUEST_A,
                "run": RUN_A,
                "audit": AUDIT_CREATED,
                "outbox": OUTBOX_CREATED,
            },
        ).one() == (1, 1, 3, 1, 1)


def test_rollback_leaves_no_partial_persistence(
    phase27_engines: tuple[Engine, Engine],
) -> None:
    owner, app = phase27_engines
    request = _request(REQUEST_ROLLBACK, WORKSPACE_A)
    run = _run(RUN_ROLLBACK, request)
    step = ExecutionStep(
        STEP_ROLLBACK,
        RUN_ROLLBACK,
        WORKSPACE_A,
        "fake.prepare",
        0,
        StepStatus.PENDING,
        0,
        1,
        "rollback:0",
    )
    with pytest.raises(RuntimeError, match="rollback proof"), Session(app) as session:
        _insert_execution(session, request, run, (step,))
        SqlAlchemyAuditEvidenceRepository(session).append(
            WORKSPACE_A, _audit(AUDIT_ROLLBACK, WORKSPACE_A, "run.created", RUN_ROLLBACK)
        )
        SqlAlchemyOutboxRepository(session).add(
            WORKSPACE_A,
            _event(OUTBOX_ROLLBACK, WORKSPACE_A, "execution.run.created.v1", "rollback"),
        )
        raise RuntimeError("rollback proof")
    with owner.connect() as connection:
        assert connection.execute(
            text(
                "SELECT (SELECT count(*) FROM execution_requests WHERE id=:request),"
                "(SELECT count(*) FROM execution_runs WHERE id=:run),"
                "(SELECT count(*) FROM execution_steps WHERE id=:step),"
                "(SELECT count(*) FROM audit_entries WHERE id=:audit),"
                "(SELECT count(*) FROM outbox_events WHERE id=:outbox)"
            ),
            {
                "request": REQUEST_ROLLBACK,
                "run": RUN_ROLLBACK,
                "step": STEP_ROLLBACK,
                "audit": AUDIT_ROLLBACK,
                "outbox": OUTBOX_ROLLBACK,
            },
        ).one() == (0, 0, 0, 0, 0)


def test_duplicate_request_run_and_sequence_are_rejected(
    phase27_engines: tuple[Engine, Engine],
) -> None:
    _, app = phase27_engines
    with Session(app) as session:
        with pytest.raises(IntegrityError, match="pk_execution_requests"):
            SqlAlchemyExecutionRequestRepository(session).add(
                WORKSPACE_A, _request(REQUEST_A, WORKSPACE_A)
            )
            session.commit()
        session.rollback()

    request = _request(REQUEST_DUPLICATE, WORKSPACE_A)
    run = _run(RUN_DUPLICATE, request)
    with Session(app) as session:
        SqlAlchemyExecutionRequestRepository(session).add(WORKSPACE_A, request)
        SqlAlchemyExecutionRunRepository(session).add(WORKSPACE_A, run)
        SqlAlchemyExecutionRunRepository(session).add(WORKSPACE_A, _run(RUN_ROLLBACK, request))
        with pytest.raises(IntegrityError, match="uq_execution_runs_workspace_request"):
            session.commit()
        session.rollback()

    duplicate_sequence = ExecutionStep(
        STEP_ROLLBACK,
        RUN_A,
        WORKSPACE_A,
        "fake.prepare",
        0,
        StepStatus.PENDING,
        0,
        1,
        "duplicate:0",
    )
    with Session(app) as session:
        SqlAlchemyExecutionStepRepository(session).add_all(WORKSPACE_A, (duplicate_sequence,))
        with pytest.raises(IntegrityError, match="uq_execution_steps_workspace_run_sequence"):
            session.commit()
        session.rollback()


def test_optimistic_concurrency_for_run_and_step_and_atomic_step_event(
    phase27_engines: tuple[Engine, Engine],
) -> None:
    _, app = phase27_engines
    with Session(app) as session:
        runs = SqlAlchemyExecutionRunRepository(session)
        original_run = runs.get(WORKSPACE_A, RUN_A)
        assert original_run is not None
        running = original_run.transition(RunStatus.RUNNING, NOW)
        runs.save(WORKSPACE_A, running, original_run.version)
        session.commit()
    with Session(app) as session:
        with pytest.raises(ConcurrentExecutionUpdateError):
            SqlAlchemyExecutionRunRepository(session).save(
                WORKSPACE_A,
                original_run.transition(RunStatus.RUNNING, NOW),
                original_run.version,
            )
        session.rollback()

    with Session(app) as session:
        steps = SqlAlchemyExecutionStepRepository(session)
        original_step = steps.get(WORKSPACE_A, STEPS_A[0])
        assert original_step is not None
        started = original_step.transition(StepStatus.RUNNING, NOW)
        steps.save(WORKSPACE_A, started, original_step.version)
        SqlAlchemyAuditEvidenceRepository(session).append(
            WORKSPACE_A, _audit(AUDIT_STEP_STARTED, WORKSPACE_A, "step.started", RUN_A)
        )
        SqlAlchemyOutboxRepository(session).add(
            WORKSPACE_A,
            _event(
                OUTBOX_STEP_STARTED,
                WORKSPACE_A,
                "execution.step.started.v1",
                "step-a-started",
            ),
        )
        session.commit()
    with Session(app) as session:
        with pytest.raises(ConcurrentExecutionUpdateError):
            SqlAlchemyExecutionStepRepository(session).save(
                WORKSPACE_A,
                original_step.transition(StepStatus.RUNNING, NOW),
                original_step.version,
            )
        session.rollback()


def test_reconciliation_and_cancellation_are_canonical_and_idempotent(
    phase27_engines: tuple[Engine, Engine],
) -> None:
    _, app = phase27_engines
    with Session(app) as session:
        runs = SqlAlchemyExecutionRunRepository(session)
        running = runs.get(WORKSPACE_A, RUN_A)
        assert running is not None
        reconciliation = running.transition(RunStatus.RECONCILIATION_REQUIRED, NOW)
        runs.save(WORKSPACE_A, reconciliation, running.version)
        SqlAlchemyAuditEvidenceRepository(session).append(
            WORKSPACE_A,
            _audit(AUDIT_RECONCILIATION, WORKSPACE_A, "reconciliation.required", RUN_A),
        )
        SqlAlchemyOutboxRepository(session).add(
            WORKSPACE_A,
            _event(
                OUTBOX_RECONCILIATION,
                WORKSPACE_A,
                "execution.reconciliation.required.v1",
                "run-a-reconciliation",
            ),
        )
        session.commit()

    with Session(app) as session:
        runs = SqlAlchemyExecutionRunRepository(session)
        reconciliation = runs.get(WORKSPACE_A, RUN_A)
        assert reconciliation is not None
        requested = reconciliation.request_cancellation(NOW)
        assert requested.request_cancellation(NOW) is requested
        runs.save(WORKSPACE_A, requested, reconciliation.version)
        session.flush()
        cancelled = requested.transition(RunStatus.CANCELLED, NOW)
        runs.save(WORKSPACE_A, cancelled, requested.version)
        SqlAlchemyAuditEvidenceRepository(session).append(
            WORKSPACE_A, _audit(AUDIT_CANCELLED, WORKSPACE_A, "run.cancelled", RUN_A)
        )
        SqlAlchemyOutboxRepository(session).add(
            WORKSPACE_A,
            _event(OUTBOX_CANCELLED, WORKSPACE_A, "execution.run.cancelled.v1", "run-a-cancelled"),
        )
        session.commit()
    with Session(app) as session:
        stored = SqlAlchemyExecutionRunRepository(session).get(WORKSPACE_A, RUN_A)
        assert stored is not None
        assert stored.status is RunStatus.CANCELLED
        assert stored.cancelled_at == NOW
        assert stored.request_cancellation(NOW) is stored


def test_workspace_and_missing_context_fail_closed_and_rls_is_forced(
    phase27_engines: tuple[Engine, Engine],
) -> None:
    owner, app = phase27_engines
    with owner.connect() as connection:
        rls_inventory = [
            tuple(row)
            for row in connection.execute(
                text(
                    "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class "
                    "WHERE relname IN "
                    "('execution_requests','execution_runs','execution_steps') "
                    "ORDER BY relname"
                )
            )
        ]
        assert rls_inventory == [
            ("execution_requests", True, True),
            ("execution_runs", True, True),
            ("execution_steps", True, True),
        ]
    with _context(app, WORKSPACE_A) as connection:
        visible_workspaces = set(
            connection.execute(text("SELECT workspace_id FROM execution_runs")).scalars()
        )
        assert visible_workspaces == {WORKSPACE_A}
        assert (
            connection.execute(
                text("UPDATE execution_runs SET status='cancelled' WHERE id=:id"), {"id": RUN_B}
            ).rowcount
            == 0
        )
    with _context(app, None) as connection:
        assert connection.execute(text("SELECT id FROM execution_requests")).all() == []
        assert connection.execute(text("SELECT id FROM execution_runs")).all() == []
        assert connection.execute(text("SELECT id FROM execution_steps")).all() == []
    with (
        pytest.raises(DBAPIError, match="row-level security"),
        _context(app, WORKSPACE_A) as connection,
    ):
        connection.execute(
            text(
                "INSERT INTO execution_requests "
                "(id,workspace_id,correlation_id,actor_type,actor_id,initiator_type,"
                "workflow_definition_id,workflow_type,workflow_version,input_json,created_at) "
                "VALUES (:id,:wb,:correlation,'user','user-a','user',:definition,"
                "'synthetic.sequence','1.0.0','{}',:now)"
            ),
            {
                "id": REQUEST_ROLLBACK,
                "wb": WORKSPACE_B,
                "correlation": CORRELATION,
                "definition": DEFINITION,
                "now": NOW,
            },
        )


def test_audit_append_only_and_outbox_idempotency(
    phase27_engines: tuple[Engine, Engine],
) -> None:
    owner, app = phase27_engines
    with (
        pytest.raises(ProgrammingError, match="permission denied"),
        _context(app, WORKSPACE_A) as connection,
    ):
        connection.execute(
            text("UPDATE audit_entries SET outcome='failed' WHERE id=:id"),
            {"id": AUDIT_CREATED},
        )
    with (
        pytest.raises(ProgrammingError, match="permission denied"),
        _context(app, WORKSPACE_A) as connection,
    ):
        connection.execute(text("DELETE FROM audit_entries WHERE id=:id"), {"id": AUDIT_CREATED})

    with Session(app) as session:
        SqlAlchemyOutboxRepository(session).add(
            WORKSPACE_A,
            _event(OUTBOX_ROLLBACK, WORKSPACE_A, "execution.run.created.v1", "run-a-created"),
        )
        with pytest.raises(IntegrityError, match="uq_outbox_events_workspace_idempotency"):
            session.commit()
        session.rollback()
    with owner.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM outbox_events "
                    "WHERE workspace_id=:workspace AND idempotency_key=:key"
                ),
                {"workspace": WORKSPACE_A, "key": "run-a-created"},
            )
            == 1
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM outbox_events WHERE id=:id"), {"id": OUTBOX_ROLLBACK}
            )
            == 0
        )
