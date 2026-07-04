"""Pure ASGI middleware: request context propagation and secure response headers.

Implemented against the raw ASGI protocol rather than
``starlette.middleware.base.BaseHTTPMiddleware`` so streaming responses (SSE
from the gateway in later milestones) are never buffered and no extra task is
spawned per request.
"""

import time
import uuid

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"

_access_logger = structlog.stdlib.get_logger("aiplatform.access")


class RequestContextMiddleware:
    """Assign a request id, bind logging context, and emit one access log line.

    The inbound ``X-Request-ID`` header is honoured for cross-service
    correlation; otherwise a UUID4 is generated. The id is echoed on the
    response and bound into ``structlog.contextvars`` so every log line
    emitted while handling the request carries it.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = headers.get(REQUEST_ID_HEADER, "").strip() or str(uuid.uuid4())
        status_code = 500  # reported if the app dies before responding

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)

        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            http_method=scope["method"],
            http_path=scope["path"],
        )
        start = time.perf_counter()
        try:
            await self._app(scope, receive, send_with_request_id)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            _access_logger.info("http_request", status_code=status_code, duration_ms=duration_ms)
            structlog.contextvars.clear_contextvars()


class SecurityHeadersMiddleware:
    """Attach OWASP-recommended security headers to every response.

    HSTS is only meaningful behind TLS, so it is opt-in and enabled by the
    application factory in production environments.
    """

    def __init__(self, app: ASGIApp, *, enable_hsts: bool = False) -> None:
        self._app = app
        self._enable_hsts = enable_hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
                if self._enable_hsts:
                    headers.setdefault(
                        "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
                    )
            await send(message)

        await self._app(scope, receive, send_with_security_headers)
