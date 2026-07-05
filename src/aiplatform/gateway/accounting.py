"""Token accounting: count tokens before/after provider calls.

Uses tiktoken for OpenAI-family models. Falls back to a whitespace-split
estimate for models where tiktoken has no encoding so non-OpenAI providers
work without hard-failing on unknown model names.

Actual provider-reported usage (from the response body) is always preferred;
this module fills gaps when the provider returns zero or partial usage.
"""

from __future__ import annotations

import structlog

from aiplatform.gateway.domain.models import ChatRequest, Message, TokenUsage

logger = structlog.stdlib.get_logger(__name__)

_MESSAGE_OVERHEAD = 4  # tokens added per message by chat formatting
_REPLY_OVERHEAD = 3


def _get_encoding(model: str) -> Any:  # type: ignore[return]
    try:
        import tiktoken  # type: ignore[import-untyped]

        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


from typing import Any


def _tokens_for_message(message: Message, encoding: Any) -> int:
    text = message.text_content()
    if message.name:
        text = f"{message.name}\n{text}"
    if encoding is not None:
        return len(encoding.encode(text)) + _MESSAGE_OVERHEAD
    return max(1, len(text.split()) * 4 // 3) + _MESSAGE_OVERHEAD


def estimate_prompt_tokens(request: ChatRequest) -> int:
    """Estimate token count for the prompt before sending to the provider."""
    encoding = _get_encoding(request.model)
    return sum(_tokens_for_message(m, encoding) for m in request.messages) + _REPLY_OVERHEAD


def estimate_completion_tokens(text: str, model: str) -> int:
    """Estimate tokens for a completion text string."""
    encoding = _get_encoding(model)
    if encoding is not None:
        return len(encoding.encode(text))
    return max(1, len(text.split()) * 4 // 3)


def fill_missing_usage(
    usage: TokenUsage, request: ChatRequest, completion_text: str
) -> TokenUsage:
    """Return a usage object with any zero fields estimated."""
    prompt = usage.prompt_tokens or estimate_prompt_tokens(request)
    completion = usage.completion_tokens or estimate_completion_tokens(
        completion_text, request.model
    )
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
    )
