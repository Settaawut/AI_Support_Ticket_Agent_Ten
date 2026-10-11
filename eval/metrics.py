"""Pure metric functions over (expected, predicted) pairs. No I/O, easy to unit test.

Escalation recall is the headline metric: a missed escalation (an angry customer with
money at risk getting a bot reply) costs far more than an unnecessary one.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

ESCALATE = "escalate_to_human"


@dataclass(frozen=True)
class CaseResult:
    ticket_id: str
    note: str
    expected_urgency: list[str]
    expected_action: str
    urgency: str
    action: str
    guardrails_fired: list[str] = field(default_factory=list)
    fallback_reason: str | None = None

    @property
    def urgency_ok(self) -> bool:
        return self.urgency in self.expected_urgency

    @property
    def action_ok(self) -> bool:
        return self.action == self.expected_action

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"urgency_ok": self.urgency_ok, "action_ok": self.action_ok}


@dataclass(frozen=True)
class Summary:
    total: int
    urgency_accuracy: float
    action_accuracy: float
    escalation_recall: float
    escalation_precision: float
    missed_escalations: list[str]
    unnecessary_escalations: list[str]


def summarise(cases: list[CaseResult]) -> Summary:
    total = len(cases)
    should = {c.ticket_id for c in cases if c.expected_action == ESCALATE}
    did = {c.ticket_id for c in cases if c.action == ESCALATE}
    return Summary(
        total=total,
        urgency_accuracy=_ratio(sum(c.urgency_ok for c in cases), total),
        action_accuracy=_ratio(sum(c.action_ok for c in cases), total),
        escalation_recall=_ratio(len(should & did), len(should)),
        escalation_precision=_ratio(len(should & did), len(did)),
        missed_escalations=sorted(should - did),
        unnecessary_escalations=sorted(did - should),
    )


def _ratio(numerator: int, denominator: int) -> float:
    """Undefined ratios (nothing to measure) count as perfect rather than dividing by zero."""
    return round(numerator / denominator, 3) if denominator else 1.0
