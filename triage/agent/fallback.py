"""Safe default when the model cannot produce a valid answer: fail safe, never silent.

The fallback is deliberately neutral (medium urgency, human escalation). Guardrails still
run on it afterwards, so ticket signals such as an Enterprise outage still raise urgency.
"""

from __future__ import annotations

from triage.guardrails.signals import detect_language
from triage.guardrails.templates import holding_reply
from triage.models import (
    Action,
    IssueType,
    LLMTriageOutput,
    Sentiment,
    SentimentTrend,
    Team,
    Ticket,
    Urgency,
)


def fallback_output(ticket: Ticket, reason: str) -> LLMTriageOutput:
    language = detect_language(m.text for m in ticket.messages)
    return LLMTriageOutput(
        urgency=Urgency.MEDIUM,
        product="unknown",
        issue_type=IssueType.OTHER,
        sentiment=Sentiment.NEUTRAL,
        sentiment_trend=SentimentTrend.STABLE,
        language=language,
        intents=[],
        action=Action.ESCALATE_TO_HUMAN,
        target_team=Team.GENERAL_SUPPORT,
        draft_response=holding_reply(language),
        kb_citations=[],
        reasoning=f"Automatic triage failed ({reason}). A human must review this ticket.",
        confidence=0.0,
    )
