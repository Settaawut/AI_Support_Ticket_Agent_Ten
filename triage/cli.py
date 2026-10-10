"""Command line entry point.

python -m triage run --all                 # bundled sample tickets, real OpenAI model
python -m triage run --all --offline       # same, scripted FakeLLM, no API key needed
python -m triage run --ticket my.json --json --verbose
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import openai
from pydantic import ValidationError
from rich.console import Console

from triage.agent.service import TriageService
from triage.config import Settings
from triage.data import load_sample_tickets
from triage.llm import LLMFactory, scripted_factory
from triage.llm.openai_client import openai_factory
from triage.models import Ticket
from triage.observability.logging import configure_logging
from triage.render import render_run

EXIT_USAGE_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="triage", description="Support ticket triage agent")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Triage one or more tickets")
    source = run.add_mutually_exclusive_group()
    source.add_argument("--all", action="store_true", help="Bundled sample tickets (default)")
    source.add_argument("--ticket", type=Path, help="JSON file with one ticket or a list")
    run.add_argument("--json", action="store_true", help="Print results as JSON")
    run.add_argument("--verbose", action="store_true", help="Show the per-ticket trace")
    run.add_argument("--offline", action="store_true", help="Use scripted FakeLLM (no API key)")
    return parser


def load_tickets(path: Path | None) -> list[Ticket]:
    if path is None:
        return load_sample_tickets()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Ticket.model_validate(t) for t in (raw if isinstance(raw, list) else [raw])]


def make_llm_factory(offline: bool, settings: Settings) -> LLMFactory:
    return scripted_factory() if offline else openai_factory(settings)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    errors = Console(stderr=True)

    try:
        tickets = load_tickets(args.ticket)
        service = TriageService(make_llm_factory(args.offline, settings), settings)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        errors.print(f"[red]Could not load tickets:[/] {exc}")
        return EXIT_USAGE_ERROR
    except openai.OpenAIError as exc:  # e.g. OPENAI_API_KEY not set
        errors.print(f"[red]OpenAI client error:[/] {exc}\nSet OPENAI_API_KEY or use --offline.")
        return EXIT_USAGE_ERROR

    runs = [service.triage(ticket) for ticket in tickets]

    if args.json:
        payload = [run.result.model_dump(mode="json") for run in runs]
        if isinstance(sys.stdout, io.TextIOWrapper):
            # Windows defaults to a legacy code page when output is redirected; Thai needs UTF-8.
            sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        console = Console()
        mode = "offline (FakeLLM)" if args.offline else f"model {settings.model}"
        console.print(f"[dim]Triaged {len(runs)} ticket(s) with {mode}[/]")
        for run in runs:
            render_run(console, run, verbose=args.verbose)
    return 0
