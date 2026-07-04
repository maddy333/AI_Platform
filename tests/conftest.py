"""Shared test fixtures."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aiplatform.app import create_app
from aiplatform.core.config import Environment, LoggingSettings, Settings


@pytest.fixture
def settings() -> Settings:
    """Settings isolated from any local .env file, quiet logging."""
    return Settings(
        _env_file=None,
        environment=Environment.TEST,
        logging=LoggingSettings(level="WARNING", format="console"),
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    # raise_server_exceptions=False lets tests assert on 500 responses
    # produced by the generic exception handler.
    return TestClient(app, raise_server_exceptions=False)
