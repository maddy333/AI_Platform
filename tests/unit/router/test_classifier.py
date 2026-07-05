"""Unit tests for the rule-based prompt complexity classifier."""

from __future__ import annotations

import pytest

from aiplatform.gateway.domain.models import Message, MessageRole
from aiplatform.router.classifier import classify
from aiplatform.router.domain.models import PromptComplexity


def _msg(content: str, role: MessageRole = MessageRole.USER) -> Message:
    return Message(role=role, content=content)


def test_classify_code_from_fence() -> None:
    messages = [_msg("Fix this:\n```python\ndef foo(): pass\n```")]
    assert classify(messages, prompt_tokens=20) is PromptComplexity.CODE


def test_classify_code_from_keyword() -> None:
    messages = [_msg("Implement def calculate_tax(income):")]
    assert classify(messages, prompt_tokens=10) is PromptComplexity.CODE


def test_classify_code_from_sql() -> None:
    messages = [_msg("Write an SQL query to get all users")]
    assert classify(messages, prompt_tokens=10) is PromptComplexity.CODE


def test_classify_reasoning_explain_why() -> None:
    messages = [_msg("Can you explain why the sky is blue?")]
    assert classify(messages, prompt_tokens=10) is PromptComplexity.REASONING


def test_classify_reasoning_step_by_step() -> None:
    messages = [_msg("Solve this step-by-step: 3x + 7 = 22")]
    assert classify(messages, prompt_tokens=10) is PromptComplexity.REASONING


def test_classify_reasoning_tradeoff() -> None:
    messages = [_msg("Analyze the trade-offs between REST and GraphQL")]
    assert classify(messages, prompt_tokens=15) is PromptComplexity.REASONING


def test_classify_creative_story() -> None:
    messages = [_msg("Write a story about a robot who learns to love")]
    assert classify(messages, prompt_tokens=10) is PromptComplexity.CREATIVE


def test_classify_creative_poem() -> None:
    messages = [_msg("Write a poem about autumn leaves")]
    assert classify(messages, prompt_tokens=8) is PromptComplexity.CREATIVE


def test_classify_complex_from_long_prompt() -> None:
    assert classify([_msg("Hello")], prompt_tokens=500) is PromptComplexity.COMPLEX


def test_classify_simple_short_greeting() -> None:
    assert classify([_msg("Hello!")], prompt_tokens=5) is PromptComplexity.SIMPLE


def test_classify_simple_short_question() -> None:
    assert classify([_msg("What is 2 + 2?")], prompt_tokens=10) is PromptComplexity.SIMPLE


def test_classify_uses_all_messages_in_conversation() -> None:
    messages = [
        _msg("Hello", role=MessageRole.USER),
        _msg("Hi!", role=MessageRole.ASSISTANT),
        _msg("Implement a binary search algorithm", role=MessageRole.USER),
    ]
    assert classify(messages, prompt_tokens=20) is PromptComplexity.CODE
