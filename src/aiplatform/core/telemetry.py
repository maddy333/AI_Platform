"""OpenTelemetry bootstrap.

Tracing is disabled by default and enabled with ``AIP_TELEMETRY__ENABLED=true``.
Spans are exported over OTLP/HTTP to the configured collector endpoint with
parent-based ratio sampling. Health probes are excluded from instrumentation
to keep trace volume meaningful.
"""

import structlog
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

from aiplatform.core.config import Settings

logger = structlog.stdlib.get_logger(__name__)

_EXCLUDED_URLS = "health/live,health/ready"


def configure_telemetry(app: FastAPI, settings: Settings) -> TracerProvider | None:
    """Initialise tracing for the application; no-op when disabled."""
    if not settings.telemetry.enabled:
        logger.info("telemetry_disabled")
        return None

    resource = Resource.create(
        {
            "service.name": settings.app_name,
            "service.version": settings.version,
            "deployment.environment": settings.environment.value,
        }
    )
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBasedTraceIdRatio(settings.telemetry.sample_ratio),
    )
    exporter = OTLPSpanExporter(endpoint=f"{settings.telemetry.otlp_endpoint}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls=_EXCLUDED_URLS)
    logger.info(
        "telemetry_configured",
        otlp_endpoint=settings.telemetry.otlp_endpoint,
        sample_ratio=settings.telemetry.sample_ratio,
    )
    return provider


def shutdown_telemetry(provider: TracerProvider | None) -> None:
    """Flush pending spans and release exporter resources."""
    if provider is not None:
        provider.shutdown()
