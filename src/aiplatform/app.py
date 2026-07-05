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
from aiplatform.gateway.api.router import router as gateway_router
from aiplatform.gateway.providers.registry import build_registry
from aiplatform.gateway.service import GatewayService
from aiplatform.router.service import RouterService

logger = structlog.stdlib.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI application."""
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

        registry = build_registry(settings.gateway)
        router_svc = RouterService(settings.router) if settings.router.enabled else None
        app.state.gateway = GatewayService(registry, router=router_svc)
        app.state.router = router_svc

        health: HealthRegistry = app.state.health
        for llm_provider in registry.all():
            health.register(f"provider:{llm_provider.name}", llm_provider.health)

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
    app.include_router(gateway_router)
    return app
