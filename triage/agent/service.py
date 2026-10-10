"""TriageService: Ticket -> TriageResult. The only entry point the CLI, eval and tests use.

Pipeline: input guard -> agent loop (LLM + tools) -> fallback if needed -> guardrails.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from triage.agent.fallback import fallback_output
from triage.agent.loop import AgentLoop, LoopOutcome
from triage.config import Settings
from triage.guardrails import DEFAULT_RULES, GuardrailContext, Rule, apply_rules
from triage.llm import LLMFactory
from triage.models import Ticket, TriageResult
from triage.observability.trace import Trace, TraceEvent
from triage.prompts import load_system_prompt
from triage.tools import ToolRegistry, default_registry


@dataclass(frozen=True)
class TriageRun:
    result: TriageResult
    trace: Trace


class TriageService:
    def __init__(
        self,
        llm_factory: LLMFactory,
        settings: Settings | None = None,
        registry: ToolRegistry | None = None,
        rules: Sequence[Rule] = DEFAULT_RULES,
        system_prompt: str | None = None,
    ) -> None:
        self._llm_factory = llm_factory
        self._settings = settings or Settings()
        self._registry = registry or default_registry()
        self._rules = rules
        self._system_prompt = system_prompt or load_system_prompt()

    def triage(self, ticket: Ticket) -> TriageRun:
        llm = self._llm_factory(ticket)
        trace = Trace(ticket.id, llm.model)

        if ticket.is_empty:  # input guard: nothing to triage, don't spend tokens
            outcome = LoopOutcome(failure="ticket has no message text")
        else:
            loop = AgentLoop(
                llm, self._registry, self._system_prompt, self._settings.max_iterations
            )
            outcome = loop.run(ticket, trace)

        output = outcome.output
        if output is None:
            reason = outcome.failure or "unknown failure"
            trace.record(
                TraceEvent("fallback", "escalate_to_human", ok=False, detail={"reason": reason})
            )
            output = fallback_output(ticket, reason)

        context = GuardrailContext(
            ticket, tuple(outcome.tool_outcomes), self._settings.confidence_threshold
        )
        output, overrides = apply_rules(output, context, self._rules)
        for o in overrides:
            trace.record(
                TraceEvent(
                    "guardrail",
                    o.rule,
                    detail={"field": o.field, "before": o.before, "after": o.after},
                )
            )

        result = TriageResult(
            **output.model_dump(),
            ticket_id=ticket.id,
            tools_used=trace.tools_used,
            guardrail_overrides=overrides,
            fallback_reason=outcome.failure,
            usage=trace.usage(self._settings.prices_per_1m),
        )
        return TriageRun(result, trace)
