"""The ordered list of active guardrails.

To add a guardrail: write a `(output, ctx) -> Fix | None` function in `rules.py` (or a new
module) and add it here. Order matters in two ways: a rule may read an earlier rule's
result (citations are verified before grounding is checked), and the first rule to
raise the action picks the team, so team-specific rules come before generic ones.
"""

from __future__ import annotations

from triage.guardrails import rules
from triage.guardrails.base import Rule

DEFAULT_RULES: tuple[Rule, ...] = (
    # grounding first: later rules read the verified citations
    rules.unverified_citations,
    # specific escalation policy: these know the right team, so they run before
    # the generic rules below claim the escalation for general_support
    rules.billing_dispute_never_auto,
    rules.enterprise_outage_escalate,
    rules.security_escalate,
    rules.legal_threat_escalate,
    rules.prompt_injection_escalate,
    # generic draft safety and confidence checks
    rules.no_unsafe_promises,
    rules.draft_language_matches,
    rules.ungrounded_auto_respond,
    rules.low_confidence_escalate,
    rules.action_matches_intents,
)
