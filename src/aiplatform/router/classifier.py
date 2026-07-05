"""Rule-based prompt complexity classifier.

Classifies prompts without an LLM call — pure heuristics over token count
and keyword signals. Feeds the balanced strategy's quality-weight adjustment.
"""

from __future__ import annotations

import re

from aiplatform.gateway.domain.models import Message
from aiplatform.router.domain.models import PromptComplexity

_CODE_PATTERNS = re.compile(
    r"```|def |class |import |function |algorithm|implement|debug|refactor|"
    r"optimize|sql|query|schema|dockerfile|kubernetes|terraform",
    re.IGNORECASE,
)
_REASONING_PATTERNS = re.compile(
    r"reason|explain why|step.by.step|proof|derive|theorem|calculate|solve|"
    r"analyze|compare and contrast|trade.off|pros and cons",
    re.IGNORECASE,
)
_CREATIVE_PATTERNS = re.compile(
    r"write a (story|poem|song|essay|blog|script|novel)|creative|imagine|"
    r"brainstorm|generate ideas|fictional",
    re.IGNORECASE,
)
_COMPLEX_THRESHOLD_TOKENS = 300


def _text_from_messages(messages: list[Message]) -> str:
    parts = []
    for msg in messages:
        if isinstance(msg.content, str):
            parts.append(msg.content)
        elif isinstance(msg.content, list):
            for part in msg.content:
                if hasattr(part, "text"):
                    parts.append(part.text)
    return " ".join(parts)


def classify(messages: list[Message], prompt_tokens: int) -> PromptComplexity:
    """Return the dominant complexity class for a conversation."""
    text = _text_from_messages(messages)

    if _CODE_PATTERNS.search(text):
        return PromptComplexity.CODE

    if _REASONING_PATTERNS.search(text):
        return PromptComplexity.REASONING

    if _CREATIVE_PATTERNS.search(text):
        return PromptComplexity.CREATIVE

    if prompt_tokens >= _COMPLEX_THRESHOLD_TOKENS:
        return PromptComplexity.COMPLEX

    return PromptComplexity.SIMPLE
