"""Structured JSON logging with PII masking applied to every line."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CARD = re.compile(r"\b(?:\d[ -]?){9,15}(\d{4})\b")  # 13-19 digit card-like numbers
_STANDARD_ATTRS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def mask_pii(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    return _CARD.sub(lambda m: f"[card ****{m.group(1)}]", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload |= {k: v for k, v in record.__dict__.items() if k not in _STANDARD_ATTRS}
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return mask_pii(json.dumps(payload, ensure_ascii=False, default=str))


def configure_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """Write JSON logs to `log_file` (default logs/triage.jsonl), away from CLI output."""
    path = log_file or Path("logs") / "triage.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("triage")
    root.handlers = [handler]
    root.setLevel(level)
    root.propagate = False
