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
    elif args.command == "serve":
        from news_collector.web import create_app
        import uvicorn
        app = create_app(args.db)
        print(f"Starting web UI at http://{args.host}:{args.port}", file=sys.stderr)
        print(f"Database: {args.db}", file=sys.stderr)
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
