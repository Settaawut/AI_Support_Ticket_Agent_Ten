"""Guardrail contract and engine.

A rule is a pure function `(output, context) -> Fix | None`. It never mutates anything and
never writes audit records: the engine applies the fix, diffs the fields to produce
`GuardrailOverride` entries, and enforces the one invariant every rule must respect:

    guardrails may raise `action` and `urgency`, never lower them.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from pydantic import BaseModel

from triage.guardrails.signals import detect_language
from triage.models import (
    Action,
    GuardrailOverride,
    Language,
    LLMTriageOutput,
    Team,
    Ticket,
    Urgency,
)
from triage.tools import ToolOutcome


@dataclass(frozen=True)
class GuardrailContext:
    """Everything a rule may look at besides the model output. Derived views are cached."""

    ticket: Ticket
    tool_outcomes: Sequence[ToolOutcome] = ()
    confidence_threshold: float = 0.6

    @cached_property
    def text(self) -> str:
        return self.ticket.full_text

    @cached_property
    def ticket_language(self) -> Language:
        return detect_language(m.text for m in self.ticket.messages)

    @cached_property
    def retrieved_kb_ids(self) -> frozenset[str]:
        return frozenset(
            article["id"]
            for o in self._ok("search_knowledge_base")
            for article in o.payload.get("results", [])
        )

    @cached_property
    def billing_events(self) -> list[dict[str, Any]]:
        return [e for o in self._ok("get_customer_history") for e in o.payload["billing_events"]]

    def _ok(self, tool: str) -> list[ToolOutcome]:
        return [o for o in self.tool_outcomes if o.name == tool and o.ok]


@dataclass(frozen=True)
class Fix:
    reason: str
    changes: dict[str, Any] = field(default_factory=dict)


Rule = Callable[[LLMTriageOutput, GuardrailContext], Fix | None]


def require(
    output: LLMTriageOutput,
    reason: str,
    *,
    action: Action | None = None,
    urgency: Urgency | None = None,
    team: Team | None = None,
    also: dict[str, Any] | None = None,
) -> Fix | None:
    """Build a Fix that raises action/urgency to at least the given level (if needed).

    The team is only reassigned together with a raised action. `also` carries
    any other field changes (e.g. a replaced draft). Returns None when nothing changes.
    """
    changes: dict[str, Any] = {k: v for k, v in (also or {}).items() if getattr(output, k) != v}
    if action is not None and action.rank > output.action.rank:
        changes["action"] = action
        if team is not None and team is not output.target_team:
            changes["target_team"] = team
    if urgency is not None and urgency.rank > output.urgency.rank:
        changes["urgency"] = urgency
    return Fix(reason, changes) if changes else None


class GuardrailViolation(AssertionError):
    """A rule tried to lower action or urgency: a bug in the rule, not in the model."""


def apply_rules(
    output: LLMTriageOutput, ctx: GuardrailContext, rules: Sequence[Rule]
) -> tuple[LLMTriageOutput, list[GuardrailOverride]]:
    overrides: list[GuardrailOverride] = []
    for rule in rules:
        fix = rule(output, ctx)
        if fix is None or not fix.changes:
            continue
        updated = output.model_copy(update=fix.changes)
        if updated.action.rank < output.action.rank or updated.urgency.rank < output.urgency.rank:
            raise GuardrailViolation(f"{rule.__name__} tried to lower action or urgency")
        overrides += [
            GuardrailOverride(
                rule=rule.__name__, field=name, before=before, after=after, reason=fix.reason
            )
            for name, value in fix.changes.items()
            if getattr(output, name) != value
            for before, after in [_describe_change(getattr(output, name), value)]
        ]
        output = updated
    return output, overrides


def _describe_change(before: Any, after: Any, limit: int = 80) -> tuple[str, str]:
    """Readable before/after strings; long values are cut around the first difference."""
    old, new = _as_text(before), _as_text(after)
    if max(len(old), len(new)) <= limit:
        return old, new
    start = next((i for i, (a, b) in enumerate(zip(old, new, strict=False)) if a != b), 0)
    start = max(0, min(start, len(old), len(new)) - 20)
    return _window(old, start, limit), _window(new, start, limit)


def _as_text(value: Any) -> str:
    if isinstance(value, list):
        return json.dumps(
            [v.model_dump(mode="json") if isinstance(v, BaseModel) else v for v in value],
            ensure_ascii=False,
        )
    return str(value)  # StrEnum members render as their value


def _window(text: str, start: int, limit: int) -> str:
    snippet = text[start : start + limit]
    return ("…" if start else "") + snippet + ("…" if start + limit < len(text) else "")
