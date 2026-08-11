"""Authentication and Workspace context middleware with fail-closed errors."""

from __future__ import annotations

from uuid import UUID

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from rightjob.identity.application.authentication import (
    AuthenticationError,
    AuthenticationErrorCode,
)
from rightjob.identity.application.service import IdentityResolutionError, IdentityService
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from rightjob_api.errors import problem_response

PUBLIC_PATHS = frozenset({"/health", "/ready", "/version"})


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        authorization = request.headers.get("Authorization", "")
        if request.url.path in PUBLIC_PATHS and not authorization:
            return await call_next(request)

        provider = getattr(request.app.state, "authentication_provider", None)
        if provider is None:
            return problem_response(
                request,
                503,
                AuthenticationErrorCode.UNAVAILABLE.value,
                "Authentication unavailable",
                "Authentication unavailable",
            )

        scheme, separator, token = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token.strip():
            return problem_response(
                request,
                401,
                AuthenticationErrorCode.MISSING.value,
                "Unauthenticated",
                "Bearer token required",
            )
        try:
            request.state.external_identity = await run_in_threadpool(
                provider.authenticate, token.strip()
            )
        except AuthenticationError as error:
            return problem_response(
                request, 401, error.code.value, "Unauthenticated", "Token could not be verified"
            )
        return await call_next(request)


class WorkspaceContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        identity = getattr(request.state, "external_identity", None)
        if request.url.path in PUBLIC_PATHS and identity is None:
            return await call_next(request)

        raw_workspace_id = request.headers.get("X-Workspace-ID")
        if not raw_workspace_id:
            return problem_response(
                request,
                400,
                "workspace_required",
                "Workspace required",
                "X-Workspace-ID is required",
            )
        try:
            workspace_id = UUID(raw_workspace_id)
        except (ValueError, AttributeError):
            return problem_response(
                request,
                400,
                "workspace_invalid",
                "Invalid Workspace",
                "X-Workspace-ID must be a UUID",
            )

        service = getattr(request.app.state, "identity_service", None)
        if not isinstance(service, IdentityService) or identity is None:
            return problem_response(
                request,
                503,
                "identity_unavailable",
                "Identity unavailable",
                "Identity resolution unavailable",
            )
        try:
            request.state.authorization_context = await run_in_threadpool(
                service.resolve, identity, workspace_id
            )
        except IdentityResolutionError:
            return problem_response(
                request,
                403,
                "workspace_access_denied",
                "Forbidden",
                "Workspace access denied",
            )
        return await call_next(request)
