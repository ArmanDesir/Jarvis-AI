"""Central, sanitized HTTP error translation."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from rightjob.identity.application.authorization import AuthorizationDeniedError
from rightjob.identity.application.operations import IdentityResourceNotFoundError
from rightjob.identity.application.repositories import ConcurrentUpdateError
from rightjob.shared.identifiers import new_correlation_id
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from rightjob_api.contracts import ErrorItem, ProblemDetail

logger = logging.getLogger(__name__)


def correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", str(new_correlation_id()))


def problem_response(
    request: Request,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    errors: Sequence[ErrorItem] = (),
) -> JSONResponse:
    problem = ProblemDetail(
        type=f"https://rightjob.ai/problems/{code.lower().replace('_', '-')}",
        title=title,
        status=status_code,
        code=code,
        detail=detail,
        instance=request.url.path,
        correlation_id=correlation_id(request),
        errors=tuple(errors),
    )
    return JSONResponse(status_code=status_code, content=problem.model_dump(mode="json"))


async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    details = tuple(
        ErrorItem(
            field=".".join(str(part) for part in item["loc"] if part != "body"),
            message=item["msg"],
            kind=item["type"],
        )
        for item in error.errors()
    )
    return problem_response(
        request, 422, "VALIDATION_ERROR", "Validation error", "Request validation failed", details
    )


async def http_error(request: Request, error: HTTPException) -> JSONResponse:
    code = {
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        503: "SERVICE_UNAVAILABLE",
    }.get(error.status_code, "HTTP_ERROR")
    return problem_response(request, error.status_code, code, "Request failed", str(error.detail))


async def authorization_error(request: Request, _: AuthorizationDeniedError) -> JSONResponse:
    return problem_response(request, 403, "FORBIDDEN", "Forbidden", "Workspace access denied")


async def not_found_error(request: Request, _: IdentityResourceNotFoundError) -> JSONResponse:
    return problem_response(request, 404, "NOT_FOUND", "Not found", "Resource not found")


async def concurrency_error(request: Request, _: ConcurrentUpdateError) -> JSONResponse:
    return problem_response(
        request, 409, "VERSION_CONFLICT", "Version conflict", "The resource has changed"
    )


async def database_error(request: Request, _: SQLAlchemyError) -> JSONResponse:
    logger.error("api.database_error", extra={"correlation_id": correlation_id(request)})
    return problem_response(
        request, 500, "INTERNAL", "Internal error", "The request could not be completed"
    )


async def internal_error(request: Request, _: Exception) -> JSONResponse:
    logger.error("api.unhandled_error", extra={"correlation_id": correlation_id(request)})
    return problem_response(
        request, 500, "INTERNAL", "Internal error", "The request could not be completed"
    )
