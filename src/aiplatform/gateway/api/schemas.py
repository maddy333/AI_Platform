"""OpenAI-compatible HTTP request/response schemas for the gateway API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from aiplatform.gateway.domain.models import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    Message,
    ResponseFormat,
    Tool,
    ToolChoice,
)


class ChatCompletionRequest(BaseModel):
    """POST /v1/chat/completions — OpenAI-compatible wire schema."""

    model: str
    messages: list[Message] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    stop: list[str] | str | None = None
    stream: bool = False
    tools: list[Tool] | None = None
    tool_choice: ToolChoice | None = None
    response_format: ResponseFormat | None = None
    seed: int | None = None
    user: str | None = None
    # Gateway extension: pin to a specific provider
    x_provider: str | None = Field(default=None)

    model_config = {"populate_by_name": True}

    def to_domain(self) -> ChatRequest:
        stop = self.stop if isinstance(self.stop, list) else ([self.stop] if self.stop else None)
        return ChatRequest(
            model=self.model,
            messages=self.messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            frequency_penalty=self.frequency_penalty,
            presence_penalty=self.presence_penalty,
            stop=stop,
            stream=self.stream,
            tools=self.tools,
            tool_choice=self.tool_choice,
            response_format=self.response_format,
            seed=self.seed,
            user=self.user,
            metadata={"pinned_provider": self.x_provider} if self.x_provider else {},
        )


ChatCompletionResponse = ChatResponse
ChatCompletionChunk = ChatStreamChunk


class ModelObject(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "ai-platform"


class ModelListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelObject]
