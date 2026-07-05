"""Application configuration.

All settings are sourced from the environment (Twelve-Factor III) using the
``AIP_`` prefix and ``__`` as the nested delimiter, e.g.::

    AIP_ENVIRONMENT=production
    AIP_SERVER__PORT=9000
    AIP_TELEMETRY__OTLP_ENDPOINT=http://otel-collector:4318

A local ``.env`` file is honoured for development convenience only; deployed
environments must inject real environment variables (Kubernetes secrets and
config maps in later milestones).
"""

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from aiplatform import __version__
from aiplatform.gateway.config import GatewaySettings
from aiplatform.router.config import RouterSettings


class Environment(StrEnum):
    """Deployment environment the process is running in."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class ServerSettings(BaseModel):
    """Uvicorn server binding."""

    host: str = "0.0.0.0"  # noqa: S104 - binds inside a container; ingress fronts it
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=1, ge=1)
    root_path: str = ""


class LoggingSettings(BaseModel):
    """Structured logging behaviour."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["json", "console"] = "json"


class TelemetrySettings(BaseModel):
    """OpenTelemetry tracing export."""

    enabled: bool = False
    otlp_endpoint: str = "http://localhost:4318"
    sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)


class CorsSettings(BaseModel):
    """Cross-origin resource sharing policy.

    Empty ``allow_origins`` (the default) disables CORS entirely; origins must
    be allow-listed explicitly per environment.
    """

    allow_origins: list[str] = Field(default_factory=list)
    allow_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    )
    allow_headers: list[str] = Field(
        default_factory=lambda: ["Authorization", "Content-Type", "X-Request-ID"]
    )
    allow_credentials: bool = False


class Settings(BaseSettings):
    """Root application settings, composed from the environment."""

    model_config = SettingsConfigDict(
        env_prefix="AIP_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ai-platform"
    version: str = __version__
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False

    server: ServerSettings = Field(default_factory=ServerSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)
    gateway: GatewaySettings = Field(default_factory=GatewaySettings)
    router: RouterSettings = Field(default_factory=RouterSettings)

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so every consumer observes one consistent configuration; tests may
    call ``get_settings.cache_clear()`` to re-read the environment.
    """
    return Settings()
