"""Abstract provider port (hexagonal architecture outgoing port).

Every LLM provider adapter implements this Protocol. The gateway service
depends on the protocol, never on a concrete adapter, so providers are
swappable at configuration time with zero application-layer changes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from aiplatform.gateway.domain.models import ChatRequest, ChatResponse, ChatStreamChunk


@runtime_checkable
class LLMProvider(Protocol):
    """Outgoing port: one LLM provider backend."""

    @property
    def name(self) -> str:
        """Stable identifier used in routing tables and metrics labels."""
        ...

    @property
    def supported_models(self) -> frozenset[str] | None:
        """Model IDs this provider can serve; ``None`` means accept-all (e.g. Ollama)."""
        ...

    async def complete(self, request: ChatRequest) -> ChatResponse:
        """Non-streaming chat completion."""
        ...

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        """Streaming chat completion; yields chunks until the final one with usage."""
        ...

    async def health(self) -> None:
        """Raise on failure; used by the readiness probe and the circuit breaker."""
        ...
