import os
from dataclasses import replace
from uuid import UUID

import pytest
from rightjob.identity.application.repositories import ConcurrentUpdateError
from rightjob.identity.domain.values import MembershipRole
from rightjob.identity.infrastructure.unit_of_work import SqlAlchemyIdentityUnitOfWork
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

pytest_plugins = ["tests.integration.test_identity_tenancy_rls"]
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("RIGHTJOB_DATABASE_URL")
        or not os.environ.get("RIGHTJOB_RLS_TEST_DATABASE_URL"),
        reason="isolated PostgreSQL URLs required",
    ),
]

WORKSPACE_A = UUID("0198ff00-0000-7000-8000-000000000001")
WORKSPACE_B = UUID("0198ff00-0000-7000-8000-000000000002")
USER_A = UUID("0198ff00-0000-7000-8000-000000000011")
MEMBERSHIP_A = UUID("0198ff00-0000-7000-8000-000000000021")


def _factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_verifier_role_is_least_privileged(rls_engines: tuple[Engine, Engine]) -> None:
    owner, _ = rls_engines
    with owner.connect() as connection:
        attributes = connection.execute(
            text(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolbypassrls "
                "FROM pg_roles WHERE rolname = 'rightjob_phase21_rls_verifier'"
            )
        ).one()
        grants = connection.execute(
            text(
                "SELECT table_name, privilege_type FROM information_schema.role_table_grants "
                "WHERE grantee = 'rightjob_phase21_rls_verifier' "
                "ORDER BY table_name, privilege_type"
            )
        ).all()
    assert attributes == (False, False, False, False, False)
    assert grants == [
        ("memberships", "DELETE"),
        ("memberships", "INSERT"),
        ("memberships", "SELECT"),
        ("memberships", "UPDATE"),
        ("users", "SELECT"),
        ("workspaces", "SELECT"),
    ]


def test_unit_of_work_commit_persists_versioned_membership_update(
    rls_engines: tuple[Engine, Engine],
) -> None:
    owner, app = rls_engines
    pool = app.pool
    assert isinstance(pool, QueuePool)
    with SqlAlchemyIdentityUnitOfWork(_factory(app)) as unit_of_work:
        membership = unit_of_work.memberships.get_for_user(WORKSPACE_A, USER_A)
        assert membership is not None
        saved = unit_of_work.memberships.save(
            WORKSPACE_A, replace(membership, role=MembershipRole.ADMIN)
        )
        unit_of_work.commit()
    assert pool.checkedout() == 0

    with owner.begin() as connection:
        stored = connection.execute(
            text("SELECT role, version FROM memberships WHERE id = :id"), {"id": MEMBERSHIP_A}
        ).one()
        connection.execute(
            text("UPDATE memberships SET role = 'owner' WHERE id = :id"), {"id": MEMBERSHIP_A}
        )
    assert stored == ("admin", saved.version)


def test_unit_of_work_rolls_back_when_commit_is_omitted(
    rls_engines: tuple[Engine, Engine],
) -> None:
    owner, app = rls_engines
    with SqlAlchemyIdentityUnitOfWork(_factory(app)) as unit_of_work:
        membership = unit_of_work.memberships.get_for_user(WORKSPACE_A, USER_A)
        assert membership is not None
        unit_of_work.memberships.save(WORKSPACE_A, replace(membership, role=MembershipRole.ADMIN))

    with owner.connect() as connection:
        role = connection.scalar(
            text("SELECT role FROM memberships WHERE id = :id"), {"id": MEMBERSHIP_A}
        )
    assert role == "owner"


def test_unit_of_work_explicit_rollback_discards_update(
    rls_engines: tuple[Engine, Engine],
) -> None:
    owner, app = rls_engines
    with SqlAlchemyIdentityUnitOfWork(_factory(app)) as unit_of_work:
        membership = unit_of_work.memberships.get_for_user(WORKSPACE_A, USER_A)
        assert membership is not None
        unit_of_work.memberships.save(WORKSPACE_A, replace(membership, role=MembershipRole.ADMIN))
        unit_of_work.rollback()

    with owner.connect() as connection:
        role = connection.scalar(
            text("SELECT role FROM memberships WHERE id = :id"), {"id": MEMBERSHIP_A}
        )
    assert role == "owner"


def test_unit_of_work_exception_rolls_back_and_releases_session(
    rls_engines: tuple[Engine, Engine],
) -> None:
    owner, app = rls_engines
    pool = app.pool
    assert isinstance(pool, QueuePool)
    assert pool.checkedout() == 0

    with (
        pytest.raises(RuntimeError, match="stop"),
        SqlAlchemyIdentityUnitOfWork(_factory(app)) as unit_of_work,
    ):
        membership = unit_of_work.memberships.get_for_user(WORKSPACE_A, USER_A)
        assert membership is not None
        unit_of_work.memberships.save(WORKSPACE_A, replace(membership, role=MembershipRole.ADMIN))
        raise RuntimeError("stop")

    assert pool.checkedout() == 0
    with owner.connect() as connection:
        role = connection.scalar(
            text("SELECT role FROM memberships WHERE id = :id"), {"id": MEMBERSHIP_A}
        )
    assert role == "owner"


def test_stale_membership_update_is_rejected(rls_engines: tuple[Engine, Engine]) -> None:
    _, app = rls_engines
    first = SqlAlchemyIdentityUnitOfWork(_factory(app))
    second = SqlAlchemyIdentityUnitOfWork(_factory(app))
    try:
        current = first.memberships.get_for_user(WORKSPACE_A, USER_A)
        stale = second.memberships.get_for_user(WORKSPACE_A, USER_A)
        assert current is not None and stale is not None
        first.memberships.save(WORKSPACE_A, replace(current, role=MembershipRole.ADMIN))
        first.commit()
        with pytest.raises(ConcurrentUpdateError, match="changed or removed"):
            second.memberships.save(WORKSPACE_A, stale)
        second.rollback()
    finally:
        first.close()
        second.close()


def test_repository_scope_cannot_select_another_workspace(
    rls_engines: tuple[Engine, Engine],
) -> None:
    _, app = rls_engines
    with SqlAlchemyIdentityUnitOfWork(_factory(app)) as unit_of_work:
        workspace_a_memberships = unit_of_work.memberships.list_for_workspace(WORKSPACE_A)
        assert [item.workspace_id for item in workspace_a_memberships] == [WORKSPACE_A]

        with pytest.raises(ValueError, match="workspace must match"):
            unit_of_work.memberships.save(
                WORKSPACE_A, replace(workspace_a_memberships[0], workspace_id=WORKSPACE_B)
            )
