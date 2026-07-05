# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-07-05

### Added

- **AI Gateway** — unified OpenAI-compatible inference API (`/v1/chat/completions`,
  `/v1/models`) supporting JSON and server-sent event (SSE) streaming responses.
- **Multi-provider support** — OpenAI, Anthropic (Claude), Google Gemini, Azure OpenAI,
  Ollama, vLLM, and OpenRouter; all activated via `AIP_GATEWAY__<PROVIDER>__*` env vars.
- **Async circuit breaker** — three-state (CLOSED / OPEN / HALF_OPEN) per-provider
  breaker with configurable failure threshold, recovery timeout, and half-open probe limit.
- **Provider failover** — `GatewayService` automatically retries failed requests across
  healthy providers; permanent errors (auth, context-length) short-circuit immediately.
- **Token accounting** — tiktoken-based prompt and completion token estimation with
  whitespace-split fallback for unknown models; populates `usage` when providers omit it.
- **In-process rate limiter** — token-bucket rate limiter per API key (Redis upgrade
  planned for the persistence milestone).
- **Provider health integration** — each enabled provider registers a health check with
  the existing `HealthRegistry`; `/health/ready` reflects provider liveness.
- **Gateway configuration** — nested `GatewaySettings` with per-provider sub-models;
  zero providers enabled by default; full `.env.example` documentation.
- **Unit test suite** — circuit breaker, domain models, accounting, `GatewayService`
  failover, and API router (JSON + SSE + validation) covered.

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
