"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aiplatform.api.health import HealthRegistry
from aiplatform.api.health import router as health_router
from aiplatform.core.config import Settings, get_settings
from aiplatform.core.errors import register_exception_handlers
from aiplatform.core.logging import configure_logging
from aiplatform.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from aiplatform.core.telemetry import configure_telemetry, shutdown_telemetry

logger = structlog.stdlib.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI application.

    Accepts explicit settings for tests; falls back to the environment-derived
    singleton when run as a service (uvicorn factory mode).
    """
    settings = settings or get_settings()
    configure_logging(settings.logging)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "application_startup",
            environment=settings.environment.value,
            version=settings.version,
        )
        provider = configure_telemetry(app, settings)
        yield
        shutdown_telemetry(provider)
        logger.info("application_shutdown")

    app = FastAPI(
        title="AI Platform",
        description="Enterprise LLM gateway, intelligent routing, RAG, agents, and evaluation.",
        version=settings.version,
        lifespan=lifespan,
        # API schema and interactive docs are internal tooling; keep them out
        # of production surfaces.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
        root_path=settings.server.root_path,
    )
    app.state.settings = settings
    app.state.health = HealthRegistry()

    # Middleware executes in reverse registration order: request context runs
    # first so even CORS rejections carry a request id and security headers.
    if settings.cors.allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors.allow_origins,
            allow_methods=settings.cors.allow_methods,
            allow_headers=settings.cors.allow_headers,
            allow_credentials=settings.cors.allow_credentials,
        )
    app.add_middleware(SecurityHeadersMiddleware, enable_hsts=settings.is_production)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(health_router)
    return app
