"""Phase 2: Tag and summarize collected articles via Gemini Flash."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from news_collector.storage import Storage


def run_process(args: argparse.Namespace) -> None:
    """Entry point for the process subcommand."""
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

        for article in articles:
            tags, summary = generate_tags_and_summary(article.title, article.summary_raw)
            storage.update_processed(
                article.id,
                tags=tags,
                summary=summary,
                processed_at=datetime.now().isoformat(),
            )
            if args.verbose:
                print(f"  ✓ {article.title} → {tags}", file=sys.stderr)

        print(f"Done: {len(articles)} articles processed.", file=sys.stderr)
    finally:
        storage.close()


def generate_tags_and_summary(title: str, raw_summary: str) -> tuple[list[str], str]:
    """Generate tags and summary using Gemini Flash."""
    # TODO: implement in Phase 2 development
    raise NotImplementedError("generate_tags_and_summary is not yet implemented")
