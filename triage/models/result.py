"""Output-side models.

`LLMTriageOutput` is the contract the model must fill (sent as a strict JSON schema).
`TriageResult` extends it with fields only *code* may set (audit trail, usage),
so the model can never fake its own tool usage or guardrail history.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from triage.models.enums import (
    Action,
    IssueType,
    Language,
    Sentiment,
    SentimentTrend,
    Team,
    Urgency,
)


class Intent(BaseModel):
    """One thing the customer wants. A ticket can carry several."""

    summary: str
    issue_type: IssueType
    action: Action
    target_team: Team
    kb_ids: list[str] = Field(description="KB article ids that answer this intent, if any.")


class LLMTriageOutput(BaseModel):
    urgency: Urgency
    product: str = Field(description="Product area or feature concerned, e.g. 'Billing / Pro'.")
    issue_type: IssueType = Field(description="Primary issue type of the ticket.")
    sentiment: Sentiment
    sentiment_trend: SentimentTrend
    language: Language
    intents: list[Intent]
    action: Action
    target_team: Team
    draft_response: str = Field(description="Reply to the customer, in the customer's language.")
    kb_citations: list[str] = Field(description="KB ids the draft relies on.")
    reasoning: str = Field(description="Short, grounded justification (2-4 sentences).")
    confidence: float = Field(ge=0.0, le=1.0)


class GuardrailOverride(BaseModel):
    rule: str
    field: str
    before: str
    after: str
    reason: str


class Usage(BaseModel):
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: int = 0


class TriageResult(LLMTriageOutput):
    ticket_id: str
    tools_used: list[str] = Field(default_factory=list)
    guardrail_overrides: list[GuardrailOverride] = Field(default_factory=list)
    fallback_reason: str | None = None
    usage: Usage = Field(default_factory=Usage)
