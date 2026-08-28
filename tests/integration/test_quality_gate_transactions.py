from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from uuid import UUID

import pytest
from rightjob.audit.infrastructure.repositories import (
    SqlAlchemyAuditEvidenceRepository,
    SqlAlchemyOutboxRepository,
)
from rightjob.contracts.revision import QualityGateContractError
from rightjob.orchestration.application.quality_gate import (
    DurableQualityGateService,
    QualityGateDecisionService,
)
from rightjob.orchestration.infrastructure.unit_of_work import SqlAlchemyExecutionUnitOfWork
from rightjob.registry.catalog import BuiltInCapabilityRegistry
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from tests.unit.test_quality_gate import (
    GATE,
    RUN,
    STEP,
    WORKSPACE,
    assessment,
    command,
    validation,
)

OWNER_URL = os.environ.get("RIGHTJOB_DATABASE_URL")
APP_URL = os.environ.get("RIGHTJOB_PHASE219_RLS_DATABASE_URL")
APP_ROLE = "rightjob_phase219_verifier"
WORKSPACE_B = UUID("00000000-0000-4000-8000-000000000299")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not OWNER_URL or not APP_URL, reason="isolated Phase 2.19 URLs required"),
]


class _UnusedAuthorization:
    pass


class _FailingAppender:
    def append(self, workspace_id: UUID, evidence: object) -> None:
        raise RuntimeError("forced audit failure")


class _FailingOutbox:
    def add(self, workspace_id: UUID, event: object) -> None:
        raise RuntimeError("forced outbox failure")


def _uow_factory(app: Engine, *, failure: str | None = None):
    sessions = sessionmaker(app, expire_on_commit=False)

    def factory() -> SqlAlchemyExecutionUnitOfWork:
        return SqlAlchemyExecutionUnitOfWork(
            sessions,
            (lambda session: _FailingAppender())
            if failure == "audit"
            else (lambda session: SqlAlchemyAuditEvidenceRepository(session)),
            (lambda session: _FailingOutbox())
            if failure == "outbox"
            else (lambda session: SqlAlchemyOutboxRepository(session)),
            lambda session: _UnusedAuthorization(),  # type: ignore[arg-type]
        )

    return factory


def _service(app: Engine, *, failure: str | None = None) -> DurableQualityGateService:
    ids = iter(UUID(int=value) for value in range(9000, 9100))
    return DurableQualityGateService(
        QualityGateDecisionService(BuiltInCapabilityRegistry()),
        _uow_factory(app, failure=failure),
        lambda: next(ids),
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
    with owner.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260827_0005"
        connection.execute(
            text(
                "INSERT INTO workspaces (id,name,slug) VALUES "
                "(:a,'Quality A','phase219-quality-a'),(:b,'Quality B','phase219-quality-b')"
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
        connection.execute(text(f"GRANT CONNECT ON DATABASE rightjob_phase219 TO {APP_ROLE}"))
        connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
        connection.execute(text(f"GRANT SELECT ON execution_steps TO {APP_ROLE}"))
        connection.execute(text(f"GRANT SELECT,INSERT,UPDATE ON quality_gate_states TO {APP_ROLE}"))
        connection.execute(text(f"GRANT SELECT,INSERT ON quality_gate_decisions TO {APP_ROLE}"))
        connection.execute(
            text(f"GRANT SELECT,INSERT ON audit_entries,outbox_events TO {APP_ROLE}")
        )
    try:
        yield owner, app
    finally:
        app.dispose()
        with owner.begin() as connection:
            connection.execute(text("DELETE FROM quality_gate_decisions"))
            connection.execute(text("DELETE FROM quality_gate_states"))
            connection.execute(text("DELETE FROM audit_entries"))
            connection.execute(text("DELETE FROM outbox_events"))
            connection.execute(text("SET session_replication_role = replica"))
            connection.execute(text("DELETE FROM execution_steps WHERE id=:step"), {"step": STEP})
            connection.execute(text("SET session_replication_role = origin"))
            connection.execute(
                text("DELETE FROM workspaces WHERE id IN (:a,:b)"),
                {"a": WORKSPACE, "b": WORKSPACE_B},
            )
            connection.execute(text(f"DROP OWNED BY {APP_ROLE}"))
            connection.execute(text(f"DROP ROLE {APP_ROLE}"))
        owner.dispose()


def test_schema_rls_constraints_and_cross_workspace_denial(
    engines: tuple[Engine, Engine],
) -> None:
    owner, app = engines
    with owner.connect() as connection:
        assert connection.execute(
            text(
                "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname "
                "IN ('quality_gate_states','quality_gate_decisions') ORDER BY relname"
            )
        ).all() == [
            ("quality_gate_decisions", True, True),
            ("quality_gate_states", True, True),
        ]
    with _context(app, WORKSPACE_B) as connection:
        assert connection.execute(text("SELECT id FROM quality_gate_states")).all() == []
    with (
        pytest.raises(DBAPIError, match="row-level security"),
        _context(app, WORKSPACE_B) as connection,
    ):
        connection.execute(
            text(
                "INSERT INTO quality_gate_states "
                "(id,workspace_id,run_id,step_id,correlation_id,capability_definition_id,"
                "capability_key,capability_version,policy_key,policy_version,criteria_key,"
                "criteria_version,score_key,status,automated_revision_count,minimum_score,"
                "last_score,last_artifact_id,last_artifact_version,last_artifact_sha256,"
                "last_validation_id,last_assessment_id,last_decision_id,version,"
                "created_at,updated_at) "
                "VALUES (:gate,:workspace,:run,:step,:gate,:gate,'fake.verify','1.0.0','p','1.0.0',"
                "'c','1.0.0','s','accepted',0,80,80,:gate,1,:sha,:gate,:gate,:gate,1,now(),now())"
            ),
            {"gate": GATE, "workspace": WORKSPACE, "run": RUN, "step": STEP, "sha": "0" * 64},
        )


@pytest.mark.parametrize("failure", ["audit", "outbox"])
def test_atomic_failure_rolls_back_state_decision_audit_and_outbox(
    engines: tuple[Engine, Engine],
    failure: str,
) -> None:
    owner, app = engines
    item = validation()
    with pytest.raises(RuntimeError, match=f"forced {failure}"):
        _service(app, failure=failure).decide(command(), item, assessment(item, 50))
    with owner.connect() as connection:
        assert connection.execute(
            text(
                "SELECT (SELECT count(*) FROM quality_gate_states),"
                "(SELECT count(*) FROM quality_gate_decisions),"
                "(SELECT count(*) FROM audit_entries),(SELECT count(*) FROM outbox_events)"
            )
        ).one() == (0, 0, 0, 0)


def test_reservations_idempotency_safe_evidence_and_terminal_protection(
    engines: tuple[Engine, Engine],
) -> None:
    owner, app = engines
    service = _service(app)
    first_validation = validation()
    unsafe = assessment(
        first_validation,
        50,
        reason="credential=synthetic-secret execute shell",
        reference="raw provider response prompt",
    )
    first = service.decide(command(), first_validation, unsafe)
    assert first.next_state.automated_revision_count == 1
    assert service.decide(command(), first_validation, unsafe) == first
    with pytest.raises(QualityGateContractError, match="conflicting duplicate"):
        service.decide(
            replace(command(), issued_at=command().issued_at.replace(microsecond=1)),
            first_validation,
            unsafe,
        )
    with owner.begin() as connection:
        assert connection.execute(
            text(
                "SELECT (SELECT count(*) FROM quality_gate_states),"
                "(SELECT count(*) FROM quality_gate_decisions),"
                "(SELECT count(*) FROM audit_entries),(SELECT count(*) FROM outbox_events)"
            )
        ).one() == (1, 1, 1, 1)
        durable = connection.execute(
            text(
                "SELECT row_to_json(s)::text FROM quality_gate_states s UNION ALL "
                "SELECT row_to_json(d)::text FROM quality_gate_decisions d UNION ALL "
                "SELECT row_to_json(a)::text FROM audit_entries a UNION ALL "
                "SELECT row_to_json(o)::text FROM outbox_events o"
            )
        ).scalars()
        assert all(
            "synthetic-secret" not in value and "raw provider" not in value for value in durable
        )
        connection.execute(
            text("UPDATE quality_gate_states SET status='awaiting_review' WHERE id=:gate"),
            {"gate": GATE},
        )
    second_validation = validation(2, "second")
    second_command = command(
        expected_version=1,
        command_id=UUID(int=3002),
        artifact=second_validation.provenance.artifact,
    )
    second = service.decide(second_command, second_validation, assessment(second_validation, 60))
    assert second.next_state.automated_revision_count == 2
    with owner.begin() as connection:
        connection.execute(
            text("UPDATE quality_gate_states SET status='awaiting_review' WHERE id=:gate"),
            {"gate": GATE},
        )
    third_validation = validation(3, "third")
    third = service.decide(
        command(
            expected_version=2,
            command_id=UUID(int=3003),
            artifact=third_validation.provenance.artifact,
        ),
        third_validation,
        assessment(third_validation, 70),
    )
    assert third.next_state.automated_revision_count == 2
    assert third.outcome.value == "needs_human_review"
    fourth_validation = validation(4, "fourth")
    with pytest.raises(QualityGateContractError, match="not awaiting review"):
        service.decide(
            command(
                expected_version=3,
                command_id=UUID(int=3004),
                artifact=fourth_validation.provenance.artifact,
            ),
            fourth_validation,
            assessment(fourth_validation, 75),
        )


def test_append_only_repository_and_stale_version_fail_closed(
    engines: tuple[Engine, Engine],
) -> None:
    _, app = engines
    with (
        pytest.raises(ProgrammingError, match="permission denied"),
        _context(app, WORKSPACE) as connection,
    ):
        connection.execute(text("UPDATE quality_gate_decisions SET outcome='accepted'"))
    with Session(app) as session:
        result = session.execute(
            text(
                "UPDATE quality_gate_states SET last_score=last_score "
                "WHERE workspace_id=:workspace AND id=:gate AND version=1"
            ),
            {"workspace": WORKSPACE, "gate": GATE},
        )
        assert result.rowcount == 0
        session.rollback()
