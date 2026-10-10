"""Guardrail rules. Each is a pure function `(output, ctx) -> Fix | None`.

Rules encode business policy that must hold no matter what the model says. They run after
the LLM, in the order listed in `registry.DEFAULT_RULES`.
"""

from __future__ import annotations

from triage.guardrails import signals
from triage.guardrails.base import Fix, GuardrailContext, require
from triage.guardrails.templates import holding_reply
from triage.models import Action, IssueType, Language, LLMTriageOutput, Plan, Team, Urgency

_UNRESOLVED_PAYMENT_STATUSES = {"authorization_pending", "payment_failed"}

# --- grounding & draft safety -------------------------------------------------------------


def unverified_citations(out: LLMTriageOutput, ctx: GuardrailContext) -> Fix | None:
    """The draft may only cite KB articles that a search actually returned in this run."""
    unknown = [c for c in out.kb_citations if c not in ctx.retrieved_kb_ids]
    if not unknown:
        return None
    kept = [c for c in out.kb_citations if c in ctx.retrieved_kb_ids]
    return Fix(f"Cited KB ids never returned by search: {unknown}", {"kb_citations": kept})


def no_unsafe_promises(out: LLMTriageOutput, ctx: GuardrailContext) -> Fix | None:
    """Refunds, fix times and compensation are human decisions; strip them from the draft."""
    promises = signals.find_promises(out.draft_response)
    if not promises:
        return None
    return require(
        out,
        f"Draft made commitments only a human can make: {promises}",
        action=Action.ESCALATE_TO_HUMAN if out.action is Action.AUTO_RESPOND else None,
        team=Team.GENERAL_SUPPORT,
        also={"draft_response": holding_reply(_reply_language(out, ctx))},
    )


def draft_language_matches(out: LLMTriageOutput, ctx: GuardrailContext) -> Fix | None:
    """The reply must be in the customer's language (detected from the ticket, not the model)."""
    expected = ctx.ticket_language
    if expected is Language.OTHER:
        return None
    draft_language = signals.detect_language([out.draft_response])
    also: dict[str, object] = {"language": expected}
    if draft_language is not expected:
        also["draft_response"] = holding_reply(expected)
    return require(
        out,
        f"Customer writes '{expected}', draft is '{draft_language}'",
        # a holding reply answers nothing, so it cannot be sent automatically
        action=Action.ROUTE_TO_SPECIALIST if "draft_response" in also else None,
        team=Team.GENERAL_SUPPORT,
        also=also,
    )


def ungrounded_auto_respond(out: LLMTriageOutput, ctx: GuardrailContext) -> Fix | None:
    """No automatic reply unless it is backed by at least one retrieved KB article."""
    if out.action is not Action.AUTO_RESPOND or out.kb_citations:
        return None
    return require(
        out,
        "Auto-response is not grounded in any retrieved KB article",
        action=Action.ROUTE_TO_SPECIALIST,
        team=Team.GENERAL_SUPPORT,
    )


# --- escalation policy --------------------------------------------------------------------


def billing_dispute_never_auto(out: LLMTriageOutput, ctx: GuardrailContext) -> Fix | None:
    """Money + (chargeback threat or repeated failed/pending payments) -> billing human."""
    is_billing = out.issue_type is IssueType.BILLING or signals.mentions(signals.BILLING, ctx.text)
    threat = signals.mentions(signals.CHARGEBACK, ctx.text)
    unresolved = sum(e.get("status") in _UNRESOLVED_PAYMENT_STATUSES for e in ctx.billing_events)
    if not is_billing or not (threat or unresolved >= 2):
        return None
    evidence = "chargeback/dispute threat" if threat else f"{unresolved} unresolved payments"
    return require(
        out,
        f"Billing issue with {evidence}",
        action=Action.ESCALATE_TO_HUMAN,
        urgency=Urgency.HIGH,
        team=Team.BILLING,
    )


def enterprise_outage_escalate(out: LLMTriageOutput, ctx: GuardrailContext) -> Fix | None:
    """An Enterprise customer who cannot use the product is always critical."""
    if ctx.ticket.customer.plan is not Plan.ENTERPRISE:
        return None
    if out.issue_type is not IssueType.OUTAGE and not signals.mentions(signals.OUTAGE, ctx.text):
        return None
    return require(
        out,
        "Enterprise customer reports an outage",
        action=Action.ESCALATE_TO_HUMAN,
        urgency=Urgency.CRITICAL,
        team=Team.INCIDENT_RESPONSE,
    )


def security_escalate(out: LLMTriageOutput, ctx: GuardrailContext) -> Fix | None:
    if out.issue_type is not IssueType.SECURITY and not signals.mentions(
        signals.SECURITY, ctx.text
    ):
        return None
    return require(
        out,
        "Possible security incident",
        action=Action.ESCALATE_TO_HUMAN,
        urgency=Urgency.HIGH,
        team=Team.SECURITY,
    )


def legal_threat_escalate(out: LLMTriageOutput, ctx: GuardrailContext) -> Fix | None:
    if not signals.mentions(signals.LEGAL, ctx.text):
        return None
    return require(
        out,
        "Legal language in ticket",
        action=Action.ESCALATE_TO_HUMAN,
        urgency=Urgency.HIGH,
        team=Team.ACCOUNT_MANAGEMENT,
    )


def prompt_injection_escalate(out: LLMTriageOutput, ctx: GuardrailContext) -> Fix | None:
    """Attempts to instruct the agent are a red flag; a human should look."""
    if not signals.mentions(signals.INJECTION, ctx.text):
        return None
    return require(
        out,
        "Ticket contains instructions aimed at the agent (possible prompt injection)",
        action=Action.ESCALATE_TO_HUMAN,
        team=Team.GENERAL_SUPPORT,
    )


def low_confidence_escalate(out: LLMTriageOutput, ctx: GuardrailContext) -> Fix | None:
    if out.confidence >= ctx.confidence_threshold:
        return None
    return require(
        out,
        f"Model confidence {out.confidence:.2f} < {ctx.confidence_threshold:.2f}",
        action=Action.ESCALATE_TO_HUMAN,
        team=Team.GENERAL_SUPPORT,
    )


def action_matches_intents(out: LLMTriageOutput, ctx: GuardrailContext) -> Fix | None:
    """The ticket-level action must be at least as cautious as its most cautious intent."""
    if not out.intents:
        return None
    strictest = max(out.intents, key=lambda i: i.action.rank)
    return require(
        out,
        f"Intent '{strictest.summary}' requires {strictest.action}",
        action=strictest.action,
        team=strictest.target_team,
    )


def _reply_language(out: LLMTriageOutput, ctx: GuardrailContext) -> Language:
    return ctx.ticket_language if ctx.ticket_language is not Language.OTHER else out.language
