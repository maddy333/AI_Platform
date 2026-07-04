"""Platform exception hierarchy and RFC 9457 problem-details responses.

Every error surface — domain errors, request validation, framework HTTP
errors, and unexpected exceptions — is normalised to ``application/problem+json``
so API consumers handle exactly one error shape. Unexpected exceptions are
logged with full context but masked in the response body.
"""

from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.stdlib.get_logger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"
ERROR_TYPE_BASE = "https://aiplatform.dev/errors"


class PlatformError(Exception):
    """Base class for all domain errors raised by the platform."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"
    title: str = "Internal Server Error"

    def __init__(self, detail: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.context = context or {}


class ConfigurationError(PlatformError):
    """The platform is misconfigured; requires operator intervention."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "configuration_error"
    title = "Configuration Error"


class NotFoundError(PlatformError):
    """A requested resource does not exist."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"
    title = "Resource Not Found"


class ConflictError(PlatformError):
    """The request conflicts with the current state of a resource."""

    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"
    title = "Conflict"


class ServiceUnavailableError(PlatformError):
    """An upstream dependency is unavailable; the request may be retried."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "service_unavailable"
    title = "Service Unavailable"


def problem_response(
    request: Request,
    *,
    status_code: int,
    title: str,
    detail: str,
    error_code: str,
    extensions: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build an RFC 9457 problem-details response."""
    body: dict[str, Any] = {
        "type": f"{ERROR_TYPE_BASE}/{error_code}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
    }
    if extensions:
        body.update(extensions)
    return JSONResponse(body, status_code=status_code, media_type=PROBLEM_CONTENT_TYPE)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach problem+json handlers for every error surface."""

    @app.exception_handler(PlatformError)
    async def handle_platform_error(request: Request, exc: PlatformError) -> JSONResponse:
        log = logger.error if exc.status_code >= 500 else logger.warning
        log("platform_error", error_code=exc.error_code, detail=exc.detail, **exc.context)
        return problem_response(
            request,
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            error_code=exc.error_code,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Strip submitted input values from the echo to avoid reflecting
        # sensitive payloads back to the caller.
        errors = [
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
            for err in exc.errors()
        ]
        return problem_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation Error",
            detail="Request validation failed.",
            error_code="validation_error",
            extensions={"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem_response(
            request,
            status_code=exc.status_code,
            title=HTTPStatus(exc.status_code).phrase,
            detail=str(exc.detail),
            error_code="http_error",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", exc_type=type(exc).__name__)
        return problem_response(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="An unexpected error occurred.",
            error_code="internal_error",
        )
