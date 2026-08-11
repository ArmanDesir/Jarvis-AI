from __future__ import annotations

from types import TracebackType

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rightjob.identity.application.repositories import IdentityUnitOfWork
from rightjob_api.dependencies import (
    CurrentIdentityUnitOfWork,
    CurrentMembershipRepository,
    CurrentUserRepository,
    CurrentWorkspaceRepository,
)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.workspaces = object()
        self.users = object()
        self.memberships = object()
        self.closed = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


@pytest.mark.integration
def test_repository_dependencies_share_one_request_scoped_unit_of_work() -> None:
    test_app = FastAPI()
    created: list[FakeUnitOfWork] = []

    def factory() -> IdentityUnitOfWork:
        unit_of_work = FakeUnitOfWork()
        created.append(unit_of_work)
        return unit_of_work  # type: ignore[return-value]

    test_app.state.identity_uow_factory = factory

    @test_app.get("/")
    def verify_dependencies(
        unit_of_work: CurrentIdentityUnitOfWork,
        workspaces: CurrentWorkspaceRepository,
        users: CurrentUserRepository,
        memberships: CurrentMembershipRepository,
    ) -> dict[str, bool]:
        return {
            "workspaces": workspaces is unit_of_work.workspaces,
            "users": users is unit_of_work.users,
            "memberships": memberships is unit_of_work.memberships,
        }

    with TestClient(test_app) as client:
        response = client.get("/")

    assert response.json() == {"workspaces": True, "users": True, "memberships": True}
    assert len(created) == 1
    assert created[0].closed is True
