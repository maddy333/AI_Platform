"""Liveness and readiness endpoints.

Liveness (``/health/live``) answers "is the process running?" and never
depends on downstream systems. Readiness (``/health/ready``) aggregates
registered dependency checks (database, cache, message broker — contributed
by subsystems in later milestones); any failing check returns 503 so the
orchestrator stops routing traffic to the pod.
"""

import asyncio
from collections.abc import Awaitable, Callable
from enum import StrEnum

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

HealthCheck = Callable[[], Awaitable[None]]

CHECK_TIMEOUT_SECONDS = 5.0


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Outcome of a single dependency check."""

    name: str
    status: HealthStatus
    detail: str | None = None


class HealthReport(BaseModel):
    """Aggregate health of the service."""

    status: HealthStatus
    version: str
    components: list[ComponentHealth]


class HealthRegistry:
    """Registry of async readiness checks contributed by subsystems.

    A check succeeds by returning and fails by raising; the exception message
    becomes the reported detail. Checks run concurrently and are individually
    bounded by ``CHECK_TIMEOUT_SECONDS`` so one hung dependency cannot stall
    the probe.
    """

    def __init__(self) -> None:
        self._checks: dict[str, HealthCheck] = {}

    def register(self, name: str, check: HealthCheck) -> None:
        if name in self._checks:
            raise ValueError(f"health check already registered: {name}")
        self._checks[name] = check

    async def run_all(self) -> list[ComponentHealth]:
        async def run_one(name: str, check: HealthCheck) -> ComponentHealth:
            try:
                async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
                    await check()
            except TimeoutError:
                return ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    detail=f"health check timed out after {CHECK_TIMEOUT_SECONDS}s",
                )
            except Exception as exc:
                return ComponentHealth(name=name, status=HealthStatus.UNHEALTHY, detail=str(exc))
            return ComponentHealth(name=name, status=HealthStatus.HEALTHY)

        results = await asyncio.gather(
            *(run_one(name, check) for name, check in self._checks.items())
        )
        return list(results)


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthReport)
async def liveness(request: Request) -> HealthReport:
    """Process liveness: always healthy while the event loop responds."""
    return HealthReport(
        status=HealthStatus.HEALTHY,
        version=request.app.state.settings.version,
        components=[],
    )


@router.get(
    "/ready",
    response_model=HealthReport,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthReport}},
)
async def readiness(request: Request, response: Response) -> HealthReport:
    """Dependency readiness: 503 when any registered check fails."""
    registry: HealthRegistry = request.app.state.health
    components = await registry.run_all()
    healthy = all(c.status is HealthStatus.HEALTHY for c in components)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthReport(
        status=HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY,
        version=request.app.state.settings.version,
        components=components,
    )
