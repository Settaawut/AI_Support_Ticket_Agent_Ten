"""Provider-agnostic LLM interface.

The agent only depends on `LLMClient`. Messages and tool specs use the OpenAI chat wire
format because it is the de-facto standard; a different provider adapts at its boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from triage.models import Ticket

ChatMessage = dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string, validated by the tool registry


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)


class LLMError(Exception):
    """The LLM could not produce a response (after retries, or non-retryable)."""


class LLMClient(Protocol):
    model: str

    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
        response_format: dict[str, Any],
    ) -> LLMResponse: ...


# Picks the client for a ticket. Online this returns one shared client; offline it returns
# a FakeLLM loaded with that ticket's script.
LLMFactory = Callable[[Ticket], LLMClient]
