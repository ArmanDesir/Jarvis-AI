"""Identity/Tenancy application operations for the current Workspace context."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import UUID

from rightjob.identity.application.authorization import WorkspaceAuthorization
from rightjob.identity.application.context import AuthorizationContext, Principal
from rightjob.identity.application.repositories import ConcurrentUpdateError, IdentityUnitOfWork
from rightjob.identity.domain.entities import Membership, Workspace


class IdentityResourceNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class WorkspaceUpdate:
    expected_version: int
    name: str | None = None
    timezone: str | None = None
    locale: str | None = None


@dataclass(frozen=True)
class RequestMetadata:
    request_id: str
    correlation_id: str


@dataclass(frozen=True)
class MutationMetadata:
    correlation_id: str
    actor_user_id: UUID
    workspace_id: UUID
    membership_id: UUID
    operation: str
    target_id: UUID
    expected_version: int
    resulting_version: int
    occurred_at: datetime
    outcome: str


@dataclass(frozen=True)
class WorkspaceUpdateResult:
    workspace: Workspace
    metadata: MutationMetadata


class IdentityApplicationService:
    def __init__(self, authorization: WorkspaceAuthorization | None = None) -> None:
        self._authorization = authorization or WorkspaceAuthorization()

    def get_current_principal(self, context: AuthorizationContext) -> Principal:
        self._authorization.require_read(context)
        return context.principal

    def get_current_workspace(
        self, context: AuthorizationContext, unit_of_work: IdentityUnitOfWork
    ) -> Workspace:
        self._authorization.require_read(context)
        workspace = unit_of_work.workspaces.get(context.workspace.id)
        if workspace is None:
            raise IdentityResourceNotFoundError("Workspace not found")
        return workspace

    def get_current_membership(
        self, context: AuthorizationContext, unit_of_work: IdentityUnitOfWork
    ) -> Membership:
        self._authorization.require_read(context)
        membership = unit_of_work.memberships.get_for_user(
            context.workspace.id, context.principal.user_id
        )
        if membership is None:
            raise IdentityResourceNotFoundError("Membership not found")
        return membership

    def update_current_workspace(
        self,
        context: AuthorizationContext,
        update: WorkspaceUpdate,
        metadata: RequestMetadata,
        unit_of_work: IdentityUnitOfWork,
    ) -> WorkspaceUpdateResult:
        self._authorization.require_update(context)
        workspace = unit_of_work.workspaces.get(context.workspace.id)
        if workspace is None:
            raise IdentityResourceNotFoundError("Workspace not found")
        if workspace.version != update.expected_version:
            raise ConcurrentUpdateError("Workspace version is stale")

        updated = replace(
            workspace,
            name=update.name if update.name is not None else workspace.name,
            timezone=update.timezone if update.timezone is not None else workspace.timezone,
            locale=update.locale if update.locale is not None else workspace.locale,
        )
        saved = unit_of_work.workspaces.save(updated)
        unit_of_work.commit()
        occurred_at = datetime.now(timezone.utc)
        return WorkspaceUpdateResult(
            workspace=saved,
            metadata=MutationMetadata(
                correlation_id=metadata.correlation_id,
                actor_user_id=context.principal.user_id,
                workspace_id=context.workspace.id,
                membership_id=context.membership.id,
                operation="identity.workspace.update",
                target_id=saved.id,
                expected_version=update.expected_version,
                resulting_version=saved.version,
                occurred_at=occurred_at,
                outcome="committed",
            ),
        )
