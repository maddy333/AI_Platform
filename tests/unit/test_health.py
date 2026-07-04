"""Tests for liveness/readiness endpoints and the health registry."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aiplatform import __version__
from aiplatform.api import health as health_module
from aiplatform.api.health import HealthRegistry


async def _ok() -> None:
    return None


async def _boom() -> None:
    raise ConnectionError("database unreachable")


def test_liveness_reports_healthy(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["version"] == __version__
    assert body["components"] == []


def test_readiness_with_no_checks(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_readiness_reports_failing_check(app: FastAPI, client: TestClient) -> None:
    app.state.health.register("database", _boom)
    response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    [component] = body["components"]
    assert component["name"] == "database"
    assert component["status"] == "unhealthy"
    assert component["detail"] == "database unreachable"


def test_readiness_mixed_checks(app: FastAPI, client: TestClient) -> None:
    app.state.health.register("cache", _ok)
    app.state.health.register("database", _boom)
    response = client.get("/health/ready")
    assert response.status_code == 503
    statuses = {c["name"]: c["status"] for c in response.json()["components"]}
    assert statuses == {"cache": "healthy", "database": "unhealthy"}


def test_readiness_all_healthy(app: FastAPI, client: TestClient) -> None:
    app.state.health.register("cache", _ok)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_duplicate_check_registration_rejected() -> None:
    registry = HealthRegistry()
    registry.register("database", _ok)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("database", _ok)


def test_hung_check_times_out(
    monkeypatch: pytest.MonkeyPatch, app: FastAPI, client: TestClient
) -> None:
    monkeypatch.setattr(health_module, "CHECK_TIMEOUT_SECONDS", 0.05)

    async def _slow() -> None:
        await asyncio.sleep(5)

    app.state.health.register("slow-dependency", _slow)
    response = client.get("/health/ready")
    assert response.status_code == 503
    [component] = response.json()["components"]
    assert "timed out" in component["detail"]
