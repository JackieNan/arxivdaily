import sqlite3

from arxiv_local_daily.crawler.parser import parse_daily_listing
from arxiv_local_daily.db import transaction
from arxiv_local_daily.models import CrawlSourceInput
from arxiv_local_daily.repositories import CrawlRepository, PaperRepository


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
