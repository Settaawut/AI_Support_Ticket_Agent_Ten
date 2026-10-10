"""Shared builders. Tests construct inputs explicitly instead of relying on hidden fixtures."""

from __future__ import annotations

import json
from typing import Any

import pytest

from triage.data import load_sample_tickets
from triage.llm import LLMResponse, ToolCall
from triage.models import Ticket


def output_dict(**overrides: Any) -> dict[str, Any]:
    """A valid LLMTriageOutput payload for a harmless English how-to ticket."""
    base: dict[str, Any] = {
        "urgency": "low",
        "product": "Desktop app / Appearance",
        "issue_type": "how_to",
        "sentiment": "neutral",
        "sentiment_trend": "stable",
        "language": "en",
        "intents": [
            {
                "summary": "How to enable dark mode",
                "issue_type": "how_to",
                "action": "auto_respond",
                "target_team": "none",
                "kb_ids": ["KB-UI-001"],
            }
        ],
        "action": "auto_respond",
        "target_team": "none",
        "draft_response": "You can switch themes in Settings > Appearance.",
        "kb_citations": ["KB-UI-001"],
        "reasoning": "Simple how-to answered by KB-UI-001.",
        "confidence": 0.9,
    }
    return base | overrides


def final(**overrides: Any) -> LLMResponse:
    return LLMResponse(content=json.dumps(output_dict(**overrides), ensure_ascii=False))


def tool_turn(*calls: tuple[str, dict[str, Any]]) -> LLMResponse:
    return LLMResponse(
        content=None,
        tool_calls=[
            ToolCall(id=f"call_{i}", name=name, arguments=json.dumps(args))
            for i, (name, args) in enumerate(calls)
        ],
    )


def make_ticket(*texts: str, plan: str = "pro", region: str = "United Kingdom") -> Ticket:
    return Ticket.model_validate(
        {
            "id": "T-TEST",
            "customer": {"id": "cus_1003", "plan": plan, "region": region, "tenure_months": 3},
            "messages": [{"age": "now", "text": t} for t in texts],
        }
    )


@pytest.fixture
def samples() -> dict[str, Ticket]:
    return {t.id: t for t in load_sample_tickets()}
