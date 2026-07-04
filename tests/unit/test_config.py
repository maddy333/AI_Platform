"""Unit tests for aiplatform.core.config."""

from typing import Any

import pytest
from pydantic import ValidationError

from aiplatform import __version__
from aiplatform.core.config import Environment, ServerSettings, Settings, get_settings


def make_settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)


class TestSettings:
    def test_defaults(self) -> None:
        settings = make_settings()
        assert settings.app_name == "ai-platform"
        assert settings.version == __version__
        assert settings.environment is Environment.DEVELOPMENT
        assert settings.debug is False
        assert settings.server.port == 8000
        assert settings.logging.format == "json"
        assert settings.telemetry.enabled is False
        assert settings.cors.allow_origins == []

    def test_reads_environment_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AIP_ENVIRONMENT", "production")
        monkeypatch.setenv("AIP_SERVER__PORT", "9001")
        monkeypatch.setenv("AIP_TELEMETRY__ENABLED", "true")
        settings = make_settings()
        assert settings.environment is Environment.PRODUCTION
        assert settings.server.port == 9001
        assert settings.telemetry.enabled is True

    def test_is_production(self) -> None:
        assert make_settings(environment=Environment.PRODUCTION).is_production
        assert not make_settings(environment=Environment.DEVELOPMENT).is_production

    def test_rejects_invalid_port(self) -> None:
        with pytest.raises(ValidationError):
            ServerSettings(port=0)

    def test_rejects_unknown_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AIP_ENVIRONMENT", "galaxy")
        with pytest.raises(ValidationError):
            make_settings()

    def test_rejects_out_of_range_sample_ratio(self) -> None:
        with pytest.raises(ValidationError):
            make_settings(telemetry={"sample_ratio": 1.5})


class TestGetSettings:
    def test_returns_cached_singleton(self) -> None:
        get_settings.cache_clear()
        try:
            assert get_settings() is get_settings()
        finally:
            get_settings.cache_clear()
