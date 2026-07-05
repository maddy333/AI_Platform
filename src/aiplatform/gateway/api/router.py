"""Gateway API routes: /v1/chat/completions and /v1/models."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from aiplatform.gateway.api.dependencies import GatewayDep
from aiplatform.gateway.api.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelListResponse,
    ModelObject,
)
from aiplatform.gateway.domain.models import ChatStreamChunk
from aiplatform.gateway.service import GatewayService

logger = structlog.stdlib.get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["gateway"])


def _to_sse(chunk: ChatStreamChunk) -> str:
    return f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"


async def _stream_sse(
    service: GatewayService,
    body: ChatCompletionRequest,
) -> AsyncIterator[str]:
    domain_request = body.to_domain()
    try:
        async for chunk in service.chat_stream(domain_request):
            yield _to_sse(chunk)
    except Exception as exc:
        error_payload = json.dumps(
            {"error": {"message": str(exc), "type": getattr(exc, "error_code", "stream_error")}}
        )
        yield f"data: {error_payload}\n\n"
    finally:
        yield "data: [DONE]\n\n"


@router.post(
    "/chat/completions",
    response_model=ChatCompletionResponse,
    summary="Create chat completion",
)
async def chat_completions(
    request: Request,
    body: ChatCompletionRequest,
    service: GatewayService = GatewayDep,  # type: ignore[assignment]
) -> StreamingResponse | ChatCompletionResponse:
    if body.stream:
        return StreamingResponse(
            _stream_sse(service, body),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    domain_request = body.to_domain()
    return await service.chat_complete(domain_request)


@router.get("/models", response_model=ModelListResponse, summary="List available models")
async def list_models(
    service: GatewayService = GatewayDep,  # type: ignore[assignment]
) -> ModelListResponse:
    seen: set[str] = set()
    models: list[ModelObject] = []
    for provider in service._registry.all():
        if provider.supported_models is not None:
            for mid in sorted(provider.supported_models):
                if mid not in seen:
                    seen.add(mid)
                    models.append(ModelObject(id=mid, owned_by=provider.name))
        else:
            entry = f"{provider.name}/*"
            if entry not in seen:
                seen.add(entry)
                models.append(ModelObject(id=entry, owned_by=provider.name))
    return ModelListResponse(data=models)
