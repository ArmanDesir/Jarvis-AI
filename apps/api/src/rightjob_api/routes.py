"""Approved Phase 2.4 Identity/Tenancy application routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Security
from fastapi.security import HTTPBearer
from rightjob.identity.application.operations import (
    IdentityApplicationService,
    RequestMetadata,
    WorkspaceUpdate,
)

from rightjob_api.contracts import (
    CurrentPrincipalResponse,
    MembershipResponse,
    ProblemDetail,
    WorkspacePatchRequest,
    WorkspaceResponse,
)
from rightjob_api.dependencies import CurrentAuthorizationContext, CurrentIdentityUnitOfWork

bearer = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="Provider-neutral bearer token verified by the configured identity adapter",
)
router = APIRouter(prefix="/api/v1", tags=["identity"], dependencies=[Security(bearer)])
service = IdentityApplicationService()


def identity_application_service() -> IdentityApplicationService:
    return service


CurrentIdentityApplicationService = Annotated[
    IdentityApplicationService, Depends(identity_application_service)
]

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetail, "description": "Unauthenticated"},
    403: {"model": ProblemDetail, "description": "Forbidden"},
    422: {"model": ProblemDetail, "description": "Validation error"},
    500: {"model": ProblemDetail, "description": "Internal error"},
}


@router.get(
    "/me",
    response_model=CurrentPrincipalResponse,
    operation_id="getCurrentPrincipalContext",
    responses=ERROR_RESPONSES,
)
def current_principal(
    context: CurrentAuthorizationContext,
    application: CurrentIdentityApplicationService,
) -> CurrentPrincipalResponse:
    return CurrentPrincipalResponse.from_principal(application.get_current_principal(context))


@router.get(
    "/workspace",
    response_model=WorkspaceResponse,
    operation_id="getCurrentWorkspace",
    responses=ERROR_RESPONSES | {404: {"model": ProblemDetail, "description": "Not found"}},
)
def current_workspace(
    context: CurrentAuthorizationContext,
    unit_of_work: CurrentIdentityUnitOfWork,
    application: CurrentIdentityApplicationService,
) -> WorkspaceResponse:
    return WorkspaceResponse.from_workspace(
        application.get_current_workspace(context, unit_of_work)
    )


@router.patch(
    "/workspace",
    response_model=WorkspaceResponse,
    operation_id="updateCurrentWorkspace",
    responses=ERROR_RESPONSES
    | {
        404: {"model": ProblemDetail, "description": "Not found"},
        409: {"model": ProblemDetail, "description": "Version conflict"},
    },
)
def update_workspace(
    patch: WorkspacePatchRequest,
    request: Request,
    context: CurrentAuthorizationContext,
    unit_of_work: CurrentIdentityUnitOfWork,
    application: CurrentIdentityApplicationService,
) -> WorkspaceResponse:
    result = application.update_current_workspace(
        context,
        WorkspaceUpdate(**patch.model_dump()),
        RequestMetadata(
            request_id=request.state.request_id,
            correlation_id=request.state.correlation_id,
        ),
        unit_of_work,
    )
    return WorkspaceResponse.from_workspace(result.workspace)


@router.get(
    "/membership",
    response_model=MembershipResponse,
    operation_id="getCurrentMembership",
    responses=ERROR_RESPONSES | {404: {"model": ProblemDetail, "description": "Not found"}},
)
def current_membership(
    context: CurrentAuthorizationContext,
    unit_of_work: CurrentIdentityUnitOfWork,
    application: CurrentIdentityApplicationService,
) -> MembershipResponse:
    return MembershipResponse.from_membership(
        application.get_current_membership(context, unit_of_work)
    )
