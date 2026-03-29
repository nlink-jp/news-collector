"""Shared retry logic for Gemini API rate limiting."""

from __future__ import annotations

import random
import sys
import time
from collections.abc import Callable
from typing import TypeVar

_T = TypeVar("_T")

MAX_RETRIES = 6
BASE_DELAY = 5.0
MAX_DELAY = 120.0


def is_rate_limit(exc: Exception) -> bool:
    """Check if an exception is a Gemini rate limit error."""
    msg = str(exc).lower()
    return "429" in msg or "resource_exhausted" in msg


def call_with_retry(fn: Callable[[], _T], label: str = "") -> _T:
    """Call fn with exponential backoff + jitter on rate limit errors.

    Retry schedule (base=5s): 5s, 10s, 20s, 40s, 80s, 120s (capped).
    Each delay has ±1s jitter added.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return fn()
        except Exception as e:
            if is_rate_limit(e) and attempt < MAX_RETRIES - 1:
                delay = min(BASE_DELAY * (2**attempt), MAX_DELAY) + random.uniform(0, 1)
                tag = f" [{label}]" if label else ""
                print(
                    f"\n  Rate limited (429){tag} — retrying in {delay:.1f}s "
                    f"({attempt + 1}/{MAX_RETRIES - 1})",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            raise
    raise RuntimeError("unreachable")
