"""Tests for the exception hierarchy and problem+json handlers."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from aiplatform.app import create_app
from aiplatform.core.config import Settings
from aiplatform.core.errors import PROBLEM_CONTENT_TYPE, NotFoundError


class _Payload(BaseModel):
    count: int


@pytest.fixture
def error_app(settings: Settings) -> FastAPI:
    app = create_app(settings)

    @app.get("/boom-domain")
    async def boom_domain() -> None:
        raise NotFoundError("model 'gpt-x' is not registered", context={"model": "gpt-x"})

    @app.post("/echo")
    async def echo(payload: _Payload) -> _Payload:
        return payload

    @app.get("/boom-unexpected")
    async def boom_unexpected() -> None:
        raise RuntimeError("secret internal state")

    return app


@pytest.fixture
def error_client(error_app: FastAPI) -> TestClient:
    return TestClient(error_app, raise_server_exceptions=False)


def test_domain_error_renders_problem_json(error_client: TestClient) -> None:
    response = error_client.get("/boom-domain")
    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    body = response.json()
    assert body["title"] == "Resource Not Found"
    assert body["detail"] == "model 'gpt-x' is not registered"
    assert body["status"] == 404
    assert body["instance"] == "/boom-domain"
    assert body["type"].endswith("/not_found")


def test_validation_error_renders_problem_json(error_client: TestClient) -> None:
    response = error_client.post("/echo", json={"count": "not-a-number"})
    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    body = response.json()
    assert body["title"] == "Validation Error"
    assert body["errors"][0]["loc"] == ["body", "count"]


def test_validation_error_does_not_echo_input(error_client: TestClient) -> None:
    response = error_client.post("/echo", json={"count": "sk-super-secret-value"})
    assert "sk-super-secret-value" not in response.text


def test_unexpected_error_is_masked(error_client: TestClient) -> None:
    response = error_client.get("/boom-unexpected")
    assert response.status_code == 500
    assert "secret internal state" not in response.text
    body = response.json()
    assert body["title"] == "Internal Server Error"
    assert body["detail"] == "An unexpected error occurred."


def test_framework_http_errors_are_normalised(error_client: TestClient) -> None:
    response = error_client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    assert response.json()["title"] == "Not Found"
