"""The ordered list of active guardrails.

To add a guardrail: write a `(output, ctx) -> Fix | None` function in `rules.py` (or a new
module) and append it here. Order matters only where a rule reads another's result
(e.g. citations are verified before grounding is checked).
"""

from __future__ import annotations

from triage.guardrails import rules
from triage.guardrails.base import Rule

DEFAULT_RULES: tuple[Rule, ...] = (
    # grounding & draft safety
    rules.unverified_citations,
    rules.no_unsafe_promises,
    rules.draft_language_matches,
    rules.ungrounded_auto_respond,
    # escalation policy
    rules.billing_dispute_never_auto,
    rules.enterprise_outage_escalate,
    rules.security_escalate,
    rules.legal_threat_escalate,
    rules.prompt_injection_escalate,
    rules.low_confidence_escalate,
    rules.action_matches_intents,
)
