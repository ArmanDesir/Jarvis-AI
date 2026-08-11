from __future__ import annotations

from dataclasses import replace
from types import TracebackType

import pytest
from rightjob.identity.application.authorization import AuthorizationDeniedError
from rightjob.identity.application.operations import (
    IdentityApplicationService,
    RequestMetadata,
    WorkspaceUpdate,
)
from rightjob.identity.application.repositories import ConcurrentUpdateError
from rightjob.identity.domain.entities import Workspace
from rightjob.identity.domain.values import MembershipRole

from tests.unit.test_identity_service import MEMBERSHIP_A, USER, WORKSPACE_A, _service


class Workspaces:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.saved: Workspace | None = None

    def get(self, workspace_id: object) -> Workspace | None:
        return self.workspace if workspace_id == self.workspace.id else None

    def save(self, workspace: Workspace) -> Workspace:
        if workspace.version != self.workspace.version:
            raise ConcurrentUpdateError("stale")
        self.saved = replace(workspace, version=workspace.version + 1)
        self.workspace = self.saved
        return self.saved


class UnitOfWork:
    def __init__(self, workspace: Workspace = WORKSPACE_A) -> None:
        self.workspaces = Workspaces(workspace)
        self.users = object()
        self.memberships = object()
        self.commits = 0

    def __enter__(self) -> UnitOfWork:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


def test_owner_update_commits_once_and_returns_audit_ready_metadata() -> None:
    context = _service().resolve(
        type("Identity", (), {"provider": "test-oidc", "subject": "subject-1"})(),
        WORKSPACE_A.id,
    )
    unit_of_work = UnitOfWork()

    result = IdentityApplicationService().update_current_workspace(
        context,
        WorkspaceUpdate(expected_version=1, name="Updated"),
        RequestMetadata("request-1", "correlation-1"),
        unit_of_work,  # type: ignore[arg-type]
    )

    assert result.workspace.name == "Updated"
    assert result.workspace.version == 2
    assert unit_of_work.commits == 1
    assert result.metadata.actor_user_id == USER.id
    assert result.metadata.workspace_id == WORKSPACE_A.id
    assert result.metadata.membership_id == MEMBERSHIP_A.id
    assert result.metadata.correlation_id == "correlation-1"
    assert result.metadata.operation == "identity.workspace.update"
    assert result.metadata.expected_version == 1
    assert result.metadata.resulting_version == 2


def test_member_cannot_update_workspace() -> None:
    context = replace(
        _service().resolve(
            type("Identity", (), {"provider": "test-oidc", "subject": "subject-1"})(),
            WORKSPACE_A.id,
        ),
        membership=replace(MEMBERSHIP_A, role=MembershipRole.MEMBER),
    )

    with pytest.raises(AuthorizationDeniedError):
        IdentityApplicationService().update_current_workspace(
            context,
            WorkspaceUpdate(expected_version=1, name="Denied"),
            RequestMetadata("request-1", "correlation-1"),
            UnitOfWork(),  # type: ignore[arg-type]
        )


def test_stale_workspace_update_does_not_commit() -> None:
    context = _service().resolve(
        type("Identity", (), {"provider": "test-oidc", "subject": "subject-1"})(),
        WORKSPACE_A.id,
    )
    unit_of_work = UnitOfWork()

    with pytest.raises(ConcurrentUpdateError):
        IdentityApplicationService().update_current_workspace(
            context,
            WorkspaceUpdate(expected_version=2, name="Stale"),
            RequestMetadata("request-1", "correlation-1"),
            unit_of_work,  # type: ignore[arg-type]
        )

    assert unit_of_work.commits == 0
    assert unit_of_work.workspaces.workspace == WORKSPACE_A
