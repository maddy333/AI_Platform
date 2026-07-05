"""FastAPI dependency providers for the gateway API."""

from __future__ import annotations

from fastapi import Depends, Request

from aiplatform.gateway.service import GatewayService


def get_gateway_service(request: Request) -> GatewayService:
    """Return the process-wide GatewayService from application state."""
    return request.app.state.gateway  # type: ignore[no-any-return]


GatewayDep = Depends(get_gateway_service)
