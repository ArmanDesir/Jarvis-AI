"""Minimal API process: lifecycle and system health only."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, TypedDict

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from rightjob import __version__
from rightjob.identity.application.authorization import AuthorizationDeniedError
from rightjob.identity.application.operations import IdentityResourceNotFoundError
from rightjob.identity.application.repositories import ConcurrentUpdateError
from rightjob.shared.config import Settings
from rightjob.shared.identifiers import new_correlation_id, new_request_id
from rightjob.shared.logging import configure_logging
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from rightjob_api.dependencies import (
    CurrentAuthorizationContext,
    CurrentMembership,
    CurrentPrincipal,
    CurrentWorkspace,
)
from rightjob_api.errors import (
    authorization_error,
    concurrency_error,
    database_error,
    http_error,
    internal_error,
    not_found_error,
    validation_error,
)
from rightjob_api.identity_middleware import AuthenticationMiddleware, WorkspaceContextMiddleware
from rightjob_api.routes import router as identity_router

settings = Settings.load()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


class ReadinessItem(TypedDict):
    required: bool
    state: str
    detail: str


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("api.started", extra={"environment": settings.environment})
    yield
    logger.info("api.stopped")


app = FastAPI(
    title="Rightjob AI OS Bootstrap API",
    version=__version__,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
app.state.authentication_provider = None
app.state.identity_service = None
app.state.identity_uow_factory = None
app.add_middleware(WorkspaceContextMiddleware)
app.add_middleware(AuthenticationMiddleware)
app.include_router(identity_router)


@app.middleware("http")
async def correlation_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = str(new_request_id())
    correlation_id = request.headers.get("X-Correlation-ID") or str(new_correlation_id())
    request.state.request_id = request_id
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Correlation-ID"] = correlation_id
    return response


app.add_exception_handler(RequestValidationError, validation_error)  # type: ignore[arg-type]
app.add_exception_handler(HTTPException, http_error)  # type: ignore[arg-type]
app.add_exception_handler(AuthorizationDeniedError, authorization_error)  # type: ignore[arg-type]
app.add_exception_handler(IdentityResourceNotFoundError, not_found_error)  # type: ignore[arg-type]
app.add_exception_handler(ConcurrentUpdateError, concurrency_error)  # type: ignore[arg-type]
app.add_exception_handler(SQLAlchemyError, database_error)  # type: ignore[arg-type]
app.add_exception_handler(Exception, internal_error)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "running"}


@app.get("/ready", tags=["system"])
async def readiness() -> JSONResponse:
    database_state = "unavailable" if settings.database.enabled else "disabled"
    dependencies: dict[str, ReadinessItem] = {
        "database": {
            "required": settings.api.database_required,
            "state": database_state,
            "detail": "No database adapter is connected in Phase 1.",
        },
        "storage": {
            "required": False,
            "state": "unavailable" if settings.storage.enabled else "disabled",
            "detail": "Storage adapter is not implemented in Phase 1.",
        },
        "identity": {
            "required": False,
            "state": "unavailable" if settings.identity.enabled else "disabled",
            "detail": "Identity contracts exist; provider selection remains proof-gated.",
        },
        "ai": {
            "required": False,
            "state": "unavailable" if settings.ai.enabled else "disabled",
            "detail": "AI providers are not implemented in Phase 1.",
        },
        "workflow": {
            "required": False,
            "state": "unavailable" if settings.workflow.enabled else "disabled",
            "detail": "Workflow engine proof gate has not selected an adapter.",
        },
    }
    ready = all(not item["required"] or item["state"] == "ready" for item in dependencies.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "process": "running",
            "required_dependencies_ready": ready,
            "dependencies": dependencies,
        },
    )


@app.get("/version", tags=["system"])
async def version() -> dict[str, str]:
    return {
        "service": "rightjob-api",
        "version": __version__,
        "build": settings.build_version,
    }


@app.get("/identity/context", tags=["identity"])
async def identity_context(
    authorization: CurrentAuthorizationContext,
    principal: CurrentPrincipal,
    workspace: CurrentWorkspace,
    membership: CurrentMembership,
) -> dict[str, object]:
    assert authorization.principal == principal
    return {
        "user_id": str(principal.user_id),
        "external_subject": principal.external_subject,
        "workspace_id": str(workspace.id),
        "membership_id": str(membership.id),
        "roles": principal.roles,
        "permissions": principal.permissions,
        "authentication_provider": principal.authentication_provider,
    }
