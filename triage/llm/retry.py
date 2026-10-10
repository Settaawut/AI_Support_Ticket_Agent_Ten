"""Exponential backoff with jitter, for transient failures only."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


def with_retry(
    fn: Callable[[], T],
    *,
    retries: int,
    base_delay_s: float,
    is_transient: Callable[[Exception], bool],
    max_delay_s: float = 20.0,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[float], float] = lambda d: random.uniform(d / 2, d),
) -> T:
    """Call `fn`; on a transient error wait base*2^attempt (jittered) and try again.

    Non-transient errors and the final transient error are re-raised unchanged.
    """
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == retries or not is_transient(exc):
                raise
            delay = jitter(min(max_delay_s, base_delay_s * 2**attempt))
            logger.warning(
                "transient LLM error, retrying",
                extra={"attempt": attempt + 1, "delay_s": round(delay, 2), "error": repr(exc)},
            )
            sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
