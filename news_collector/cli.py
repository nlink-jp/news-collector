"""CLI entry point for news-collector."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="News collection agent — collect, structure, tag, and summarize news articles",
    )
    subparsers = parser.add_subparsers(dest="command")

    # collect
    collect_parser = subparsers.add_parser(
        "collect",
        help="Collect news articles for topics and date range",
        epilog="""\
examples:
  news-collector collect --topics topics.toml
  news-collector collect --genre cybersecurity --keywords "ransomware,zero-day"
  news-collector collect --genre ai --from 2026-03-01 --to 2026-03-31""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source_group = collect_parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--topics", "-t", metavar="FILE",
        help="TOML file defining topics and keywords (recommended for batch)",
    )
    source_group.add_argument(
        "--genre", "-g", default=None,
        help="Single genre to collect (default: cybersecurity if no --topics)",
    )
    collect_parser.add_argument(
        "--keywords", "-k", default=None,
        help="Comma-separated keywords to focus the search (used with --genre)",
    )
    collect_parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD, default: yesterday)")
    collect_parser.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD, default: yesterday)")
    collect_parser.add_argument("--db", default="news.db", help="SQLite database path (default: news.db)")
    collect_parser.add_argument("--jsonl", help="Also append to JSONL file")
    collect_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed progress")

    # process
    process_parser = subparsers.add_parser("process", help="Tag and summarize unprocessed articles")
    process_parser.add_argument("--from", dest="from_date", help="Start date filter (YYYY-MM-DD)")
    process_parser.add_argument("--to", dest="to_date", help="End date filter (YYYY-MM-DD)")
    process_parser.add_argument("--db", default="news.db", help="SQLite database path (default: news.db)")
    process_parser.add_argument("--force", action="store_true", help="Re-process already processed articles")
    process_parser.add_argument(
        "--topics", "-t", metavar="FILE",
        help="TOML file with languages config (reads 'languages' field)",
    )
    process_parser.add_argument(
        "--languages", "-l", default=None,
        help="Comma-separated target languages for translation (e.g. ja,ko)",
    )
    process_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed progress")

    # notify
    notify_parser = subparsers.add_parser(
        "notify",
        help="Output articles as Slack Block Kit JSON (pipe to swrite)",
        epilog="example: news-collector notify --lang ja | swrite post --format blocks -c '#news'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    notify_parser.add_argument("--db", default="news.db", help="SQLite database path")
    notify_parser.add_argument("--from", dest="from_date", help="Start date filter")
    notify_parser.add_argument("--to", dest="to_date", help="End date filter")
    notify_parser.add_argument("--genre", "-g", default="", help="Filter by genre")
    notify_parser.add_argument("--lang", "-l", default="", help="Use translations for this language")
    notify_parser.add_argument("--title", default="News Digest", help="Digest header title")
    notify_parser.add_argument("--limit", type=int, default=0, help="Max articles (0 = all)")

    # curate
    curate_parser = subparsers.add_parser(
        "curate",
        help="Generate analyst commentary and output as Slack Block Kit JSON",
        epilog="example: news-collector curate --lang ja | swrite post --format blocks -c '#news'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    curate_parser.add_argument("--db", default="news.db", help="SQLite database path")
    curate_parser.add_argument("--from", dest="from_date", help="Start date filter")
    curate_parser.add_argument("--to", dest="to_date", help="End date filter")
    curate_parser.add_argument("--genre", "-g", default="", help="Filter by genre")
    curate_parser.add_argument("--lang", "-l", default="", help="Language for translations and commentary")
    curate_parser.add_argument("--title", default="Curated News", help="Digest header title")
    curate_parser.add_argument("--limit", type=int, default=0, help="Max articles (0 = all)")
    curate_parser.add_argument("--verbose", "-v", action="store_true", help="Show progress on stderr")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start the web UI")
    serve_parser.add_argument("--db", default="news.db", help="SQLite database path (default: news.db)")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    serve_parser.add_argument("--port", "-p", type=int, default=8080, help="Port (default: 8080)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "collect":
        from news_collector.collector import run_collect
        run_collect(args)
    elif args.command == "process":
        from news_collector.processor import run_process
        run_process(args)
    elif args.command == "notify":
        _run_notify(args)
    elif args.command == "curate":
        _run_curate(args)
    elif args.command == "serve":
        from news_collector.web import create_app
        import uvicorn
        app = create_app(args.db)
        print(f"Starting web UI at http://{args.host}:{args.port}", file=sys.stderr)
        print(f"Database: {args.db}", file=sys.stderr)
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def _load_articles_for_output(args) -> list:
    """Load and filter articles for notify/curate commands."""
    from news_collector.storage import Storage

    storage = Storage(args.db)
    try:
        articles = storage.get_all(
            from_date=args.from_date or None,
            to_date=args.to_date or None,
        )
        if args.genre:
            articles = [a for a in articles if a.genre == args.genre]
        # Only include processed articles
        articles = [a for a in articles if a.processed_at]

        if args.lang:
            for a in articles:
                a.translations = storage.get_translations(a.id)

        if args.limit and args.limit > 0:
            articles = articles[:args.limit]

        return articles
    finally:
        storage.close()


def _run_notify(args) -> None:
    import json
    from news_collector.slack import build_single_article_blocks

    articles = _load_articles_for_output(args)
    if not articles:
        print("No articles to notify.", file=sys.stderr)
        sys.exit(0)

    for article in articles:
        blocks = build_single_article_blocks(article, lang=args.lang)
        print(json.dumps(blocks, ensure_ascii=False))


def _run_curate(args) -> None:
    import json
    import os
    from google import genai
    from news_collector.processor import generate_commentary
    from news_collector.slack import build_single_article_blocks

    articles = _load_articles_for_output(args)
    if not articles:
        print("No articles to curate.", file=sys.stderr)
        sys.exit(0)

    client = genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    print(f"Generating commentary for {len(articles)} articles...", file=sys.stderr)
    for i, article in enumerate(articles):
        source_summary = article.summary or article.summary_raw
        commentary = generate_commentary(
            client, article.title, source_summary, article.tags, lang=args.lang,
        )
        if getattr(args, "verbose", False):
            print(f"  ✓ [{i + 1}/{len(articles)}] {article.title}", file=sys.stderr)

        blocks = build_single_article_blocks(
            article, lang=args.lang, commentary=commentary,
        )
        print(json.dumps(blocks, ensure_ascii=False))

    print(f"Done: {len(articles)} articles.", file=sys.stderr)


if __name__ == "__main__":
    main()
