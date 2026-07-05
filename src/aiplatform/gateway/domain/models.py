"""Provider-agnostic domain models for the AI Gateway.

All provider adapters translate to/from these types so the gateway service
and API layer have a single, stable model surface regardless of which
upstream is servicing the request.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


class ResponseFormatType(StrEnum):
    TEXT = "text"
    JSON_OBJECT = "json_object"
    JSON_SCHEMA = "json_schema"


class ImageURL(BaseModel):
    url: str
    detail: Literal["auto", "low", "high"] = "auto"


class TextContentPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImageContentPart(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: ImageURL


ContentPart = TextContentPart | ImageContentPart


class FunctionDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    strict: bool | None = None


class Tool(BaseModel):
    type: Literal["function"] = "function"
    function: FunctionDefinition


class FunctionCall(BaseModel):
    name: str
    arguments: str  # JSON string


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: FunctionCall


ToolChoice = Literal["none", "auto", "required"] | dict[str, Any]


class ResponseFormat(BaseModel):
    type: ResponseFormatType = ResponseFormatType.TEXT
    json_schema: dict[str, Any] | None = None


class Message(BaseModel):
    role: MessageRole
    content: str | list[ContentPart] | None = None
    name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

    @model_validator(mode="after")
    def validate_tool_message(self) -> Message:
        if self.role is MessageRole.TOOL and self.tool_call_id is None:
            raise ValueError("tool messages must include tool_call_id")
        return self

    def text_content(self) -> str:
        if isinstance(self.content, str):
            return self.content
        if isinstance(self.content, list):
            return " ".join(p.text for p in self.content if isinstance(p, TextContentPart))
        return ""


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class ChatRequest(BaseModel):
    """Provider-agnostic chat completion request."""

    model: str
    messages: list[Message] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    stop: list[str] | None = None
    stream: bool = False
    tools: list[Tool] | None = None
    tool_choice: ToolChoice | None = None
    response_format: ResponseFormat | None = None
    seed: int | None = None
    user: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("stop", mode="before")
    @classmethod
    def normalise_stop(cls, v: list[str] | str | None) -> list[str] | None:
        if isinstance(v, str):
            return [v]
        return v


class ChatChoice(BaseModel):
    index: int
    message: Message
    finish_reason: FinishReason | None = None


class ChatResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatChoice]
    usage: TokenUsage = Field(default_factory=TokenUsage)
    provider: str | None = None


class StreamDelta(BaseModel):
    role: MessageRole | None = None
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


class StreamChoice(BaseModel):
    index: int
    delta: StreamDelta
    finish_reason: FinishReason | None = None


class ChatStreamChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[StreamChoice]
    usage: TokenUsage | None = None
    provider: str | None = None
