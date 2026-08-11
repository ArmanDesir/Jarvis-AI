"""Owner-scoped Repository interfaces for Identity/Tenancy aggregates."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self, Sequence
from uuid import UUID

from rightjob.identity.domain.entities import Membership, User, Workspace


class ConcurrentUpdateError(RuntimeError):
    """The stored aggregate changed after it was loaded."""


class WorkspaceRepository(Protocol):
    def add(self, workspace: Workspace) -> None: ...

    def get(self, workspace_id: UUID) -> Workspace | None: ...

    def save(self, workspace: Workspace) -> Workspace: ...


class UserRepository(Protocol):
    def add(self, user: User) -> None: ...

    def get_by_external_identity(self, provider: str, subject: str) -> User | None: ...

    def save(self, user: User) -> User: ...


class MembershipRepository(Protocol):
    def add(self, workspace_id: UUID, membership: Membership) -> None: ...

    def list_for_workspace(self, workspace_id: UUID) -> Sequence[Membership]: ...

    def get_for_user(self, workspace_id: UUID, user_id: UUID) -> Membership | None: ...

    def save(self, workspace_id: UUID, membership: Membership) -> Membership: ...


class IdentityUnitOfWork(Protocol):
    workspaces: WorkspaceRepository
    users: UserRepository
    memberships: MembershipRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...
