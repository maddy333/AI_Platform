# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-05

### Added

- Project scaffolding: uv-managed Python 3.13 project, ruff, mypy (strict), pytest.
- FastAPI application factory with lifespan management.
- Environment-driven configuration (`AIP_*` variables, pydantic-settings).
- Structured logging via structlog: JSON in production, console in development,
  stdlib/uvicorn records routed through the same pipeline.
- Request context middleware: `X-Request-ID` propagation and structured access logs.
- Security headers middleware with production-only HSTS.
- RFC 9457 problem-details error handling for all error surfaces.
- Kubernetes-ready health endpoints: `/health/live` and `/health/ready` with a
  pluggable, timeout-bounded dependency check registry.
- OpenTelemetry tracing bootstrap (OTLP/HTTP export, parent-based ratio sampling).
- CI workflow: lint, format check, strict type check, tests with coverage gate.
