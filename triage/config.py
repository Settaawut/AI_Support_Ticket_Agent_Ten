"""Runtime settings, read once from the environment.

Everything tunable lives here so behaviour can change without touching code paths.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# USD per 1M tokens (input, output). Used only for cost *estimates* in traces.
MODEL_PRICES_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default


def _env_temperature(default: float | None) -> float | None:
    raw = os.getenv("TRIAGE_TEMPERATURE")
    if raw is None or raw == "":
        return default
    return None if raw.lower() == "none" else float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    model: str = "gpt-4o-mini"
    temperature: float | None = 0.0  # None = omit (reasoning models reject it)
    max_iterations: int = 6
    llm_timeout_s: float = 30.0
    llm_max_retries: int = 3
    retry_base_delay_s: float = 1.0
    confidence_threshold: float = 0.6
    log_level: str = "INFO"
    prices_per_1m: dict[str, tuple[float, float]] = field(
        default_factory=lambda: dict(MODEL_PRICES_PER_1M)
    )

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            model=os.getenv("OPENAI_MODEL", cls.model),
            temperature=_env_temperature(cls.temperature),
            max_iterations=_env_int("TRIAGE_MAX_ITERATIONS", cls.max_iterations),
            llm_timeout_s=_env_float("TRIAGE_LLM_TIMEOUT_S", cls.llm_timeout_s),
            confidence_threshold=_env_float(
                "TRIAGE_CONFIDENCE_THRESHOLD", cls.confidence_threshold
            ),
            log_level=os.getenv("TRIAGE_LOG_LEVEL", cls.log_level),
        )
