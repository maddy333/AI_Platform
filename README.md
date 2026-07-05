# AI Platform

Enterprise-grade AI platform: unified LLM gateway, intelligent model routing,
prompt registry, enterprise RAG, agent orchestration, evaluation, and full
observability — built to run on Kubernetes.

[![CI](https://github.com/ai-platform/ai-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/ai-platform/ai-platform/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)
![Coverage](https://img.shields.io/badge/coverage-80%25-brightgreen)

---

## Why

Organisations adopting LLMs face the same platform problems: provider lock-in,
uncontrolled spend, no audit trail, brittle prompts, and unobservable failures.
This platform solves them once, centrally:

- **One API, many providers** — OpenAI, Anthropic, Gemini, Azure OpenAI, Ollama,
  vLLM, and OpenRouter behind a single OpenAI-compatible inference API.
- **Intelligent routing** — requests scored on cost, latency, quality, context size,
  tenant policy, and budget; virtual model aliases (`smart`, `fast`, `cheap`).
- **Reliability** — async circuit breakers, automatic provider failover, tenacity
  retries, token-bucket rate limiting.
- **Governance** — versioned prompts with approval workflows, RBAC, tenant isolation,
  audit logs, token accounting.
- **Observability** — OpenTelemetry traces, Prometheus metrics, structured JSON logs,
  Grafana dashboards.

---

## Current Status

| Milestone | Capability | Status |
|---|---|---|
| 1 | App skeleton, config, logging, health, telemetry, CI | ✅ |
| 2 | AI Gateway — unified inference API, 7 providers, circuit breakers, failover | ✅ |
| 3 | Intelligent Model Router — cost/latency/quality scoring, virtual aliases | ✅ |
| 4 | Persistence & Auth — PostgreSQL, Redis, JWT/API keys, RBAC, tenants | 🔜 |
| 5 | Prompt Registry — versioning, approvals, evaluation | 🔜 |
| 6 | Enterprise RAG — ingestion, hybrid retrieval, reranking | 🔜 |
| 7 | Agent Platform — LangGraph, memory, human approval | 🔜 |
| 8 | Evaluation — RAGAS, LLM-as-a-judge, regression suites | 🔜 |
| 9 | Deployment — Docker, Helm, Terraform, Kubernetes | 🔜 |
| 10 | Admin Dashboard — Next.js management UI | 🔜 |

---

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) ≥ 0.5 (Python 3.13 is auto-provisioned).

```bash
git clone <repo-url> && cd ai-platform
make install          # uv sync --all-groups
cp .env.example .env  # edit with your provider keys
make run              # http://localhost:8000
```

Verify the platform is healthy:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Send a chat completion (requires at least one provider enabled in `.env`):

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

Use a virtual model alias — the router selects the best available model automatically:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "smart",
    "messages": [{"role": "user", "content": "Explain transformers."}]
  }'
```

Interactive API docs are served at `/docs` in non-production environments.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                       API Layer                          │
│  POST /v1/chat/completions   GET /v1/models              │
│  GET  /health/live           GET /health/ready           │
└───────────────┬──────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────┐
│                   Model Router (M3)                       │
│  Scoring strategies: cost · latency · quality · balanced  │
│  Policy enforcement · Virtual aliases · Budget caps       │
└───────────────┬──────────────────────────────────────────┘
                │  ordered candidate list
┌───────────────▼──────────────────────────────────────────┐
│                    Gateway Service                        │
│  Provider selection · Failover · Rate limiting            │
│  Token accounting · Request normalisation                 │
└──────┬──────────┬──────────┬──────────┬───────────┬──────┘
       │          │          │          │           │
   OpenAI   Anthropic    Gemini   Azure OAI   Ollama/vLLM
```

The backend follows **Clean/Hexagonal Architecture**: domain logic is isolated from
transport (FastAPI) and infrastructure (providers, databases), wired at the edges via
dependency injection. Cross-cutting concerns live in `aiplatform.core`.

```
src/aiplatform/
├── app.py              # application factory: middleware, routers, lifespan
├── __main__.py         # uvicorn entrypoint
├── core/               # config, logging, telemetry, errors, middleware
├── api/                # health endpoints
├── gateway/            # AI Gateway: providers, circuit breakers, service
│   ├── domain/         # domain models and port definitions
│   ├── providers/      # OpenAI, Anthropic, Gemini, Azure, Ollama, vLLM, OR
│   ├── api/            # HTTP router (/v1/chat/completions, /v1/models)
│   └── service.py      # GatewayService: failover orchestration
└── router/             # Intelligent Model Router
    ├── domain/         # RoutingContext, RoutingDecision, RoutingPolicy
    ├── strategies/     # cost, latency, quality, balanced scoring
    ├── catalog.py      # model profiles: context window, pricing, quality
    ├── latency.py      # EWMA latency tracker per model
    ├── classifier.py   # rule-based prompt complexity classifier
    └── service.py      # RouterService: policy + strategy orchestration
```

Architecture Decision Records land in `docs/adr/` as subsystems are built.

---

## Provider Configuration

All providers are **disabled by default**. Enable them in `.env`:

### OpenAI

```bash
AIP_GATEWAY__OPENAI__ENABLED=true
AIP_GATEWAY__OPENAI__API_KEY=sk-...
```

### Anthropic

```bash
AIP_GATEWAY__ANTHROPIC__ENABLED=true
AIP_GATEWAY__ANTHROPIC__API_KEY=sk-ant-...
```

### Google Gemini

```bash
AIP_GATEWAY__GEMINI__ENABLED=true
AIP_GATEWAY__GEMINI__API_KEY=AIza...
```

### Azure OpenAI

```bash
AIP_GATEWAY__AZURE_OPENAI__ENABLED=true
AIP_GATEWAY__AZURE_OPENAI__API_KEY=...
AIP_GATEWAY__AZURE_OPENAI__AZURE_ENDPOINT=https://<resource>.openai.azure.com
AIP_GATEWAY__AZURE_OPENAI__AZURE_DEPLOYMENT=gpt-4o
```

### Ollama (self-hosted)

```bash
AIP_GATEWAY__OLLAMA__ENABLED=true
AIP_GATEWAY__OLLAMA__BASE_URL=http://localhost:11434
```

### vLLM (self-hosted)

```bash
AIP_GATEWAY__VLLM__ENABLED=true
AIP_GATEWAY__VLLM__BASE_URL=http://localhost:8001/v1
```

---

## Model Router

The router scores candidate models across four strategies:

| Strategy | Optimises for | Best when |
|---|---|---|
| `cost` | Lowest USD per request | Batch jobs, high-volume dev |
| `latency` | Lowest EWMA response time | Real-time UX |
| `quality` | Highest benchmark score | Critical / complex tasks |
| `balanced` | Weighted blend (default) | General use |

### Virtual Model Aliases

Use these instead of hardcoding provider-specific model IDs:

| Alias | Resolves to |
|---|---|
| `smart` | Highest quality available model |
| `fast` | Lowest latency available model |
| `cheap` | Lowest cost available model |
| `balanced` | Balanced scoring winner |

```bash
# Route to the best quality model your enabled providers offer
curl http://localhost:8000/v1/chat/completions \
  -d '{"model": "smart", "messages": [...]}'
```

### Routing Configuration

```bash
AIP_ROUTER__DEFAULT_STRATEGY=balanced   # cost | latency | quality | balanced
AIP_ROUTER__COST_WEIGHT=0.35
AIP_ROUTER__LATENCY_WEIGHT=0.35
AIP_ROUTER__QUALITY_WEIGHT=0.30
AIP_ROUTER__LATENCY_ALPHA=0.2           # EWMA smoothing factor (0–1)
```

---

## API Reference

### `POST /v1/chat/completions`

OpenAI-compatible chat completion endpoint.

| Field | Type | Description |
|---|---|---|
| `model` | string | Model ID or virtual alias (`smart`, `fast`, `cheap`, `balanced`) |
| `messages` | array | Conversation history (min 1 message) |
| `stream` | boolean | Enable SSE streaming |
| `temperature` | float | 0.0–2.0 |
| `max_tokens` | integer | Max completion tokens |
| `tools` | array | OpenAI-format tool definitions |
| `x_provider` | string | Pin to a specific provider (bypasses router) |

**Streaming**: `text/event-stream` with `data: {...}\n\n` frames, terminated by `data: [DONE]`.

### `GET /v1/models`

Returns available models across all enabled providers.

### `GET /health/live`

Kubernetes liveness probe — `200` when the process is running.

### `GET /health/ready`

Kubernetes readiness probe — `200` when all dependency checks pass, `503` otherwise.

---

## Development

```bash
make install     # uv sync --all-groups
make run         # uvicorn with reload
make lint        # ruff check + format check
make typecheck   # mypy --strict
make test        # pytest
make coverage    # pytest + coverage (80% gate)
make check       # lint + typecheck + coverage
```

### Running locally with Ollama

```bash
ollama pull llama3.2
AIP_GATEWAY__OLLAMA__ENABLED=true make run
curl http://localhost:8000/v1/chat/completions \
  -d '{"model": "cheap", "messages": [{"role": "user", "content": "hi"}]}'
```

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `AIP_ENVIRONMENT` | `development` | `development` / `test` / `staging` / `production` |
| `AIP_SERVER__PORT` | `8000` | HTTP listen port |
| `AIP_LOGGING__LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `AIP_LOGGING__FORMAT` | `json` | `json` (production) / `console` (dev) |
| `AIP_TELEMETRY__ENABLED` | `false` | Enable OTLP trace export |
| `AIP_TELEMETRY__OTLP_ENDPOINT` | `http://localhost:4318` | Collector endpoint |
| `AIP_CORS__ALLOW_ORIGINS` | `[]` | JSON array; empty disables CORS |
| `AIP_GATEWAY__<PROVIDER>__ENABLED` | `false` | Activate a provider |
| `AIP_GATEWAY__<PROVIDER>__API_KEY` | — | Provider API key |
| `AIP_ROUTER__DEFAULT_STRATEGY` | `balanced` | Default routing strategy |

See [.env.example](.env.example) for the full list.

---

## Roadmap

1. ✅ **Foundation** — FastAPI, config, logging, health, telemetry, CI
2. ✅ **AI Gateway** — unified inference API, 7 providers, circuit breakers, failover
3. ✅ **Model Router** — cost/latency/quality scoring, virtual aliases, policy enforcement
4. 🔜 **Persistence & Auth** — PostgreSQL, Redis, JWT/API keys, RBAC, tenant isolation
5. 🔜 **Prompt Registry** — versioning, rollbacks, approval workflow, evaluation
6. 🔜 **Enterprise RAG** — ingestion pipeline, hybrid retrieval, vector store adapters
7. 🔜 **Agent Platform** — LangGraph orchestration, checkpoints, human-in-the-loop
8. 🔜 **Evaluation** — RAGAS, LLM-as-a-judge, regression suites, dashboards
9. 🔜 **Deployment** — Docker, Helm charts, Terraform modules, Kubernetes manifests
10. 🔜 **Admin Dashboard** — Next.js management UI

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
