from dataclasses import replace
from typing import Any

import pytest
from rightjob.identity.application.repositories import ConcurrentUpdateError
from rightjob.identity.infrastructure.repositories import SqlAlchemyWorkspaceRepository

from tests.unit.test_identity_service import WORKSPACE_A


class Result:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class Session:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount
        self.statements: list[Any] = []

    def execute(self, statement: Any) -> Result:
        self.statements.append(statement)
        return Result(self.rowcount)


def test_save_increments_version_after_version_checked_update() -> None:
    session = Session(rowcount=1)
    repository = SqlAlchemyWorkspaceRepository(session)  # type: ignore[arg-type]

    saved = repository.save(replace(WORKSPACE_A, name="Updated"))

    assert saved.name == "Updated"
    assert saved.version == WORKSPACE_A.version + 1
    assert saved.updated_at > WORKSPACE_A.updated_at
    assert len(session.statements) == 1


def test_save_rejects_stale_version() -> None:
    repository = SqlAlchemyWorkspaceRepository(Session(rowcount=0))  # type: ignore[arg-type]

    with pytest.raises(ConcurrentUpdateError, match="changed or removed"):
        repository.save(WORKSPACE_A)
