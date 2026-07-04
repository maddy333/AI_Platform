"""Tests for request context and security headers middleware."""

import uuid

from fastapi.testclient import TestClient

from aiplatform.app import create_app
from aiplatform.core.config import Environment, LoggingSettings, Settings


def test_request_id_is_generated(client: TestClient) -> None:
    response = client.get("/health/live")
    # a generated id must be a valid UUID
    uuid.UUID(response.headers["X-Request-ID"])


def test_inbound_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "req-abc-123"})
    assert response.headers["X-Request-ID"] == "req-abc-123"


def test_security_headers_present(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in response.headers


def test_hsts_absent_outside_production(client: TestClient) -> None:
    response = client.get("/health/live")
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_present_in_production() -> None:
    settings = Settings(
        _env_file=None,
        environment=Environment.PRODUCTION,
        logging=LoggingSettings(level="WARNING", format="console"),
    )
    client = TestClient(create_app(settings))
    response = client.get("/health/live")
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")


def test_error_responses_carry_headers(client: TestClient) -> None:
    response = client.get("/no-such-route")
    assert response.status_code == 404
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    uuid.UUID(response.headers["X-Request-ID"])
