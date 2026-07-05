"""Unit tests for gateway domain models and accounting helpers."""

from __future__ import annotations

import pytest

from aiplatform.gateway.accounting import (
    estimate_completion_tokens,
    estimate_prompt_tokens,
    fill_missing_usage,
)
from aiplatform.gateway.domain.models import (
    ChatRequest,
    FinishReason,
    Message,
    MessageRole,
    TokenUsage,
)


# ---------------------------------------------------------------------------
# TokenUsage
# ---------------------------------------------------------------------------


def test_token_usage_addition() -> None:
    a = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    b = TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30)
    result = a + b
    assert result.prompt_tokens == 30
    assert result.completion_tokens == 15
    assert result.total_tokens == 45


def test_token_usage_total_defaults_to_sum() -> None:
    usage = TokenUsage(prompt_tokens=7, completion_tokens=3)
    assert usage.total_tokens == 10


# ---------------------------------------------------------------------------
# ChatRequest construction
# ---------------------------------------------------------------------------


def test_chat_request_requires_at_least_one_message() -> None:
    with pytest.raises(Exception):
        ChatRequest(model="gpt-4o", messages=[])


def test_chat_request_valid() -> None:
    req = ChatRequest(
        model="gpt-4o",
        messages=[Message(role=MessageRole.USER, content="hello")],
    )
    assert req.model == "gpt-4o"
    assert len(req.messages) == 1


def test_chat_request_temperature_bounds() -> None:
    with pytest.raises(Exception):
        ChatRequest(
            model="gpt-4o",
            messages=[Message(role=MessageRole.USER, content="hi")],
            temperature=3.0,
        )


# ---------------------------------------------------------------------------
# Accounting helpers
# ---------------------------------------------------------------------------


def test_estimate_prompt_tokens_returns_positive() -> None:
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="What is the capital of France?"),
    ]
    count = estimate_prompt_tokens(messages, model="gpt-4o")
    assert count > 0


def test_estimate_completion_tokens_returns_positive() -> None:
    count = estimate_completion_tokens("Paris is the capital of France.", model="gpt-4o")
    assert count > 0


def test_estimate_prompt_tokens_unknown_model_falls_back() -> None:
    messages = [Message(role=MessageRole.USER, content="hello world")]
    count = estimate_prompt_tokens(messages, model="some-unknown-model-xyz")
    assert count > 0


def test_fill_missing_usage_fills_when_none() -> None:
    messages = [Message(role=MessageRole.USER, content="hi")]
    usage = fill_missing_usage(None, messages=messages, completion="hello", model="gpt-4o")
    assert usage is not None
    assert usage.prompt_tokens > 0
    assert usage.completion_tokens > 0


def test_fill_missing_usage_returns_existing_when_present() -> None:
    existing = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    messages = [Message(role=MessageRole.USER, content="hi")]
    returned = fill_missing_usage(
        existing, messages=messages, completion="hello", model="gpt-4o"
    )
    assert returned is existing


# ---------------------------------------------------------------------------
# Message roles and finish reasons
# ---------------------------------------------------------------------------


def test_message_role_values() -> None:
    assert MessageRole.USER == "user"
    assert MessageRole.ASSISTANT == "assistant"
    assert MessageRole.SYSTEM == "system"
    assert MessageRole.TOOL == "tool"


def test_finish_reason_values() -> None:
    assert FinishReason.STOP == "stop"
    assert FinishReason.LENGTH == "length"
    assert FinishReason.TOOL_CALLS == "tool_calls"
