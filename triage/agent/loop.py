"""The tool-calling loop: model -> tools -> model ... -> validated final answer.

The loop never raises for model or tool problems. It returns either a validated output or a
`failure` reason, and the service turns a failure into a safe escalation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from triage.agent.parsing import (
    RESPONSE_FORMAT,
    OutputValidationError,
    parse_output,
    repair_instruction,
)
from triage.llm import ChatMessage, LLMClient, LLMError, LLMResponse
from triage.models import LLMTriageOutput, Ticket
from triage.observability.trace import Stopwatch, Trace, TraceEvent
from triage.prompts import render_ticket
from triage.tools import ToolOutcome, ToolRegistry


@dataclass
class LoopOutcome:
    output: LLMTriageOutput | None = None
    failure: str | None = None
    tool_outcomes: list[ToolOutcome] = field(default_factory=list)


class AgentLoop:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        system_prompt: str,
        max_iterations: int,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._system_prompt = system_prompt
        self._max_iterations = max_iterations

    def run(self, ticket: Ticket, trace: Trace) -> LoopOutcome:
        outcome = LoopOutcome()
        messages: list[ChatMessage] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": render_ticket(ticket)},
        ]
        repair_used = False
        tool_cache: dict[tuple[str, str], ToolOutcome] = {}

        for _ in range(self._max_iterations):
            try:
                response = self._call_llm(messages, trace)
            except LLMError as exc:
                outcome.failure = f"LLM unavailable: {exc}"
                return outcome

            if response.tool_calls:
                messages.append(_assistant_tool_message(response))
                for call in response.tool_calls:
                    result = self._run_tool(call.name, call.arguments, trace, tool_cache)
                    outcome.tool_outcomes.append(result)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": result.as_message_content(),
                        }
                    )
                continue

            messages.append({"role": "assistant", "content": response.content or ""})
            try:
                outcome.output = parse_output(response.content)
                return outcome
            except OutputValidationError as exc:
                trace.record(
                    TraceEvent("repair", "output_validation", ok=False, detail={"error": str(exc)})
                )
                if repair_used:
                    outcome.failure = f"Invalid output after one repair attempt: {exc}"
                    return outcome
                repair_used = True
                messages.append({"role": "user", "content": repair_instruction(exc)})

        outcome.failure = f"No valid final answer within {self._max_iterations} iterations"
        return outcome

    def _call_llm(self, messages: list[ChatMessage], trace: Trace) -> LLMResponse:
        with Stopwatch() as sw:
            response = self._llm.complete(messages, self._registry.specs(), RESPONSE_FORMAT)
        trace.record_llm_call(response.usage.prompt_tokens, response.usage.completion_tokens, sw.ms)
        return response

    def _run_tool(
        self,
        name: str,
        arguments: str,
        trace: Trace,
        cache: dict[tuple[str, str], ToolOutcome],
    ) -> ToolOutcome:
        """Execute a tool call; an identical repeat call is answered from the run's cache."""
        key = (name, _canonical(arguments))
        cached = key in cache
        with Stopwatch() as sw:
            result = cache[key] if cached else self._registry.execute(name, arguments)
        cache[key] = result
        detail: dict[str, Any] = {"arguments": arguments, "cached": cached}
        if not result.ok:
            detail["error"] = result.payload["error"]
        trace.record(TraceEvent("tool_call", name, ok=result.ok, latency_ms=sw.ms, detail=detail))
        return result


def _assistant_tool_message(response: LLMResponse) -> ChatMessage:
    return {
        "role": "assistant",
        "content": response.content,
        "tool_calls": [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.name, "arguments": c.arguments},
            }
            for c in response.tool_calls
        ],
    }


def _canonical(arguments: str) -> str:
    try:
        return json.dumps(json.loads(arguments), sort_keys=True)
    except json.JSONDecodeError:
        return arguments
