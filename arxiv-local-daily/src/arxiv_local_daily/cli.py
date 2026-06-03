import argparse
import json
from pathlib import Path

from arxiv_local_daily.config import default_settings
from arxiv_local_daily.crawler.live import run_live_daily_crawl
from arxiv_local_daily.db import connect, initialize_schema
from arxiv_local_daily.models import PaperDiscussionInput, SummaryTemplateInput
from arxiv_local_daily.repositories import DiscussionRepository, SearchRepository, TemplateRepository
from arxiv_local_daily.services import (
    enrich_metadata_for_date,
    generate_summaries_for_date,
    get_crawl_completeness_for_date,
    retry_incomplete_crawl_categories_for_date,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="arxiv-local-daily")
    subparsers = parser.add_subparsers(dest="command", required=True)
    crawl = subparsers.add_parser("crawl")
    crawl.add_argument("--date", required=True)
    crawl.add_argument("--category", action="append")
    crawl.add_argument("--db", default=str(default_settings().database_path))
    crawl_audit = subparsers.add_parser("crawl-audit")
    crawl_audit.add_argument("--date", required=True)
    crawl_audit.add_argument("--expected-category", action="append")
    crawl_audit.add_argument("--db", default=str(default_settings().database_path))
    crawl_retry = subparsers.add_parser("crawl-retry-failed")
    crawl_retry.add_argument("--date", required=True)
    crawl_retry.add_argument("--expected-category", action="append")
    crawl_retry.add_argument("--db", default=str(default_settings().database_path))
    search = subparsers.add_parser("search")
    search.add_argument("--query")
    search.add_argument("--date")
    search.add_argument("--category")
    search.add_argument("--event-type")
    search.add_argument("--metadata-status")
    search.add_argument("--summary-status")
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--db", default=str(default_settings().database_path))
    discuss = subparsers.add_parser("discuss")
    discuss_subparsers = discuss.add_subparsers(dest="discuss_command", required=True)
    discuss_add = discuss_subparsers.add_parser("add")
    discuss_add.add_argument("--arxiv-id", required=True)
    discuss_add.add_argument("--role", required=True)
    discuss_add.add_argument("--content", required=True)
    discuss_add.add_argument("--tag", action="append")
    discuss_add.add_argument("--db", default=str(default_settings().database_path))
    discuss_list = discuss_subparsers.add_parser("list")
    discuss_list.add_argument("--arxiv-id", required=True)
    discuss_list.add_argument("--db", default=str(default_settings().database_path))
    metadata = subparsers.add_parser("metadata")
    metadata.add_argument("--date", required=True)
    metadata.add_argument("--limit", type=int, default=100)
    metadata.add_argument("--db", default=str(default_settings().database_path))
    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--date", required=True)
    summarize.add_argument("--template-id", type=int)
    summarize.add_argument("--template-name")
    summarize.add_argument("--model", default="local")
    summarize.add_argument("--limit", type=int, default=20)
    summarize.add_argument("--force", action="store_true")
    summarize.add_argument("--db", default=str(default_settings().database_path))
    template = subparsers.add_parser("template")
    template_subparsers = template.add_subparsers(dest="template_command", required=True)
    template_import = template_subparsers.add_parser("import")
    template_import.add_argument("--file", required=True)
    template_import.add_argument("--db", default=str(default_settings().database_path))
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
    if args.command == "crawl-audit":
        connection = connect(args.db)
        initialize_schema(connection)
        try:
            result = get_crawl_completeness_for_date(
                connection,
                date=args.date,
                expected_categories=args.expected_category,
            )
        finally:
            connection.close()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "crawl-retry-failed":
        connection = connect(args.db)
        initialize_schema(connection)
        try:
            result = retry_incomplete_crawl_categories_for_date(
                connection,
                date=args.date,
                expected_categories=args.expected_category,
            )
        finally:
            connection.close()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "search":
        connection = connect(args.db)
        initialize_schema(connection)
        try:
            papers = SearchRepository(connection).search_papers(
                query=args.query,
                date=args.date,
                category=args.category,
                event_type=args.event_type,
                metadata_status=args.metadata_status,
                summary_status=args.summary_status,
                limit=args.limit,
            )
        finally:
            connection.close()
        print(json.dumps({"count": len(papers), "papers": papers}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "discuss" and args.discuss_command == "add":
        connection = connect(args.db)
        initialize_schema(connection)
        try:
            message_id = DiscussionRepository(connection).add_message(
                args.arxiv_id,
                PaperDiscussionInput(
                    role=args.role,
                    content=args.content,
                    tags=args.tag or [],
                ),
            )
            connection.commit()
        finally:
            connection.close()
        print(json.dumps({"message_id": message_id}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "discuss" and args.discuss_command == "list":
        connection = connect(args.db)
        initialize_schema(connection)
        try:
            messages = DiscussionRepository(connection).list_messages(args.arxiv_id)
        finally:
            connection.close()
        print(json.dumps({"discussions": messages}, ensure_ascii=False, sort_keys=True))
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
    if args.command == "summarize":
        connection = connect(args.db)
        initialize_schema(connection)
        try:
            result = generate_summaries_for_date(
                connection,
                date=args.date,
                template_id=args.template_id,
                template_name=args.template_name,
                model=args.model,
                limit=args.limit,
                force=args.force,
            )
        finally:
            connection.close()
        print(result)
        return 0
    if args.command == "template" and args.template_command == "import":
        connection = connect(args.db)
        initialize_schema(connection)
        try:
            payload = json.loads(Path(args.file).read_text())
            template = SummaryTemplateInput.model_validate(payload)
            repo = TemplateRepository(connection)
            template_id = repo.create_template(template)
            connection.commit()
            row = repo.get_template(template_id=template_id)
        finally:
            connection.close()
        print({"template_id": template_id, "version": row["version"]})
        return 0
    raise ValueError(f"unknown command: {args.command}")
