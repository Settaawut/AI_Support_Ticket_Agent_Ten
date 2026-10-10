"""Bundled mock data. Loaded via importlib.resources so it works from any cwd."""

from __future__ import annotations

import json
from functools import cache
from importlib.resources import files
from typing import Any

from triage.models import Ticket


@cache
def load_json(name: str) -> Any:
    return json.loads(files(__package__).joinpath(name).read_text(encoding="utf-8"))


def load_sample_tickets() -> list[Ticket]:
    return [Ticket.model_validate(raw) for raw in load_json("sample_tickets.json")]
