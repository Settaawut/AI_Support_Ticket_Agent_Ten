"""Rich terminal views of a triage run. Presentation only: no decisions are made here."""

from __future__ import annotations

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from triage.agent.service import TriageRun
from triage.models import Action, TriageResult, Urgency

URGENCY_STYLE = {
    Urgency.CRITICAL: "bold white on red",
    Urgency.HIGH: "bold red",
    Urgency.MEDIUM: "yellow",
    Urgency.LOW: "green",
}
ACTION_STYLE = {
    Action.ESCALATE_TO_HUMAN: "bold red",
    Action.ROUTE_TO_SPECIALIST: "bold yellow",
    Action.AUTO_RESPOND: "bold green",
}


def render_run(console: Console, run: TriageRun, verbose: bool = False) -> None:
    r = run.result
    parts: list[RenderableType] = [_summary(r), _intents(r)]
    parts.append(Panel(r.draft_response, title="Draft response", border_style="cyan"))
    parts.append(Text.assemble(("Reasoning: ", "bold"), r.reasoning))
    if r.guardrail_overrides:
        parts.append(_overrides(r))
    if r.fallback_reason:
        parts.append(Text(f"Fallback: {r.fallback_reason}", style="bold red"))
    if verbose:
        parts.append(_trace(run))
    parts.append(_usage(r))
    console.print(Panel(Group(*parts), title=f"[bold]{r.ticket_id}[/]", expand=True))


def _summary(r: TriageResult) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Urgency", Text(r.urgency.upper(), style=URGENCY_STYLE[r.urgency]))
    table.add_row("Action", Text(r.action, style=ACTION_STYLE[r.action]))
    table.add_row("Team", r.target_team)
    table.add_row("Issue", f"{r.issue_type} | {r.product}")
    table.add_row("Sentiment", f"{r.sentiment} ({r.sentiment_trend})")
    table.add_row("Language", r.language)
    table.add_row("Confidence", f"{r.confidence:.2f}")
    table.add_row("Tools used", ", ".join(r.tools_used) or "none")
    table.add_row("KB cited", ", ".join(r.kb_citations) or "none")
    return table


def _intents(r: TriageResult) -> Table:
    table = Table(title="Intents", title_justify="left", expand=True)
    for column in ("Intent", "Type", "Action", "Team", "KB"):
        table.add_column(column)
    for i in r.intents:
        table.add_row(
            i.summary,
            i.issue_type,
            Text(i.action, style=ACTION_STYLE[i.action]),
            i.target_team,
            ", ".join(i.kb_ids),
        )
    return table


def _overrides(r: TriageResult) -> Table:
    table = Table(title="Guardrail overrides", title_justify="left", border_style="yellow")
    for column in ("Rule", "Field", "Before", "After", "Reason"):
        table.add_column(column)
    for o in r.guardrail_overrides:
        table.add_row(o.rule, o.field, o.before, o.after, o.reason)
    return table


def _trace(run: TriageRun) -> Table:
    table = Table(title="Trace", title_justify="left", border_style="dim")
    for column in ("#", "Kind", "Name", "OK", "ms", "Detail"):
        table.add_column(column)
    for n, e in enumerate(run.trace.events, 1):
        detail = ", ".join(f"{k}={v}" for k, v in e.detail.items())
        table.add_row(str(n), e.kind, e.name, "✓" if e.ok else "✗", str(e.latency_ms), detail[:90])
    return table


def _usage(r: TriageResult) -> Text:
    u = r.usage
    return Text(
        f"{u.llm_calls} LLM calls | {u.prompt_tokens}+{u.completion_tokens} tokens | "
        f"~${u.estimated_cost_usd:.5f} | {u.latency_ms} ms",
        style="dim",
    )
