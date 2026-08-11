"""Minimal Workspace authorization owned by Identity/Tenancy."""

from __future__ import annotations

from rightjob.identity.application.context import AuthorizationContext
from rightjob.identity.domain.values import MembershipRole, RecordStatus


class AuthorizationDeniedError(PermissionError):
    pass


class WorkspaceAuthorization:
    def require_read(self, context: AuthorizationContext) -> None:
        if (
            context.membership.status is not RecordStatus.ACTIVE
            or context.workspace.status is not RecordStatus.ACTIVE
        ):
            raise AuthorizationDeniedError("active Workspace membership required")

    def require_update(self, context: AuthorizationContext) -> None:
        self.require_read(context)
        if context.membership.role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
            raise AuthorizationDeniedError("Workspace owner or admin required")
