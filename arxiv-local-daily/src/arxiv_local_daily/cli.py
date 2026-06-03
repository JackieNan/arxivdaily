import argparse

from arxiv_local_daily.config import default_settings
from arxiv_local_daily.crawler.live import run_live_daily_crawl
from arxiv_local_daily.db import connect, initialize_schema
from arxiv_local_daily.services import enrich_metadata_for_date


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="arxiv-local-daily")
    subparsers = parser.add_subparsers(dest="command", required=True)
    crawl = subparsers.add_parser("crawl")
    crawl.add_argument("--date", required=True)
    crawl.add_argument("--category", action="append")
    crawl.add_argument("--db", default=str(default_settings().database_path))
    metadata = subparsers.add_parser("metadata")
    metadata.add_argument("--date", required=True)
    metadata.add_argument("--limit", type=int, default=100)
    metadata.add_argument("--db", default=str(default_settings().database_path))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "crawl":
        connection = connect(args.db)
        initialize_schema(connection)
        try:
            run_id = run_live_daily_crawl(connection, date=args.date, categories=args.category)
        finally:
            connection.close()
        print(f"crawl_run_id={run_id}")
        return 0
    if args.command == "metadata":
        connection = connect(args.db)
        initialize_schema(connection)
        try:
            result = enrich_metadata_for_date(connection, date=args.date, limit=args.limit)
        finally:
            connection.close()
        print(result)
        return 0
    raise ValueError(f"unknown command: {args.command}")
