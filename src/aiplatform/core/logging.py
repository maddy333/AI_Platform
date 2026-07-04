"""Structured logging built on structlog.

The stdlib logging tree (uvicorn, third-party libraries) is routed through the
same processor pipeline so every line ships in one format: JSON in production,
human-readable console rendering in development. Request-scoped context
(request id, method, path) is attached via ``structlog.contextvars`` by
``RequestContextMiddleware``.
"""

import logging
import sys

import structlog
from structlog.typing import Processor

from aiplatform.core.config import LoggingSettings


def configure_logging(settings: LoggingSettings) -> None:
    """Configure structlog and route stdlib logging through its pipeline."""
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.ExtraAdder(),
    ]

    rendering: list[Processor]
    if settings.format == "json":
        rendering = [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        rendering = [structlog.dev.ConsoleRenderer()]

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *rendering,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.level)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Uvicorn installs its own handlers at import time; strip them so its
    # records propagate to the root handler and share the structured format.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structured logger."""
    return structlog.stdlib.get_logger(name)
