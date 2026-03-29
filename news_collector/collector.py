"""Phase 1: Collect news articles via Gemini + Google Search Grounding."""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date, datetime, timedelta

from news_collector.models import Article
from news_collector.storage import Storage


def run_collect(args: argparse.Namespace) -> None:
    """Entry point for the collect subcommand."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    from_date = args.from_date or yesterday
    to_date = args.to_date or yesterday

    print(f"Collecting: genre={args.genre}, from={from_date}, to={to_date}", file=sys.stderr)

    storage = Storage(args.db, args.jsonl)
    try:
        articles = search_news(args.genre, from_date, to_date, verbose=args.verbose)
        new_count = 0
        for article in articles:
            if storage.insert(article):
                new_count += 1
                if args.verbose:
                    print(f"  + {article.title}", file=sys.stderr)
            elif args.verbose:
                print(f"  = {article.title} (duplicate)", file=sys.stderr)
        print(f"Done: {new_count} new articles collected ({len(articles)} total found)", file=sys.stderr)
    finally:
        storage.close()


def search_news(genre: str, from_date: str, to_date: str, *, verbose: bool = False) -> list[Article]:
    """Search for news articles using Gemini with Google Search Grounding."""
    # TODO: implement in Phase 1 development
    raise NotImplementedError("search_news is not yet implemented")


def _article_id(url: str) -> str:
    """Generate a deterministic article ID from a URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]
