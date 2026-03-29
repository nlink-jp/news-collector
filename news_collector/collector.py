"""Phase 1: Collect news articles via Gemini + Google Search Grounding."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from news_collector.models import Article
from news_collector.storage import Storage

_T = TypeVar("_T")

# Retry settings for 429 / RESOURCE_EXHAUSTED
_MAX_RETRIES = 5
_RETRY_BASE_DELAY = 5.0


# ──────────────────────────────────────────────
# Response models for structured extraction
# ──────────────────────────────────────────────


class _NewsItem(BaseModel):
    """A single news article discovered by search."""

    title: str = Field(description="Article headline")
    url: str = Field(description="Full URL to the article")
    source: str = Field(description="Publisher or media outlet name")
    published_date: str | None = Field(
        default=None, description="Publication date in YYYY-MM-DD format if known"
    )
    summary: str = Field(description="Brief summary of the article content (2-3 sentences)")


class _NewsSearchResult(BaseModel):
    """Collection of news articles from a search."""

    articles: list[_NewsItem] = Field(description="List of discovered news articles")


# ──────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────

_SEARCH_SYSTEM_PROMPT = """\
You are a news research agent. Your task is to find recent news articles
on the given topic using Google Search.

For each article found, extract:
- The exact article title (headline)
- The full URL
- The publisher/source name
- The publication date (YYYY-MM-DD) if available
- A 2-3 sentence summary of the article content

Requirements:
- Find as many distinct, relevant articles as possible (aim for 10-20)
- Focus on articles published within the specified date range
- Include articles from diverse sources (not just one outlet)
- Only include real articles with actual URLs — do not fabricate
- If a publication date is uncertain, set it to null
"""


def _build_search_prompt(genre: str, from_date: str, to_date: str) -> str:
    return (
        f"Search for recent news articles about **{genre}** "
        f"published between {from_date} and {to_date}.\n\n"
        f"Find notable incidents, announcements, vulnerabilities, "
        f"breaches, policy changes, and other significant developments "
        f"in the {genre} space during this period.\n\n"
        f"Return all distinct articles you can find."
    )


# ──────────────────────────────────────────────
# Retry logic
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

_SEARCH_MODEL = "gemini-2.5-pro"
_EXTRACTION_MODEL = "gemini-2.5-pro"


def _make_client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )


# ──────────────────────────────────────────────
# Phase 1: Search + extract
# ──────────────────────────────────────────────


def run_collect(args: argparse.Namespace) -> None:
    """Entry point for the collect subcommand."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    from_date = args.from_date or yesterday
    to_date = args.to_date or yesterday

    print(f"Collecting: genre={args.genre}, from={from_date}, to={to_date}", file=sys.stderr)

    articles = search_news(args.genre, from_date, to_date, verbose=args.verbose)

    storage = Storage(args.db, args.jsonl)
    try:
        new_count = 0
        for article in articles:
            if storage.insert(article):
                new_count += 1
                if args.verbose:
                    print(f"  + {article.title}", file=sys.stderr)
            elif args.verbose:
                print(f"  = {article.title} (duplicate)", file=sys.stderr)
        print(
            f"Done: {new_count} new articles collected ({len(articles)} total found)",
            file=sys.stderr,
        )
    finally:
        storage.close()


def search_news(
    genre: str, from_date: str, to_date: str, *, verbose: bool = False
) -> list[Article]:
    """Search for news articles using Gemini with Google Search Grounding.

    Two-step process:
    1. Use Grounding to search the web and collect raw research text
    2. Use structured output to extract individual articles from the text
    """
    client = _make_client()
    now = datetime.now()

    # Step 1: Search with Grounding
    print("  [Step 1] Searching with Google Search Grounding...", file=sys.stderr)
    raw_text = _search_with_grounding(client, genre, from_date, to_date, verbose)

    if not raw_text.strip():
        print("  No results from search.", file=sys.stderr)
        return []

    # Step 2: Extract structured articles
    print("\n  [Step 2] Extracting structured article data...", file=sys.stderr)
    items = _extract_articles(client, raw_text, genre)

    print(f"  Found {len(items)} articles.", file=sys.stderr)

    # Convert to Article models
    articles: list[Article] = []
    for item in items:
        pub_date: date | None = None
        if item.published_date:
            try:
                pub_date = date.fromisoformat(item.published_date)
            except ValueError:
                pass

        articles.append(
            Article(
                id=_article_id(item.url),
                title=item.title,
                url=item.url,
                source=item.source,
                published_date=pub_date,
                genre=genre,
                summary_raw=item.summary,
                collected_at=now,
            )
        )
    return articles


def _search_with_grounding(
    client: genai.Client,
    genre: str,
    from_date: str,
    to_date: str,
    verbose: bool,
) -> str:
    """Use Gemini + Google Search Grounding to find news articles."""
    prompt = _build_search_prompt(genre, from_date, to_date)

    def _run() -> str:
        parts: list[str] = []
        for chunk in client.models.generate_content_stream(
            model=_SEARCH_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SEARCH_SYSTEM_PROMPT,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        ):
            if chunk.text:
                parts.append(chunk.text)
                print(chunk.text, end="", flush=True, file=sys.stderr)

            if verbose and chunk.candidates:
                for candidate in chunk.candidates:
                    meta = getattr(candidate, "grounding_metadata", None)
                    if meta:
                        for gc in getattr(meta, "grounding_chunks", []) or []:
                            web = getattr(gc, "web", None)
                            if web:
                                print(
                                    f"\n    [ref] {getattr(web, 'uri', '')}",
                                    file=sys.stderr,
                                )

        print(file=sys.stderr)
        return "".join(parts)

    return _call_with_retry(_run, "search")


def _extract_articles(
    client: genai.Client,
    raw_text: str,
    genre: str,
) -> list[_NewsItem]:
    """Extract structured article records from raw search text."""

    def _run() -> list[_NewsItem]:
        response = client.models.generate_content(
            model=_EXTRACTION_MODEL,
            contents=(
                f"Extract all distinct news articles from the following research text "
                f"about {genre}. Return each article with its title, URL, source, "
                f"publication date, and summary.\n\n"
                f"Research text:\n{raw_text}"
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_NewsSearchResult,
            ),
        )
        data = json.loads(response.text)
        result = _NewsSearchResult(**data)
        return result.articles

    return _call_with_retry(_run, "extract")


def _article_id(url: str) -> str:
    """Generate a deterministic article ID from a URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]
