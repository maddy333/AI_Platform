# AI Platform

Enterprise-grade AI platform: a unified LLM gateway with intelligent model routing,
prompt registry, enterprise RAG, agent orchestration, evaluation, and full
observability — built to run on Kubernetes.

[![CI](https://github.com/ai-platform/ai-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/ai-platform/ai-platform/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)

## Why

Organisations adopting LLMs face the same platform problems: provider lock-in,
uncontrolled spend, no audit trail, brittle prompts, and unobservable failures.
This platform solves them once, centrally:

- **One API, many providers** — OpenAI, Anthropic, Gemini, Azure OpenAI, Ollama,
  vLLM, and OpenRouter behind a single inference API; switch via configuration.
- **Intelligent routing** — requests routed on cost, latency, health, context
  size, tenant policy, and budget.
- **Governance** — versioned prompts with approval workflows, RBAC, tenant
  isolation, audit logs, token accounting.
- **Reliability** — retries, circuit breakers, provider failover, rate limiting.
- **Observability** — OpenTelemetry traces, Prometheus metrics, structured logs.

## Current Status

Milestone 1 (platform foundation) is complete:

| Capability | Status |
|---|---|
| Application skeleton (FastAPI, app factory, lifespan) | ✅ |
| Twelve-factor configuration (`AIP_*` env vars) | ✅ |
| Structured logging (structlog, JSON/console) | ✅ |
| Request ID propagation + access logs | ✅ |
| Security headers, RFC 9457 error model | ✅ |
| Health probes with pluggable dependency checks | ✅ |
| OpenTelemetry tracing bootstrap | ✅ |
| CI (lint, types, tests, coverage gate) | ✅ |
| AI Gateway & providers | 🔜 Milestone 2 |
| Model router, prompt registry, RAG, agents, evals | 🔜 Roadmap |

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) (Python 3.13 is provisioned automatically).

```bash
git clone <repo-url> && cd ai-platform
make install          # uv sync --all-groups
cp .env.example .env  # local configuration
make run              # serve on http://localhost:8000
```

Verify:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Interactive API docs are served at `/docs` outside production environments.

## Development

```bash
make lint        # ruff check + format check
make typecheck   # mypy --strict
make test        # pytest
make coverage    # pytest with coverage (80% gate)
make check       # all of the above
```

## Configuration

All configuration comes from the environment with the `AIP_` prefix and `__`
as the nesting delimiter (see [.env.example](.env.example)):

| Variable | Default | Description |
|---|---|---|
| `AIP_ENVIRONMENT` | `development` | `development` / `test` / `staging` / `production` |
| `AIP_SERVER__PORT` | `8000` | HTTP port |
| `AIP_LOGGING__LEVEL` | `INFO` | Log level |
| `AIP_LOGGING__FORMAT` | `json` | `json` or `console` |
| `AIP_TELEMETRY__ENABLED` | `false` | Enable OTLP trace export |
| `AIP_TELEMETRY__OTLP_ENDPOINT` | `http://localhost:4318` | Collector endpoint |
| `AIP_CORS__ALLOW_ORIGINS` | `[]` | JSON array; empty disables CORS |

## Architecture

The backend follows Clean/Hexagonal Architecture: domain logic is isolated from
transport (FastAPI) and infrastructure (PostgreSQL, Redis, providers), which are
wired in at the edges via dependency injection. Cross-cutting concerns —
configuration, logging, telemetry, error handling — live in `aiplatform.core`.

```
src/aiplatform/
├── app.py          # application factory: middleware, handlers, routers
├── __main__.py     # uvicorn entrypoint
├── core/           # config, logging, telemetry, errors, middleware
└── api/            # HTTP surface (health; gateway API in Milestone 2)
```

Architecture documentation and ADRs land in `docs/` as subsystems are built.

## Roadmap

1. ✅ **Foundation** — app skeleton, config, logging, errors, health, telemetry, CI
2. 🔜 **AI Gateway** — unified inference API, streaming, multi-provider adapters
3. 🔜 **Reliability** — retries, circuit breakers, rate limiting, failover
4. 🔜 **Model Router** — cost/latency/policy-aware routing
5. 🔜 **Persistence & Auth** — PostgreSQL, Redis, JWT/API keys, RBAC, tenants
6. 🔜 **Prompt Registry** — versioning, approvals, evaluation
7. 🔜 **RAG** — ingestion, hybrid retrieval, reranking, vector store adapters
8. 🔜 **Agents** — LangGraph orchestration, checkpoints, human approval
9. 🔜 **Evaluation** — RAGAS, LLM-as-a-judge, regression suites
10. 🔜 **Deployment** — Docker, Helm, Terraform, Kubernetes manifests
11. 🔜 **Admin Dashboard** — Next.js management UI

## License

Apache License 2.0 — see [LICENSE](LICENSE).
