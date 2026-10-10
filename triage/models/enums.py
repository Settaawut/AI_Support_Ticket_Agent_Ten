"""Closed vocabularies shared by the model contract, guardrails and eval."""

from __future__ import annotations

from enum import StrEnum


class Urgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _URGENCY_ORDER.index(self)


_URGENCY_ORDER = [Urgency.LOW, Urgency.MEDIUM, Urgency.HIGH, Urgency.CRITICAL]


class Action(StrEnum):
    AUTO_RESPOND = "auto_respond"
    ROUTE_TO_SPECIALIST = "route_to_specialist"
    ESCALATE_TO_HUMAN = "escalate_to_human"

    @property
    def rank(self) -> int:
        """Higher rank = more human involvement. Guardrails may only move up."""
        return _ACTION_ORDER.index(self)


_ACTION_ORDER = [Action.AUTO_RESPOND, Action.ROUTE_TO_SPECIALIST, Action.ESCALATE_TO_HUMAN]


def max_urgency(a: Urgency, b: Urgency) -> Urgency:
    return a if a.rank >= b.rank else b


def max_action(a: Action, b: Action) -> Action:
    return a if a.rank >= b.rank else b


class IssueType(StrEnum):
    BILLING = "billing"
    OUTAGE = "outage"
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    HOW_TO = "how_to"
    ACCOUNT_ACCESS = "account_access"
    SECURITY = "security"
    SPAM = "spam"
    OTHER = "other"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"


class SentimentTrend(StrEnum):
    STABLE = "stable"
    ESCALATING = "escalating"
    IMPROVING = "improving"


class Language(StrEnum):
    TH = "th"
    EN = "en"
    OTHER = "other"


class Team(StrEnum):
    BILLING = "billing"
    TECHNICAL_SUPPORT = "technical_support"
    INCIDENT_RESPONSE = "incident_response"
    PRODUCT_ENGINEERING = "product_engineering"
    ACCOUNT_MANAGEMENT = "account_management"
    SECURITY = "security"
    GENERAL_SUPPORT = "general_support"
    NONE = "none"


class Plan(StrEnum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
