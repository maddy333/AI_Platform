# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-07-05

### Added

- **Intelligent Model Router** — pluggable scoring system that selects the optimal
  `(provider, model)` pair for every inference request based on cost, latency, quality,
  or a weighted combination of all three.
- **Four routing strategies** — `CostStrategy`, `LatencyStrategy`, `QualityStrategy`,
  and `BalancedStrategy`; each implements a `RoutingStrategy` Protocol and is selected
  per-request via `RoutingContext.effective_strategy`.
- **Virtual model aliases** — send `model: "smart"` (quality), `"fast"` (latency),
  `"cheap"` (cost), or `"balanced"` (balanced) and the router resolves a real model
  and provider transparently; alias is substituted before the provider call.
- **EWMA latency tracker** — thread-safe exponentially-weighted moving average tracker
  feeds real measured latency back into routing decisions after every successful call.
- **Rule-based prompt classifier** — assigns `PromptComplexity` (CODE / REASONING /
  CREATIVE / COMPLEX / SIMPLE) from message content and token count; used by
  `QualityStrategy` to boost tag-matched models.
- **Static model catalog** — 14-model catalog spanning OpenAI (gpt-4o, gpt-4o-mini,
  o1, o1-mini, o3-mini), Anthropic (claude-opus-4-8, claude-sonnet-4-6, claude-haiku
  variants), and Gemini (2.5-pro, 2.0-flash, 2.0-flash-lite, 1.5-pro); `ModelProfile`
  provides `estimate_cost()` (Decimal arithmetic) and `fits_context()`.
- **Policy enforcement** — `RoutingPolicy` filters candidates by allowed/denied model
  IDs, allowed provider names, maximum input tokens, and per-request cost ceiling.
- **Gateway integration** — `GatewayService` accepts an injected `RouterService`;
  router candidates are tried in score order with latency feedback after each call;
  falls back to registry-order failover when the router returns no candidates.
- **Router configuration** — `RouterSettings` wired into `Settings.router`; all fields
  configurable via `AIP_ROUTER__*` environment variables.
- **Router unit tests** — catalog completeness, EWMA convergence and thread safety,
  classifier accuracy, all four strategy comparisons, and `RouterService` policy/alias
  integration tests.

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
