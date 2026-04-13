"""Phase 1: Collect news articles via Gemini + Google Search Grounding."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request

from datetime import date, datetime, timedelta

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from news_collector.models import Article
from news_collector.retry import call_with_retry
from news_collector.storage import Storage
from news_collector.topics import Topic, load_topics, topic_from_genre

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

def _build_search_prompt(
    genre: str, from_date: str, to_date: str, keywords: list[str] | None = None
) -> str:
    parts = [
        f"Search for recent news articles about **{genre}** "
        f"published between {from_date} and {to_date}.",
    ]
    if keywords:
        kw_str = ", ".join(f'"{k}"' for k in keywords)
        parts.append(
            f"\nFocus especially on articles related to these keywords: {kw_str}."
        )
    parts.append(
        f"\nFind notable incidents, announcements, vulnerabilities, "
        f"breaches, policy changes, and other significant developments "
        f"in the {genre} space during this period."
        f"\n\nReturn all distinct articles you can find."
    )
    return "\n".join(parts)

# ──────────────────────────────────────────────
# Client factory
# ──────────────────────────────────────────────

_SEARCH_MODEL = "gemini-2.5-pro"
_EXTRACTION_MODEL = "gemini-2.5-pro"

def _make_client() -> genai.Client:
    from news_collector.config import get_config
    cfg = get_config()
    return genai.Client(
        vertexai=True,
        project=cfg["project"],
        location=cfg["location"],
    )

# ──────────────────────────────────────────────
# Phase 1: Search + extract
# ──────────────────────────────────────────────

def run_collect(args: argparse.Namespace) -> None:
    """Entry point for the collect subcommand."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    from_date = args.from_date or yesterday
    to_date = args.to_date or yesterday

    # Build topic list from --topics file or --genre/--keywords flags
    if args.topics:
        topics = load_topics(args.topics)
    else:
        genre = args.genre or "cybersecurity"
        keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else []
        topics = [topic_from_genre(genre, keywords)]

    storage = Storage(args.db, args.jsonl)
    try:
        total_new = 0
        total_found = 0
        for topic in topics:
            kw_display = f" (keywords: {', '.join(topic.keywords)})" if topic.keywords else ""
            print(
                f"\nCollecting: topic={topic.name}{kw_display}, "
                f"from={from_date}, to={to_date}",
                file=sys.stderr,
            )

            articles = search_news(
                topic.name, from_date, to_date,
                keywords=topic.keywords,
                verbose=args.verbose,
            )
            total_found += len(articles)

            for article in articles:
                if storage.insert(article):
                    total_new += 1
                    if args.verbose:
                        print(f"  + {article.title}", file=sys.stderr)
                elif args.verbose:
                    print(f"  = {article.title} (duplicate)", file=sys.stderr)

        print(
            f"\nDone: {total_new} new articles collected "
            f"({total_found} total found across {len(topics)} topic(s))",
            file=sys.stderr,
        )
    finally:
        storage.close()

def search_news(
    genre: str,
    from_date: str,
    to_date: str,
    *,
    keywords: list[str] | None = None,
    verbose: bool = False,
) -> list[Article]:
    """Search for news articles using Gemini with Google Search Grounding.

    Three-step process:
    1. Use Grounding to search the web and collect raw research text
    2. Resolve redirect URLs to actual source URLs
    3. Use structured output to extract individual articles from the text
    """
    client = _make_client()
    now = datetime.now()

    # Step 1: Search with Grounding
    print("  [Step 1] Searching with Google Search Grounding...", file=sys.stderr)
    raw_text, ref_urls = _search_with_grounding(
        client, genre, from_date, to_date, verbose, keywords=keywords
    )

    if not raw_text.strip():
        print("  No results from search.", file=sys.stderr)
        return []

    # Step 2: Resolve redirect URLs to actual source URLs
    print(f"\n  [Step 2] Resolving {len(ref_urls)} reference URLs...", file=sys.stderr)
    url_mapping = _resolve_urls_batch(ref_urls, verbose=verbose)
    resolved_urls = list(url_mapping.values())

    # Step 3: Extract structured articles
    print(f"  [Step 3] Extracting structured article data...", file=sys.stderr)
    items = _extract_articles(client, raw_text, genre, resolved_urls)

    print(f"  Found {len(items)} articles.", file=sys.stderr)

    # Convert to Article models, resolving any remaining redirect URLs
    articles: list[Article] = []
    for item in items:
        url = _resolve_redirect(item.url) if "vertexaisearch" in item.url else item.url

        pub_date: date | None = None
        if item.published_date:
            try:
                pub_date = date.fromisoformat(item.published_date)
            except ValueError:
                pass

        articles.append(
            Article(
                id=_article_id(url),
                title=item.title,
                url=url,
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
    *,
    keywords: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Use Gemini + Google Search Grounding to find news articles.

    Returns (raw_text, reference_urls) where reference_urls are the actual
    source URLs discovered by Grounding.
    """
    prompt = _build_search_prompt(genre, from_date, to_date, keywords)

    def _run() -> tuple[str, list[str]]:
        parts: list[str] = []
        urls: list[str] = []
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

            if chunk.candidates:
                for candidate in chunk.candidates:
                    meta = getattr(candidate, "grounding_metadata", None)
                    if meta:
                        for gc in getattr(meta, "grounding_chunks", []) or []:
                            web = getattr(gc, "web", None)
                            if web:
                                uri = getattr(web, "uri", "")
                                title = getattr(web, "title", "")
                                if uri:
                                    urls.append(uri)
                                    if verbose:
                                        print(
                                            f"\n    [ref] {uri}",
                                            file=sys.stderr,
                                        )

        print(file=sys.stderr)
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_urls: list[str] = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)
        return "".join(parts), unique_urls

    return call_with_retry(_run, "search")

def _extract_articles(
    client: genai.Client,
    raw_text: str,
    genre: str,
    ref_urls: list[str],
) -> list[_NewsItem]:
    """Extract structured article records from raw search text."""

    url_list = "\n".join(f"- {u}" for u in ref_urls) if ref_urls else "(none available)"

    def _run() -> list[_NewsItem]:
        response = client.models.generate_content(
            model=_EXTRACTION_MODEL,
            contents=(
                f"Extract all distinct news articles from the following research text "
                f"about {genre}. Return each article with its title, URL, source, "
                f"publication date, and summary.\n\n"
                f"IMPORTANT: Use the actual source URLs from the reference list below. "
                f"Do NOT fabricate or guess URLs. If no matching URL is found for an "
                f"article, use the most relevant URL from the reference list.\n\n"
                f"Reference URLs (from Google Search):\n{url_list}\n\n"
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

    return call_with_retry(_run, "extract")

def _resolve_redirect(url: str, timeout: float = 5.0) -> str:
    """Resolve a Vertex AI grounding redirect URL to the actual source URL.

    Returns the original URL unchanged if it is not a redirect or if
    resolution fails.
    """
    if "vertexaisearch.cloud.google.com/grounding-api-redirect" not in url:
        return url
    try:
        req = urllib.request.Request(url, method="HEAD")
        # Use a non-redirecting opener to read the Location header
        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
                return None

        opener = urllib.request.build_opener(_NoRedirect)
        try:
            opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.status in (301, 302, 303, 307, 308):
                location = e.headers.get("Location", "")
                if location:
                    return location
        return url
    except Exception:
        return url

def _resolve_urls_batch(urls: list[str], verbose: bool = False) -> dict[str, str]:
    """Resolve a list of redirect URLs. Returns a mapping old → resolved."""
    mapping: dict[str, str] = {}
    for url in urls:
        resolved = _resolve_redirect(url)
        mapping[url] = resolved
        if verbose and resolved != url:
            print(f"    [resolved] {resolved}", file=sys.stderr)
    return mapping

def _article_id(url: str) -> str:
    """Generate a deterministic article ID from a URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]
