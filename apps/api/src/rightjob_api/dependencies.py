"""Request-scoped Identity/Tenancy dependencies."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from rightjob.identity.application.context import AuthorizationContext, Principal
from rightjob.identity.application.repositories import (
    IdentityUnitOfWork,
    MembershipRepository,
    UserRepository,
    WorkspaceRepository,
)
from rightjob.identity.domain.entities import Membership, Workspace


def current_authorization_context(request: Request) -> AuthorizationContext:
    context = getattr(request.state, "authorization_context", None)
    if not isinstance(context, AuthorizationContext):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return context


def current_principal(request: Request) -> Principal:
    return current_authorization_context(request).principal


def current_workspace(request: Request) -> Workspace:
    return current_authorization_context(request).workspace


def current_membership(request: Request) -> Membership:
    return current_authorization_context(request).membership


def identity_unit_of_work(request: Request) -> Iterator[IdentityUnitOfWork]:
    factory = getattr(request.app.state, "identity_uow_factory", None)
    if not callable(factory):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")
    unit_of_work = cast(Callable[[], IdentityUnitOfWork], factory)()
    with unit_of_work:
        yield unit_of_work


CurrentIdentityUnitOfWork = Annotated[IdentityUnitOfWork, Depends(identity_unit_of_work)]


def workspace_repository(unit_of_work: CurrentIdentityUnitOfWork) -> WorkspaceRepository:
    return unit_of_work.workspaces


def user_repository(unit_of_work: CurrentIdentityUnitOfWork) -> UserRepository:
    return unit_of_work.users


def membership_repository(unit_of_work: CurrentIdentityUnitOfWork) -> MembershipRepository:
    return unit_of_work.memberships


CurrentAuthorizationContext = Annotated[
    AuthorizationContext, Depends(current_authorization_context)
]
CurrentPrincipal = Annotated[Principal, Depends(current_principal)]
CurrentWorkspace = Annotated[Workspace, Depends(current_workspace)]
CurrentMembership = Annotated[Membership, Depends(current_membership)]
CurrentWorkspaceRepository = Annotated[WorkspaceRepository, Depends(workspace_repository)]
CurrentUserRepository = Annotated[UserRepository, Depends(user_repository)]
CurrentMembershipRepository = Annotated[MembershipRepository, Depends(membership_repository)]
