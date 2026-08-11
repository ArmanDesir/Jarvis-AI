"""Read-only identity and Workspace Membership resolution."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from rightjob.identity.application.authentication import ExternalIdentity
from rightjob.identity.application.context import AuthorizationContext, Principal
from rightjob.identity.application.repositories import (
    MembershipRepository,
    UserRepository,
    WorkspaceRepository,
)
from rightjob.identity.domain.values import RecordStatus


class IdentityResolutionCode(str, Enum):
    USER_NOT_FOUND = "user_not_found"
    USER_INACTIVE = "user_inactive"
    NOT_A_MEMBER = "not_a_member"
    MEMBERSHIP_INACTIVE = "membership_inactive"
    WORKSPACE_NOT_FOUND = "workspace_not_found"
    WORKSPACE_INACTIVE = "workspace_inactive"


class IdentityResolutionError(Exception):
    def __init__(self, code: IdentityResolutionCode) -> None:
        self.code = code
        super().__init__(code.value)


class IdentityService:
    def __init__(
        self,
        users: UserRepository,
        memberships: MembershipRepository,
        workspaces: WorkspaceRepository,
    ) -> None:
        self._users = users
        self._memberships = memberships
        self._workspaces = workspaces

    def resolve(self, identity: ExternalIdentity, workspace_id: UUID) -> AuthorizationContext:
        user = self._users.get_by_external_identity(identity.provider, identity.subject)
        if user is None:
            raise IdentityResolutionError(IdentityResolutionCode.USER_NOT_FOUND)
        if user.status is not RecordStatus.ACTIVE:
            raise IdentityResolutionError(IdentityResolutionCode.USER_INACTIVE)

        membership = self._memberships.get_for_user(workspace_id, user.id)
        if membership is None:
            raise IdentityResolutionError(IdentityResolutionCode.NOT_A_MEMBER)
        if membership.status is not RecordStatus.ACTIVE:
            raise IdentityResolutionError(IdentityResolutionCode.MEMBERSHIP_INACTIVE)

        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise IdentityResolutionError(IdentityResolutionCode.WORKSPACE_NOT_FOUND)
        if workspace.status is not RecordStatus.ACTIVE:
            raise IdentityResolutionError(IdentityResolutionCode.WORKSPACE_INACTIVE)

        principal = Principal(
            user_id=user.id,
            external_subject=identity.subject,
            workspace_id=workspace.id,
            membership_id=membership.id,
            roles=(membership.role.value,),
            permissions=(),
            authentication_provider=identity.provider,
        )
        return AuthorizationContext(principal, workspace, membership)
