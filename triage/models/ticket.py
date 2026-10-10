"""Input-side models: what a support ticket looks like."""

from __future__ import annotations

from pydantic import BaseModel, Field

from triage.models.enums import Plan


class Message(BaseModel):
    age: str = Field(description="Relative timestamp as shown to agents, e.g. '2 hours ago'.")
    text: str


class CustomerProfile(BaseModel):
    id: str
    plan: Plan
    region: str
    seats: int | None = None
    tenure_months: int
    notes: str = ""


class Ticket(BaseModel):
    id: str
    customer: CustomerProfile
    messages: list[Message] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        """All customer text, oldest first. Used by deterministic signal checks."""
        return "\n".join(m.text for m in self.messages)

    @property
    def is_empty(self) -> bool:
        return not self.full_text.strip()
