from rightjob.identity.domain.entities import Workspace
from rightjob.identity.infrastructure.models import Base, WorkspaceRecord
from rightjob.identity.infrastructure.repositories import SqlAlchemyWorkspaceRepository
from sqlalchemy.orm import Session


def test_phase21_metadata_contains_only_approved_tables() -> None:
    assert set(Base.metadata.tables) == {"workspaces", "users", "memberships"}


def test_membership_mapping_is_directly_workspace_scoped() -> None:
    memberships = Base.metadata.tables["memberships"]
    assert memberships.c.workspace_id.nullable is False
    assert {constraint.name for constraint in memberships.constraints} >= {
        "pk_memberships",
        "fk_memberships_workspace",
        "fk_memberships_user",
        "uq_memberships_workspace_user",
    }
    assert all("tenant_id" not in table.c for table in Base.metadata.tables.values())
    assert all("organization_id" not in table.c for table in Base.metadata.tables.values())


def test_workspace_repository_maps_status_to_storage_value() -> None:
    with Session() as session:
        SqlAlchemyWorkspaceRepository(session).add(Workspace(name="Test", slug="test"))
        record = next(iter(session.new))

    assert isinstance(record, WorkspaceRecord)
    assert record.status == "active"
