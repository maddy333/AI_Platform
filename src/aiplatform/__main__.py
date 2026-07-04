"""Console entrypoint: ``python -m aiplatform`` or the ``aiplatform`` script."""

import uvicorn

from aiplatform.core.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "aiplatform.app:create_app",
        factory=True,
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers,
        log_config=None,  # the app configures stdlib logging via structlog
        access_log=False,  # replaced by RequestContextMiddleware structured access logs
    )


if __name__ == "__main__":
    main()
