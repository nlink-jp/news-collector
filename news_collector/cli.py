"""CLI entry point for news-collector."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="News collection agent — collect, structure, tag, and summarize news articles",
    )
    subparsers = parser.add_subparsers(dest="command")

    # collect
    collect_parser = subparsers.add_parser("collect", help="Collect news articles for a genre and date range")
    collect_parser.add_argument("--genre", "-g", default="cybersecurity", help="News genre to collect (default: cybersecurity)")
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
    process_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed progress")

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


if __name__ == "__main__":
    main()
