import sqlite3
from typing import Any

from arxiv_local_daily.crawler.audit import build_crawl_completeness_report
from arxiv_local_daily.crawler.metadata import ArxivMetadataClient
from arxiv_local_daily.crawler.parser import parse_daily_listing
from arxiv_local_daily.db import transaction
from arxiv_local_daily.models import CrawlSourceInput
from arxiv_local_daily.repositories import CrawlRepository, PaperRepository, SummaryRepository, TemplateRepository
from arxiv_local_daily.summary import (
    LLMClient,
    OpenAICompatibleChatClient,
    build_summary_messages,
    enabled_template_fields,
    parse_summary_response,
)


def ingest_daily_listing_html(
    connection: sqlite3.Connection,
    *,
    date: str,
    listing_category: str,
    source_url: str,
    html: str,
) -> int:
    events = parse_daily_listing(
        html,
        listing_category=listing_category,
        source_url=source_url,
    )
    counts: dict[str, int] = {}
    for event in events:
        counts[event.event_type] = counts.get(event.event_type, 0) + 1

    with transaction(connection):
        crawl_repo = CrawlRepository(connection)
        paper_repo = PaperRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode="single-source", status="running")
        for event in events:
            paper_repo.upsert_daily_event(date=date, event=event)
        crawl_repo.record_source(
            run_id=run_id,
            category=listing_category,
            event_section="all",
            url=source_url,
            status="complete",
            http_status=200,
            parsed_count=len(events),
        )
        crawl_repo.finish_run(run_id, status="complete", summary_counts=counts)
        return run_id


def ingest_daily_crawl_sources(
    connection: sqlite3.Connection,
    *,
    date: str,
    mode: str,
    sources: list[CrawlSourceInput],
) -> int:
    summary_counts: dict[str, int] = {}
    failed_count = 0
    with transaction(connection):
        crawl_repo = CrawlRepository(connection)
        paper_repo = PaperRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode=mode, status="running")
        for source in sources:
            parsed_count = 0
            if source.status == "complete" and source.html is not None:
                events = parse_daily_listing(
                    source.html,
                    listing_category=source.category,
                    source_url=source.url,
                )
                parsed_count = len(events)
                for event in events:
                    summary_counts[event.event_type] = summary_counts.get(event.event_type, 0) + 1
                    paper_repo.upsert_daily_event(date=date, event=event)
            else:
                failed_count += 1
            crawl_repo.record_source(
                run_id=run_id,
                category=source.category,
                event_section=source.event_section,
                url=source.url,
                status=source.status,
                http_status=source.http_status,
                parsed_count=parsed_count,
                error=source.error,
                retry_count=source.retry_count,
            )
        final_status = "complete" if failed_count == 0 else "partial"
        crawl_repo.finish_run(run_id, status=final_status, summary_counts=summary_counts)
        return run_id


def enrich_metadata_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    metadata_client: ArxivMetadataClient | None = None,
    limit: int = 100,
) -> dict[str, int]:
    client = metadata_client or ArxivMetadataClient()
    repo = PaperRepository(connection)
    ids = repo.list_metadata_pending_ids_for_date(date, limit=limit)
    if not ids:
        return {"requested": 0, "updated": 0, "missing": 0, "failed": 0}
    try:
        papers = client.fetch_by_ids(ids)
    except Exception:
        with transaction(connection):
            for arxiv_id in ids:
                repo.mark_metadata_status(arxiv_id, "failed")
        return {"requested": len(ids), "updated": 0, "missing": 0, "failed": len(ids)}

    returned_by_id = {paper.arxiv_id: paper for paper in papers}
    with transaction(connection):
        for paper in papers:
            repo.upsert_metadata(paper)
        missing_ids = sorted(set(ids) - set(returned_by_id))
        for arxiv_id in missing_ids:
            repo.mark_metadata_status(arxiv_id, "failed")
    return {
        "requested": len(ids),
        "updated": len(papers),
        "missing": len(missing_ids),
        "failed": 0,
    }


def generate_summaries_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    template_id: int | None = None,
    template_name: str | None = None,
    model: str = "local",
    limit: int = 20,
    force: bool = False,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    template_repo = TemplateRepository(connection)
    template = template_repo.get_template(template_id=template_id, name=template_name)
    if template is None:
        raise ValueError("summary template not found")

    summary_repo = SummaryRepository(connection)
    template_id_value = int(template["id"])
    template_version = int(template["version"])
    input_scope = template["input_scope"]
    skipped = 0
    if not force:
        skipped = summary_repo.count_existing_complete_summaries_for_date(
            date=date,
            template_id=template_id_value,
            template_version=template_version,
            model=model,
            input_scope=input_scope,
        )
    candidate_ids = summary_repo.list_summary_candidate_ids_for_date(
        date=date,
        template_id=template_id_value,
        template_version=template_version,
        model=model,
        input_scope=input_scope,
        limit=limit,
        force=force,
    )
    client = llm_client or OpenAICompatibleChatClient.from_env()
    expected_keys = [field["key"] for field in enabled_template_fields(template)]
    completed = 0
    failed = 0

    for arxiv_id in candidate_ids:
        paper = summary_repo.get_paper_for_summary(arxiv_id)
        if paper is None:
            continue
        try:
            response_text = client.complete(
                model=model,
                messages=build_summary_messages(paper=paper, template=template),
            )
            content = parse_summary_response(response_text, expected_keys=expected_keys)
            status = "complete"
            completed += 1
        except Exception as exc:
            content = {"error": str(exc)}
            status = "failed"
            failed += 1

        with transaction(connection):
            summary_repo.upsert_summary(
                arxiv_id=arxiv_id,
                template_id=template_id_value,
                template_version=template_version,
                model=model,
                language=template["language"],
                input_scope=input_scope,
                content=content,
                status=status,
            )

    return {
        "requested": len(candidate_ids),
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "template_id": template_id_value,
        "template_version": template_version,
    }


def get_crawl_completeness_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    expected_categories: list[str] | None = None,
) -> dict[str, Any]:
    return build_crawl_completeness_report(
        connection,
        date=date,
        expected_categories=expected_categories,
    )


def retry_incomplete_crawl_categories_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    expected_categories: list[str] | None = None,
    crawl_runner: Any | None = None,
) -> dict[str, Any]:
    report = get_crawl_completeness_for_date(
        connection,
        date=date,
        expected_categories=expected_categories,
    )
    categories = report["retry_categories"]
    if not categories:
        return {"run_id": None, "retried": 0, "categories": []}
    if crawl_runner is None:
        from arxiv_local_daily.crawler.live import run_live_daily_crawl

        crawl_runner = run_live_daily_crawl
    run_id = crawl_runner(connection, date=date, categories=categories)
    return {"run_id": run_id, "retried": len(categories), "categories": categories}
