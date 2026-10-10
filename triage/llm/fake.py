"""FakeLLM: replays a scripted conversation. Used for tests and `--offline` runs.

Offline mode exercises everything *around* the model (tool execution, parsing, guardrails,
fallbacks) deterministically. It says nothing about real model quality.

Script file format (JSON):
    {"turns": [
        {"tool_calls": [{"name": "get_customer_history", "arguments": {...}}]},
        {"final": { ...LLMTriageOutput fields... }},   # or {"raw_content": "any text"}
    ]}
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from triage.llm.base import ChatMessage, LLMError, LLMFactory, LLMResponse, ToolCall
from triage.models import Ticket

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "data" / "fake_scripts"
DEFAULT_SCRIPT = "_default"


class FakeLLM:
    model = "fake-llm"

    def __init__(self, turns: Sequence[LLMResponse | Exception]) -> None:
        self._turns = list(turns)
        self.requests: list[list[ChatMessage]] = []  # what the agent sent, for assertions

    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
        response_format: dict[str, Any],
    ) -> LLMResponse:
        self.requests.append([dict(m) for m in messages])
        if not self._turns:
            raise LLMError("FakeLLM script exhausted")
        turn = self._turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn

    @classmethod
    def from_file(cls, path: Path) -> FakeLLM:
        raw_turns = json.loads(path.read_text(encoding="utf-8"))["turns"]
        return cls([parse_turn(turn, i) for i, turn in enumerate(raw_turns)])


def parse_turn(raw: dict[str, Any], index: int = 0) -> LLMResponse:
    if "tool_calls" in raw:
        return LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id=f"call_{index}_{n}", name=c["name"], arguments=json.dumps(c["arguments"])
                )
                for n, c in enumerate(raw["tool_calls"])
            ],
        )
    if "final" in raw:
        return LLMResponse(content=json.dumps(raw["final"], ensure_ascii=False))
    return LLMResponse(content=raw["raw_content"])


def scripted_factory(scripts_dir: Path = SCRIPTS_DIR) -> LLMFactory:
    """One FakeLLM per ticket, from `<ticket_id>.json`, else the default script."""

    def for_ticket(ticket: Ticket) -> FakeLLM:
        path = scripts_dir / f"{ticket.id}.json"
        return FakeLLM.from_file(path if path.exists() else scripts_dir / f"{DEFAULT_SCRIPT}.json")

    return for_ticket
