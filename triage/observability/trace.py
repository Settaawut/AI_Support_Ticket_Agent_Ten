"""Per-ticket trace: every LLM call, tool call, repair, guardrail override and fallback.

Each event is also emitted as a structured log line, so logs and the CLI trace view come
from the same source.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from triage.models import Usage

logger = logging.getLogger("triage.trace")


@dataclass(frozen=True)
class TraceEvent:
    kind: str  # llm_call | tool_call | repair | guardrail | fallback
    name: str
    ok: bool = True
    latency_ms: int = 0
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Trace:
    ticket_id: str
    model: str
    events: list[TraceEvent] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    _started: float = field(default_factory=time.perf_counter)

    def record(self, event: TraceEvent) -> None:
        self.events.append(event)
        logger.info(
            event.kind,
            extra={
                "ticket_id": self.ticket_id,
                "event": event.name,
                "ok": event.ok,
                "latency_ms": event.latency_ms,
                **event.detail,
            },
        )

    def record_llm_call(self, prompt_tokens: int, completion_tokens: int, latency_ms: int) -> None:
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.record(
            TraceEvent(
                "llm_call",
                self.model,
                latency_ms=latency_ms,
                detail={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
            )
        )

    @property
    def tools_used(self) -> list[str]:
        """Distinct tool names in call order."""
        return list(dict.fromkeys(e.name for e in self.events if e.kind == "tool_call"))

    def usage(self, prices_per_1m: dict[str, tuple[float, float]]) -> Usage:
        input_price, output_price = prices_per_1m.get(self.model, (0.0, 0.0))
        cost = (self.prompt_tokens * input_price + self.completion_tokens * output_price) / 1e6
        return Usage(
            llm_calls=sum(1 for e in self.events if e.kind == "llm_call"),
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            estimated_cost_usd=round(cost, 6),
            latency_ms=int((time.perf_counter() - self._started) * 1000),
        )


class Stopwatch:
    """`with Stopwatch() as sw: ...; sw.ms`"""

    def __enter__(self) -> Stopwatch:
        self._start = time.perf_counter()
        self.ms = 0
        return self

    def __exit__(self, *_: object) -> None:
        self.ms = int((time.perf_counter() - self._start) * 1000)
