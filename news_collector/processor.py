"""Phase 2: Tag and summarize collected articles via Gemini Flash."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from news_collector.storage import Storage

_T = TypeVar("_T")

_MAX_RETRIES = 5
_RETRY_BASE_DELAY = 5.0
_FLASH_MODEL = "gemini-2.5-flash"


# ──────────────────────────────────────────────
# Response model
# ──────────────────────────────────────────────


class _ProcessingResult(BaseModel):
    """Structured output from the tagging and summarization step."""

    tags: list[str] = Field(
        description="Topic tags for the article (3-8 tags). "
        "Use lowercase, specific terms. Examples: ransomware, data-breach, "
        "healthcare, cve, phishing, zero-day, nation-state, policy"
    )
    summary: str = Field(
        description="Concise summary of the article in 2-4 sentences. "
        "Include: what happened, who was affected, and why it matters."
    )


# ──────────────────────────────────────────────
# Prompt
# ──────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a cybersecurity news analyst. Given a news article's title and raw
summary, produce:

1. **Tags**: 3-8 lowercase topic tags that categorize the article.
   Use specific, reusable terms such as:
   - Incident type: data-breach, ransomware, phishing, zero-day, supply-chain, ddos
   - Sector: healthcare, finance, government, education, retail, critical-infrastructure
   - Actor: nation-state, apt, hacktivist, insider-threat
   - Topic: vulnerability, cve, policy, regulation, ai-security, cloud-security
   - Region: us, eu, asia, middle-east (only if geographically significant)

2. **Summary**: A concise 2-4 sentence summary covering what happened,
   who was affected, and the significance.

Be factual. Do not speculate beyond what the input states.
"""


# ──────────────────────────────────────────────
# Retry logic (same pattern as collector)
# ──────────────────────────────────────────────


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "resource_exhausted" in msg


def _call_with_retry(fn: Callable[[], _T], label: str = "") -> _T:
    for attempt in range(_MAX_RETRIES):
        try:
            return fn()
        except Exception as e:
            if _is_rate_limit(e) and attempt < _MAX_RETRIES - 1:
                delay = _RETRY_BASE_DELAY * (2**attempt) + random.uniform(0, 1)
                tag = f" [{label}]" if label else ""
                print(
                    f"\n  Rate limited (429){tag} — retrying in {delay:.1f}s "
                    f"({attempt + 1}/{_MAX_RETRIES - 1})",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            raise
    raise RuntimeError("unreachable")


# ──────────────────────────────────────────────
# Client factory
# ──────────────────────────────────────────────


def _make_client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )


# ──────────────────────────────────────────────
# Core processing
# ──────────────────────────────────────────────


def generate_tags_and_summary(
    client: genai.Client, title: str, raw_summary: str
) -> tuple[list[str], str]:
    """Generate tags and summary for a single article using Gemini Flash."""

    def _run() -> tuple[list[str], str]:
        response = client.models.generate_content(
            model=_FLASH_MODEL,
            contents=(
                f"Article title: {title}\n\n"
                f"Raw summary:\n{raw_summary}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=_ProcessingResult,
            ),
        )
        data = json.loads(response.text)
        result = _ProcessingResult(**data)
        return result.tags, result.summary

    return _call_with_retry(_run, "process")


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────


def run_process(args: argparse.Namespace) -> None:
    """Entry point for the process subcommand."""
    client = _make_client()
    storage = Storage(args.db)
    try:
        if args.force:
            articles = storage.get_all(args.from_date, args.to_date)
        else:
            articles = storage.get_unprocessed(args.from_date, args.to_date)

        if not articles:
            print("No articles to process.", file=sys.stderr)
            return

        print(f"Processing {len(articles)} articles...", file=sys.stderr)

        processed = 0
        for article in articles:
            tags, summary = generate_tags_and_summary(
                client, article.title, article.summary_raw
            )
            storage.update_processed(
                article.id,
                tags=tags,
                summary=summary,
                processed_at=datetime.now().isoformat(),
            )
            processed += 1
            if args.verbose:
                print(f"  ✓ [{processed}/{len(articles)}] {article.title}", file=sys.stderr)
                print(f"    tags: {tags}", file=sys.stderr)
            else:
                print(f"  ✓ {processed}/{len(articles)}", end="\r", file=sys.stderr)

        print(f"\nDone: {processed} articles processed.", file=sys.stderr)
    finally:
        storage.close()
