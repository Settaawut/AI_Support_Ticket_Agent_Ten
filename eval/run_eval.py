"""Run the labelled dataset through the triage service and report metrics.

    python -m eval.run_eval              # real model (needs OPENAI_API_KEY)
    python -m eval.run_eval --offline    # scripted FakeLLM: tests the harness + guardrails

Exit code is 1 when any escalation is missed, so this can gate CI.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from eval.metrics import CaseResult, Summary, summarise
from triage.agent.service import TriageService
from triage.cli import make_llm_factory
from triage.config import Settings
from triage.models import Ticket
from triage.observability.logging import configure_logging

EVAL_DIR = Path(__file__).resolve().parent
DATASET = EVAL_DIR / "dataset.jsonl"
REPORTS = EVAL_DIR / "reports"


def load_dataset(path: Path = DATASET) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def evaluate(service: TriageService, rows: list[dict[str, Any]]) -> list[CaseResult]:
    cases = []
    for row in rows:
        result = service.triage(Ticket.model_validate(row["ticket"])).result
        cases.append(
            CaseResult(
                ticket_id=result.ticket_id,
                note=row.get("note", ""),
                expected_urgency=row["expected"]["urgency"],
                expected_action=row["expected"]["action"],
                urgency=result.urgency.value,
                action=result.action.value,
                guardrails_fired=sorted({o.rule for o in result.guardrail_overrides}),
                fallback_reason=result.fallback_reason,
            )
        )
    return cases


def write_report(cases: list[CaseResult], summary: Summary, mode: str) -> Path:
    REPORTS.mkdir(exist_ok=True)
    path = REPORTS / f"eval-{mode}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    report = {"mode": mode, "summary": asdict(summary), "cases": [c.to_dict() for c in cases]}
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def print_report(console: Console, cases: list[CaseResult], summary: Summary) -> None:
    table = Table(title="Per-ticket results")
    for column in ("Ticket", "Urgency (exp)", "Action (exp)", "Guardrails", "Note"):
        table.add_column(column)
    for c in cases:
        u_style = "green" if c.urgency_ok else "red"
        a_style = "green" if c.action_ok else "red"
        table.add_row(
            c.ticket_id,
            f"[{u_style}]{c.urgency}[/] ({'/'.join(c.expected_urgency)})",
            f"[{a_style}]{c.action}[/] ({c.expected_action})",
            ", ".join(c.guardrails_fired) or "-",
            c.note,
        )
    console.print(table)
    recall_style = "bold green" if not summary.missed_escalations else "bold red"
    console.print(
        f"Urgency accuracy {summary.urgency_accuracy:.0%} | "
        f"Action accuracy {summary.action_accuracy:.0%} | "
        f"[{recall_style}]Escalation recall {summary.escalation_recall:.0%}[/] | "
        f"Escalation precision {summary.escalation_precision:.0%}"
    )
    console.print(f"Missed escalations: {summary.missed_escalations or 'none'}")
    console.print(f"Unnecessary escalations: {summary.unnecessary_escalations or 'none'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the triage agent")
    parser.add_argument("--offline", action="store_true", help="Use scripted FakeLLM")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    configure_logging(settings.log_level)
    service = TriageService(make_llm_factory(args.offline, settings), settings)
    mode = "offline" if args.offline else settings.model

    cases = evaluate(service, load_dataset(args.dataset))
    summary = summarise(cases)
    console = Console()
    print_report(console, cases, summary)
    console.print(f"[dim]Report written to {write_report(cases, summary, mode)}[/]")
    return 1 if summary.missed_escalations else 0


if __name__ == "__main__":
    raise SystemExit(main())
