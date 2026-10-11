"""OpenAI Chat Completions adapter."""

from __future__ import annotations

from typing import Any

import openai

from triage.config import Settings
from triage.llm.base import (
    ChatMessage,
    LLMError,
    LLMFactory,
    LLMResponse,
    TokenUsage,
    ToolCall,
)
from triage.llm.retry import with_retry

_TRANSIENT = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
)


def is_transient(exc: Exception) -> bool:
    return isinstance(exc, _TRANSIENT)


class OpenAIClient:
    def __init__(self, settings: Settings, client: openai.OpenAI | None = None) -> None:
        self.model = settings.model
        self._settings = settings
        # Retries are ours (with_retry) so they are visible in logs and testable;
        # the SDK's built-in retries are disabled to avoid retrying twice.
        self._client = client or openai.OpenAI(timeout=settings.llm_timeout_s, max_retries=0)

    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
        response_format: dict[str, Any],
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "response_format": response_format,
        }
        if tools:  # the API rejects an empty tool list
            kwargs["tools"] = tools
        if self._settings.temperature is not None:  # reasoning models reject temperature
            kwargs["temperature"] = self._settings.temperature
        try:
            completion = with_retry(
                lambda: self._client.chat.completions.create(**kwargs),
                retries=self._settings.llm_max_retries,
                base_delay_s=self._settings.retry_base_delay_s,
                is_transient=is_transient,
            )
        except openai.OpenAIError as exc:
            raise LLMError(f"OpenAI request failed: {exc}") from exc

        message = completion.choices[0].message
        usage = completion.usage
        return LLMResponse(
            content=message.content,
            tool_calls=[
                ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments)
                for c in (message.tool_calls or [])
                if c.type == "function"
            ],
            usage=TokenUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
            ),
        )


def openai_factory(settings: Settings) -> LLMFactory:
    """One shared client for every ticket. Fails fast if OPENAI_API_KEY is missing."""
    client = OpenAIClient(settings)
    return lambda _ticket: client
