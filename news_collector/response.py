"""Read the JSON body of a Gemini response."""

from __future__ import annotations

import json
from typing import Any


def response_json(text: str | None, label: str) -> Any:
    """Parse a structured-output response, or raise a ValueError naming the call.

    The SDK types ``response.text`` as optional: a blocked or empty answer has
    no text, and ``json.loads(None)`` would fail with a TypeError that says
    nothing about which call returned nothing.
    """
    if not text:
        raise ValueError(f"Gemini returned no text for {label}")
    return json.loads(text)
