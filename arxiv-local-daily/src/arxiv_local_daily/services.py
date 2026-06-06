import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from arxiv_local_daily.crawler.audit import build_crawl_completeness_report
from arxiv_local_daily.crawler.metadata import ArxivMetadataClient
from arxiv_local_daily.crawler.oai import OaiPmhMetadataClient
from arxiv_local_daily.crawler.parser import parse_daily_listing, parse_daily_listing_count
from arxiv_local_daily.db import transaction
from arxiv_local_daily.models import CrawlSourceInput, PaperMetadata
from arxiv_local_daily.models import ParsedDailyEvent
from arxiv_local_daily.repositories import (
    CrawlRepository,
    DailyAutomationRepository,
    MetadataEnrichmentRepository,
    MetadataSyncRepository,
    PaperRepository,
    PreflightRepository,
    ScoreRepository,
    SummaryRepository,
    TemplateRepository,
)
from arxiv_local_daily.summary import (
    LLMClient,
    OpenAICompatibleChatClient,
    build_ai_triage_messages,
    build_score_messages,
    build_summary_messages,
    enabled_template_fields,
    llm_api_configured,
    parse_ai_triage_response,
    parse_score_response,
    parse_summary_response,
)

METADATA_RATE_LIMIT_BACKOFF_SECONDS = 10 * 60
DAILY_LISTING_EVENT_TYPES = ("new", "cross-list", "replacement")
DAILY_LISTING_CRAWL_MODES = ("single-source", "all-categories", "retry-incomplete")


def _metadata_result(
    *,
    requested: int,
    updated: int,
    missing: int,
    failed: int,
    retryable: int = 0,
    error: str | None = None,
    next_run_at: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "requested": requested,
        "updated": updated,
        "missing": missing,
        "failed": failed,
        "retryable": retryable,
    }
    if error is not None:
        result["error"] = error
    if next_run_at is not None:
        result["next_run_at"] = next_run_at
    return result


def _utc_after(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")


def _is_retryable_metadata_error(error: Exception) -> bool:
    message = str(error).lower()
    retryable_markers = [
        "http 429",
        "http 500",
        "http 502",
        "http 503",
        "http 504",
        "rate limit",
        "read operation timed out",
        "timeout",
        "timed out",
        "too many requests",
    ]
    return any(marker in message for marker in retryable_markers)


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
    expected_count = parse_daily_listing_count(html)
    missing_count = max((expected_count or len(events)) - len(events), 0)
    source_status = "incomplete" if expected_count is not None and missing_count > 0 else "complete"
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
            status=source_status,
            http_status=200,
            parsed_count=len(events),
            expected_count=expected_count,
            missing_count=missing_count,
        )
        crawl_repo.finish_run(run_id, status=source_status if source_status == "complete" else "partial", summary_counts=counts)
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
            expected_count = source.expected_count
            missing_count = source.missing_count
            source_status = source.status
            if source.status == "complete" and source.html is not None:
                events = parse_daily_listing(
                    source.html,
                    listing_category=source.category,
                    source_url=source.url,
                )
                parsed_count = len(events)
                if expected_count is None:
                    expected_count = parse_daily_listing_count(source.html)
                missing_count = max((expected_count or parsed_count) - parsed_count, 0)
                if expected_count is not None and missing_count > 0:
                    source_status = "incomplete"
                for event in events:
                    summary_counts[event.event_type] = summary_counts.get(event.event_type, 0) + 1
                    paper_repo.upsert_daily_event(date=date, event=event)
            else:
                source_status = source.status
            if source_status != "complete":
                failed_count += 1
            crawl_repo.record_source(
                run_id=run_id,
                category=source.category,
                event_section=source.event_section,
                url=source.url,
                status=source_status,
                http_status=source.http_status,
                parsed_count=parsed_count,
                expected_count=expected_count,
                missing_count=missing_count,
                error=source.error,
                retry_count=source.retry_count,
            )
        final_status = "complete" if failed_count == 0 else "partial"
        crawl_repo.finish_run(run_id, status=final_status, summary_counts=summary_counts)
        return run_id


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def repair_contaminated_daily_listing_dates(
    connection: sqlite3.Connection,
    *,
    dates: list[str],
) -> dict[str, Any]:
    cleaned_dates = _ordered_unique([date for date in dates if date])
    event_placeholders = ", ".join("?" for _ in DAILY_LISTING_EVENT_TYPES)
    mode_placeholders = ", ".join("?" for _ in DAILY_LISTING_CRAWL_MODES)
    total_daily_events_deleted = 0
    total_daily_listing_papers_removed = 0
    total_crawl_runs_deleted = 0
    total_historical_events_preserved = 0
    per_date: dict[str, dict[str, int]] = {}

    with transaction(connection):
        for date in cleaned_dates:
            daily_event_params = (date, *DAILY_LISTING_EVENT_TYPES)
            daily_event_count = int(
                connection.execute(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM daily_events
                    WHERE date = ?
                      AND event_type IN ({event_placeholders})
                    """,
                    daily_event_params,
                ).fetchone()["count"]
            )
            daily_listing_papers = int(
                connection.execute(
                    f"""
                    SELECT COUNT(DISTINCT arxiv_id) AS count
                    FROM daily_events
                    WHERE date = ?
                      AND event_type IN ({event_placeholders})
                    """,
                    daily_event_params,
                ).fetchone()["count"]
            )
            historical_events = int(
                connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM daily_events
                    WHERE date = ?
                      AND event_type = 'historical'
                    """,
                    (date,),
                ).fetchone()["count"]
            )
            crawl_run_params = (date, *DAILY_LISTING_CRAWL_MODES)
            crawl_run_count = int(
                connection.execute(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM crawl_runs
                    WHERE date = ?
                      AND mode IN ({mode_placeholders})
                    """,
                    crawl_run_params,
                ).fetchone()["count"]
            )

            deleted_events = connection.execute(
                f"""
                DELETE FROM daily_events
                WHERE date = ?
                  AND event_type IN ({event_placeholders})
                """,
                daily_event_params,
            ).rowcount
            deleted_runs = connection.execute(
                f"""
                DELETE FROM crawl_runs
                WHERE date = ?
                  AND mode IN ({mode_placeholders})
                """,
                crawl_run_params,
            ).rowcount

            deleted_events = max(deleted_events, 0)
            deleted_runs = max(deleted_runs, 0)
            total_daily_events_deleted += deleted_events
            total_daily_listing_papers_removed += daily_listing_papers
            total_crawl_runs_deleted += deleted_runs
            total_historical_events_preserved += historical_events
            per_date[date] = {
                "daily_events_before": daily_event_count,
                "daily_events_deleted": deleted_events,
                "daily_listing_papers_removed": daily_listing_papers,
                "crawl_runs_before": crawl_run_count,
                "crawl_runs_deleted": deleted_runs,
                "historical_events_preserved": historical_events,
            }

    return {
        "dates": cleaned_dates,
        "daily_events_deleted": total_daily_events_deleted,
        "daily_listing_papers_removed": total_daily_listing_papers_removed,
        "crawl_runs_deleted": total_crawl_runs_deleted,
        "historical_events_preserved": total_historical_events_preserved,
        "per_date": per_date,
    }


def enrich_metadata_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    metadata_client: ArxivMetadataClient | None = None,
    limit: int | None = 100,
) -> dict[str, Any]:
    client = metadata_client or ArxivMetadataClient()
    repo = PaperRepository(connection)
    ids = repo.list_metadata_pending_ids_for_date(date, limit=limit)
    if not ids:
        return _metadata_result(requested=0, updated=0, missing=0, failed=0)
    try:
        papers = client.fetch_by_ids(ids)
    except Exception as exc:
        error = str(exc)
        is_retryable = _is_retryable_metadata_error(exc)
        next_run_at = _utc_after(METADATA_RATE_LIMIT_BACKOFF_SECONDS) if is_retryable else None
        status = "retryable" if is_retryable else "failed"
        with transaction(connection):
            for arxiv_id in ids:
                repo.mark_metadata_status(
                    arxiv_id,
                    status,
                    error=error,
                    next_run_at=next_run_at,
                    increment_attempts=True,
                )
        return _metadata_result(
            requested=len(ids),
            updated=0,
            missing=0,
            failed=0 if is_retryable else len(ids),
            retryable=len(ids) if is_retryable else 0,
            error=error,
            next_run_at=next_run_at,
        )

    returned_by_id = {paper.arxiv_id: paper for paper in papers}
    with transaction(connection):
        for paper in papers:
            repo.upsert_metadata(paper)
        missing_ids = sorted(set(ids) - set(returned_by_id))
        for arxiv_id in missing_ids:
            repo.mark_metadata_status(arxiv_id, "failed", error="not returned by arXiv API")
    return _metadata_result(
        requested=len(ids),
        updated=len(papers),
        missing=len(missing_ids),
        failed=0,
    )


def run_oai_metadata_sync(
    connection: sqlite3.Connection,
    *,
    sync_run_id: int,
    from_date: str | None = None,
    until_date: str | None = None,
    set_spec: str | None = None,
    max_pages: int = 1,
    oai_client: OaiPmhMetadataClient | None = None,
) -> dict[str, Any]:
    client = oai_client or OaiPmhMetadataClient()
    sync_repo = MetadataSyncRepository(connection)
    paper_repo = PaperRepository(connection)
    records_seen = 0
    records_upserted = 0
    pages_fetched = 0
    resumption_token: str | None = None

    with transaction(connection):
        sync_repo.mark_running(sync_run_id)

    try:
        while pages_fetched < max_pages:
            page = client.fetch_list_records(
                from_date=from_date,
                until_date=until_date,
                set_spec=set_spec,
                resumption_token=resumption_token,
            )
            pages_fetched += 1
            records_seen += len(page.papers)
            resumption_token = page.resumption_token
            page_upserted = 0
            with transaction(connection):
                for paper in page.papers:
                    paper_repo.upsert_metadata(paper)
                    page_upserted += 1
            records_upserted += page_upserted
            if not resumption_token:
                break
    except Exception as exc:
        error = str(exc)
        result = {
            "sync_run_id": sync_run_id,
            "status": "failed",
            "records_seen": records_seen,
            "records_upserted": records_upserted,
            "pages_fetched": pages_fetched,
            "resumption_token": resumption_token,
            "error": error,
        }
        with transaction(connection):
            sync_repo.finish_run(
                sync_run_id,
                status="failed",
                records_seen=records_seen,
                records_upserted=records_upserted,
                pages_fetched=pages_fetched,
                resumption_token=resumption_token,
                error=error,
            )
        return result

    result = {
        "sync_run_id": sync_run_id,
        "status": "complete",
        "records_seen": records_seen,
        "records_upserted": records_upserted,
        "pages_fetched": pages_fetched,
        "resumption_token": resumption_token,
    }
    with transaction(connection):
        sync_repo.finish_run(
            sync_run_id,
            status="complete",
            records_seen=records_seen,
            records_upserted=records_upserted,
            pages_fetched=pages_fetched,
            resumption_token=resumption_token,
        )
    return result


def _matches_categories(metadata: PaperMetadata, categories: list[str] | None) -> bool:
    if not categories:
        return True
    paper_categories = set(metadata.categories)
    if metadata.primary_category:
        paper_categories.add(metadata.primary_category)
    return bool(paper_categories.intersection(categories))


def _historical_listing_category(metadata: PaperMetadata, categories: list[str] | None) -> str:
    if categories:
        for category in categories:
            if category == metadata.primary_category or category in metadata.categories:
                return category
    return metadata.primary_category or (metadata.categories[0] if metadata.categories else "historical")


def run_historical_metadata_crawl(
    connection: sqlite3.Connection,
    *,
    date: str,
    categories: list[str] | None = None,
    max_pages: int = 100,
    oai_client: OaiPmhMetadataClient | None = None,
) -> dict[str, Any]:
    client = oai_client or OaiPmhMetadataClient()
    crawl_repo = CrawlRepository(connection)
    paper_repo = PaperRepository(connection)
    with transaction(connection):
        run_id = crawl_repo.create_run(date=date, mode="historical-oai", status="running")

    records_seen = 0
    papers_upserted = 0
    pages_fetched = 0
    complete_list_size: int | None = None
    resumption_token: str | None = None
    source_url = f"oai-pmh:{date}"

    try:
        while pages_fetched < max_pages:
            page = client.fetch_list_records(
                from_date=date,
                until_date=date,
                resumption_token=resumption_token,
            )
            pages_fetched += 1
            records_seen += len(page.papers)
            if page.complete_list_size is not None:
                complete_list_size = page.complete_list_size
            with transaction(connection):
                for paper in page.papers:
                    if not _matches_categories(paper, categories):
                        continue
                    paper_repo.upsert_metadata(paper)
                    paper_repo.upsert_daily_event(
                        date=date,
                        event=ParsedDailyEvent(
                            arxiv_id=paper.arxiv_id,
                            event_type="historical",
                            listing_category=_historical_listing_category(paper, categories),
                            primary_category=paper.primary_category,
                            title=paper.title,
                            source_url=source_url,
                        ),
                    )
                    papers_upserted += 1
            resumption_token = page.resumption_token
            if not resumption_token:
                break
    except Exception as exc:
        error = str(exc)
        with transaction(connection):
            crawl_repo.record_source(
                run_id=run_id,
                category="historical",
                event_section="historical",
                url=source_url,
                status="failed",
                http_status=None,
                parsed_count=papers_upserted,
                expected_count=complete_list_size,
                error=error,
            )
            crawl_repo.finish_run(run_id, status="partial", summary_counts={"historical": papers_upserted})
        return {
            "run_id": run_id,
            "status": "partial",
            "records_seen": records_seen,
            "papers_upserted": papers_upserted,
            "pages_fetched": pages_fetched,
            "resumption_token": resumption_token,
            "error": error,
        }

    status = "partial" if resumption_token else "complete"
    error = f"historical OAI crawl reached max_pages={max_pages}" if resumption_token else None
    with transaction(connection):
        crawl_repo.record_source(
            run_id=run_id,
            category="historical",
            event_section="historical",
            url=source_url,
            status=status,
            http_status=200,
            parsed_count=papers_upserted,
            expected_count=complete_list_size,
            error=error,
        )
        crawl_repo.finish_run(run_id, status=status, summary_counts={"historical": papers_upserted})
    return {
        "run_id": run_id,
        "status": status,
        "records_seen": records_seen,
        "papers_upserted": papers_upserted,
        "pages_fetched": pages_fetched,
        "resumption_token": resumption_token,
        "error": error,
    }


def _metadata_completeness_score(metadata: PaperMetadata) -> int:
    score = 0
    for value in [
        metadata.title,
        metadata.abstract,
        metadata.primary_category,
        metadata.abs_url,
        metadata.pdf_url,
        metadata.published_at,
        metadata.updated_at,
    ]:
        if value:
            score += 1
    score += min(len(metadata.authors), 3)
    score += min(len(metadata.categories), 3)
    return score


def _choose_metadata(
    arxiv_id: str,
    *,
    id_api_by_id: dict[str, PaperMetadata],
    oai_by_id: dict[str, PaperMetadata],
) -> PaperMetadata | None:
    candidates = [metadata for metadata in [id_api_by_id.get(arxiv_id), oai_by_id.get(arxiv_id)] if metadata is not None]
    if not candidates:
        return None
    return sorted(candidates, key=_metadata_completeness_score, reverse=True)[0]


def _metadata_mismatch(id_metadata: PaperMetadata, oai_metadata: PaperMetadata) -> dict[str, Any] | None:
    mismatches: dict[str, Any] = {}
    for field in ["title", "abstract", "primary_category"]:
        left = getattr(id_metadata, field)
        right = getattr(oai_metadata, field)
        if left and right and left != right:
            mismatches[field] = {"id_api": left, "oai": right}
    if id_metadata.categories and oai_metadata.categories and id_metadata.categories != oai_metadata.categories:
        mismatches["categories"] = {"id_api": id_metadata.categories, "oai": oai_metadata.categories}
    return mismatches or None


def enrich_metadata_for_date_unified(
    connection: sqlite3.Connection,
    *,
    date: str,
    metadata_client: ArxivMetadataClient | None = None,
    oai_client: OaiPmhMetadataClient | None = None,
    limit: int | None = None,
    oai_max_pages: int = 1,
    only_incomplete: bool = False,
) -> dict[str, Any]:
    paper_repo = PaperRepository(connection)
    enrich_repo = MetadataEnrichmentRepository(connection)
    id_client = metadata_client or ArxivMetadataClient()
    oai = oai_client or OaiPmhMetadataClient()
    crawl_ids = (
        paper_repo.list_metadata_pending_ids_for_date(date, limit=limit)
        if only_incomplete
        else paper_repo.list_daily_ids_for_date(date, limit=limit)
    )
    with transaction(connection):
        run_id = enrich_repo.create_run(date=date)

    id_api_papers: list[PaperMetadata] = []
    oai_papers: list[PaperMetadata] = []
    errors: list[str] = []
    retryable_error = False
    try:
        if crawl_ids:
            id_api_papers = id_client.fetch_by_ids(crawl_ids)
    except Exception as exc:
        errors.append(f"id_api: {exc}")
        retryable_error = retryable_error or _is_retryable_metadata_error(exc)

    try:
        resumption_token: str | None = None
        pages_fetched = 0
        while pages_fetched < oai_max_pages:
            page = oai.fetch_list_records(
                from_date=date,
                until_date=date,
                resumption_token=resumption_token,
            )
            pages_fetched += 1
            oai_papers.extend(page.papers)
            resumption_token = page.resumption_token
            if not resumption_token:
                break
    except Exception as exc:
        errors.append(f"oai: {exc}")
        retryable_error = retryable_error or _is_retryable_metadata_error(exc)

    id_api_by_id = {paper.arxiv_id: paper for paper in id_api_papers}
    oai_by_id = {paper.arxiv_id: paper for paper in oai_papers}
    crawl_id_set = set(crawl_ids)
    id_api_id_set = set(id_api_by_id)
    oai_id_set = set(oai_by_id)
    merged_count = 0
    missing_after_merge: list[str] = []
    retryable_after_merge: list[str] = []
    oai_missing = sorted(crawl_id_set - oai_id_set)
    oai_extra = sorted(oai_id_set - crawl_id_set)
    mismatch_count = 0
    next_run_at = _utc_after(METADATA_RATE_LIMIT_BACKOFF_SECONDS) if retryable_error else None
    error = "; ".join(errors) if errors else None

    with transaction(connection):
        for paper in id_api_papers:
            enrich_repo.record_source(run_id=run_id, source="id_api", metadata=paper)
        for paper in oai_papers:
            enrich_repo.record_source(run_id=run_id, source="oai", metadata=paper)

        for arxiv_id in crawl_ids:
            chosen = _choose_metadata(arxiv_id, id_api_by_id=id_api_by_id, oai_by_id=oai_by_id)
            if chosen is None:
                if retryable_error:
                    retryable_after_merge.append(arxiv_id)
                    paper_repo.mark_metadata_status(
                        arxiv_id,
                        "retryable",
                        error=error or "metadata sources temporarily unavailable",
                        next_run_at=next_run_at,
                        increment_attempts=True,
                    )
                    report_type = "retryable_after_merge"
                    details = {"sources_checked": ["id_api", "oai"], "error": error}
                else:
                    missing_after_merge.append(arxiv_id)
                    paper_repo.mark_metadata_status(
                        arxiv_id,
                        "failed",
                        error="not returned by metadata sources",
                        next_run_at=_utc_after(METADATA_RATE_LIMIT_BACKOFF_SECONDS),
                        increment_attempts=True,
                    )
                    report_type = "missing_after_merge"
                    details = {"sources_checked": ["id_api", "oai"]}
                enrich_repo.record_report(
                    run_id=run_id,
                    report_type=report_type,
                    arxiv_id=arxiv_id,
                    details=details,
                )
                continue
            paper_repo.upsert_metadata(chosen)
            merged_count += 1
            if arxiv_id in id_api_by_id and arxiv_id in oai_by_id:
                mismatch = _metadata_mismatch(id_api_by_id[arxiv_id], oai_by_id[arxiv_id])
                if mismatch:
                    mismatch_count += 1
                    enrich_repo.record_report(
                        run_id=run_id,
                        report_type="mismatch",
                        arxiv_id=arxiv_id,
                        details=mismatch,
                    )

        for arxiv_id in oai_missing:
            enrich_repo.record_report(
                run_id=run_id,
                report_type="oai_missing",
                arxiv_id=arxiv_id,
                details={"meaning": "paper was crawled but not returned by OAI in this run"},
            )
        for arxiv_id in oai_extra:
            enrich_repo.record_report(
                run_id=run_id,
                report_type="oai_extra",
                arxiv_id=arxiv_id,
                details={"meaning": "OAI returned a paper outside the crawled daily set"},
            )

        if retryable_after_merge and merged_count == 0:
            status = "retryable"
        elif error and merged_count == 0:
            status = "failed"
        else:
            status = "partial" if error or missing_after_merge or retryable_after_merge else "complete"
        enrich_repo.finish_run(
            run_id,
            status=status,
            crawl_count=len(crawl_ids),
            id_api_count=len(id_api_id_set),
            oai_count=len(oai_id_set),
            merged_count=merged_count,
            missing_after_merge_count=len(missing_after_merge),
            oai_missing_count=len(oai_missing),
            oai_extra_count=len(oai_extra),
            mismatch_count=mismatch_count,
            error=error,
        )

    return {
        "run_id": run_id,
        "status": status,
        "crawl_count": len(crawl_ids),
        "id_api_count": len(id_api_id_set),
        "oai_count": len(oai_id_set),
        "merged": merged_count,
        "missing_after_merge": len(missing_after_merge),
        "retryable_after_merge": len(retryable_after_merge),
        "oai_missing_count": len(oai_missing),
        "oai_extra_count": len(oai_extra),
        "mismatch_count": mismatch_count,
        "error": error,
        "next_run_at": next_run_at,
    }


def complete_metadata_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    batch_size: int = 100,
    max_rounds: int | None = None,
    oai_max_pages: int = 1,
    metadata_client: ArxivMetadataClient | None = None,
    oai_client: OaiPmhMetadataClient | None = None,
    metadata_runner: Any | None = None,
    sleep_fn: Any | None = None,
) -> dict[str, Any]:
    runner = metadata_runner or enrich_metadata_for_date_unified
    rounds: list[dict[str, Any]] = []
    round_count = 0

    while max_rounds is None or round_count < max_rounds:
        metadata = _daily_metadata_counts(connection, date=date)
        if metadata["total"] == 0:
            return {
                "date": date,
                "status": "no_papers",
                "rounds": round_count,
                "metadata": metadata,
                "runs": rounds,
            }
        if metadata["complete"] == metadata["total"]:
            return {
                "date": date,
                "status": "complete",
                "rounds": round_count,
                "metadata": metadata,
                "runs": rounds,
            }

        ids = PaperRepository(connection).list_metadata_pending_ids_for_date(date, limit=batch_size)
        if not ids:
            return {
                "date": date,
                "status": "waiting",
                "rounds": round_count,
                "metadata": metadata,
                "runs": rounds,
            }

        kwargs: dict[str, Any] = {
            "date": date,
            "limit": batch_size,
            "oai_max_pages": oai_max_pages,
        }
        if runner is enrich_metadata_for_date_unified:
            kwargs["only_incomplete"] = True
        if metadata_client is not None:
            kwargs["metadata_client"] = metadata_client
        if oai_client is not None:
            kwargs["oai_client"] = oai_client

        result = runner(connection, **kwargs)
        rounds.append(result)
        round_count += 1
        connection.commit()

        if result.get("status") == "retryable" and result.get("merged", 0) == 0:
            if sleep_fn is not None:
                sleep_fn(METADATA_RATE_LIMIT_BACKOFF_SECONDS)
            else:
                return {
                    "date": date,
                    "status": "waiting",
                    "rounds": round_count,
                    "metadata": _daily_metadata_counts(connection, date=date),
                    "runs": rounds,
                    "next_run_at": result.get("next_run_at"),
                }

    return {
        "date": date,
        "status": "max_rounds",
        "rounds": round_count,
        "metadata": _daily_metadata_counts(connection, date=date),
        "runs": rounds,
    }


def generate_summaries_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    template_id: int | None = None,
    template_name: str | None = None,
    model: str = "local",
    limit: int | None = None,
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


def score_papers_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    model: str = "local",
    limit: int | None = None,
    force: bool = False,
    rubric_version: str = "reading_priority_v1",
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    score_repo = ScoreRepository(connection)
    candidate_ids = score_repo.list_score_candidate_ids_for_date(
        date=date,
        model=model,
        rubric_version=rubric_version,
        limit=limit,
        force=force,
    )
    client = llm_client or OpenAICompatibleChatClient.from_env()
    completed = 0
    failed = 0
    skipped = 0

    for arxiv_id in candidate_ids:
        paper = score_repo.get_paper_for_score(arxiv_id)
        if paper is None:
            skipped += 1
            continue
        try:
            response_text = client.complete(
                model=model,
                messages=build_score_messages(
                    paper=paper,
                    summary=score_repo.get_latest_summary_content(arxiv_id),
                ),
            )
            content = parse_score_response(response_text)
            status = "complete"
            completed += 1
        except Exception as exc:
            content = {
                "score_total": 0,
                "score_relevance": 0,
                "score_novelty": 0,
                "score_technical_depth": 0,
                "score_evidence": 0,
                "score_actionability": 0,
                "recommended_action": "skip",
                "rationale": str(exc),
            }
            status = "failed"
            failed += 1
        with transaction(connection):
            score_repo.upsert_score(
                arxiv_id=arxiv_id,
                model=model,
                rubric_version=rubric_version,
                content=content,
                status=status,
            )

    return {"requested": len(candidate_ids), "completed": completed, "failed": failed, "skipped": skipped}


def _count_existing_complete_ai_triage_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    template_id: int,
    template_version: int,
    model: str,
    input_scope: str,
    rubric_version: str,
) -> int:
    row = connection.execute(
        """
        SELECT COUNT(DISTINCT p.arxiv_id) AS count
        FROM papers p
        JOIN daily_events e ON e.arxiv_id = p.arxiv_id
        WHERE e.date = ?
          AND p.metadata_status = 'complete'
          AND COALESCE(p.abstract, '') != ''
          AND EXISTS (
            SELECT 1
            FROM summaries s
            WHERE s.arxiv_id = p.arxiv_id
              AND s.template_id = ?
              AND s.template_version = ?
              AND s.model = ?
              AND s.input_scope = ?
              AND s.status = 'complete'
          )
          AND EXISTS (
            SELECT 1
            FROM paper_scores ps
            WHERE ps.arxiv_id = p.arxiv_id
              AND ps.model = ?
              AND ps.rubric_version = ?
              AND ps.status = 'complete'
          )
        """,
        (date, template_id, template_version, model, input_scope, model, rubric_version),
    ).fetchone()
    return int(row["count"] or 0)


def _list_ai_triage_candidate_ids_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    template_id: int,
    template_version: int,
    model: str,
    input_scope: str,
    rubric_version: str,
    limit: int | None,
    force: bool,
) -> list[str]:
    limit_sql = "" if limit is None else "LIMIT ?"
    params: tuple[Any, ...] = (
        date,
        1 if force else 0,
        template_id,
        template_version,
        model,
        input_scope,
        model,
        rubric_version,
    )
    if limit is not None:
        params = (*params, limit)
    rows = connection.execute(
        f"""
        SELECT DISTINCT p.arxiv_id
        FROM papers p
        JOIN daily_events e ON e.arxiv_id = p.arxiv_id
        WHERE e.date = ?
          AND p.metadata_status = 'complete'
          AND COALESCE(p.abstract, '') != ''
          AND (
            ? = 1
            OR NOT EXISTS (
                SELECT 1
                FROM summaries s
                WHERE s.arxiv_id = p.arxiv_id
                  AND s.template_id = ?
                  AND s.template_version = ?
                  AND s.model = ?
                  AND s.input_scope = ?
                  AND s.status = 'complete'
            )
            OR NOT EXISTS (
                SELECT 1
                FROM paper_scores ps
                WHERE ps.arxiv_id = p.arxiv_id
                  AND ps.model = ?
                  AND ps.rubric_version = ?
                  AND ps.status = 'complete'
            )
          )
        ORDER BY p.arxiv_id
        {limit_sql}
        """,
        params,
    ).fetchall()
    return [row["arxiv_id"] for row in rows]


def _has_complete_summary(
    connection: sqlite3.Connection,
    *,
    arxiv_id: str,
    template_id: int,
    template_version: int,
    model: str,
    input_scope: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM summaries
        WHERE arxiv_id = ?
          AND template_id = ?
          AND template_version = ?
          AND model = ?
          AND input_scope = ?
          AND status = 'complete'
        LIMIT 1
        """,
        (arxiv_id, template_id, template_version, model, input_scope),
    ).fetchone()
    return row is not None


def _has_complete_score(
    connection: sqlite3.Connection,
    *,
    arxiv_id: str,
    model: str,
    rubric_version: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM paper_scores
        WHERE arxiv_id = ?
          AND model = ?
          AND rubric_version = ?
          AND status = 'complete'
        LIMIT 1
        """,
        (arxiv_id, model, rubric_version),
    ).fetchone()
    return row is not None


def generate_ai_triage_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    template_id: int | None = None,
    template_name: str | None = None,
    model: str = "local",
    limit: int | None = None,
    force: bool = False,
    rubric_version: str = "reading_priority_v1",
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    template_repo = TemplateRepository(connection)
    template = template_repo.get_template(template_id=template_id, name=template_name)
    if template is None:
        raise ValueError("summary template not found")

    summary_repo = SummaryRepository(connection)
    score_repo = ScoreRepository(connection)
    template_id_value = int(template["id"])
    template_version = int(template["version"])
    input_scope = template["input_scope"]
    skipped = 0
    if not force:
        skipped = _count_existing_complete_ai_triage_for_date(
            connection,
            date=date,
            template_id=template_id_value,
            template_version=template_version,
            model=model,
            input_scope=input_scope,
            rubric_version=rubric_version,
        )
    candidate_ids = _list_ai_triage_candidate_ids_for_date(
        connection,
        date=date,
        template_id=template_id_value,
        template_version=template_version,
        model=model,
        input_scope=input_scope,
        rubric_version=rubric_version,
        limit=limit,
        force=force,
    )
    if llm_client is None and not llm_api_configured():
        return {
            "requested": 0,
            "completed": 0,
            "failed": 0,
            "skipped": skipped,
            "template_id": template_id_value,
            "template_version": template_version,
            "rubric_version": rubric_version,
            "status": "not_configured",
        }
    client = llm_client or OpenAICompatibleChatClient.from_env()
    expected_keys = [field["key"] for field in enabled_template_fields(template)]
    completed = 0
    failed = 0

    for arxiv_id in candidate_ids:
        paper = summary_repo.get_paper_for_summary(arxiv_id)
        if paper is None:
            skipped += 1
            continue
        try:
            response_text = client.complete(
                model=model,
                messages=build_ai_triage_messages(paper=paper, template=template),
            )
            content = parse_ai_triage_response(response_text, expected_summary_keys=expected_keys)
            with transaction(connection):
                summary_repo.upsert_summary(
                    arxiv_id=arxiv_id,
                    template_id=template_id_value,
                    template_version=template_version,
                    model=model,
                    language=template["language"],
                    input_scope=input_scope,
                    content=content["summary"],
                    status="complete",
                )
                score_repo.upsert_score(
                    arxiv_id=arxiv_id,
                    model=model,
                    rubric_version=rubric_version,
                    content=content["score"],
                    status="complete",
                )
            completed += 1
        except Exception as exc:
            error = str(exc)
            failed += 1
            with transaction(connection):
                if force or not _has_complete_summary(
                    connection,
                    arxiv_id=arxiv_id,
                    template_id=template_id_value,
                    template_version=template_version,
                    model=model,
                    input_scope=input_scope,
                ):
                    summary_repo.upsert_summary(
                        arxiv_id=arxiv_id,
                        template_id=template_id_value,
                        template_version=template_version,
                        model=model,
                        language=template["language"],
                        input_scope=input_scope,
                        content={"error": error},
                        status="failed",
                    )
                if force or not _has_complete_score(
                    connection,
                    arxiv_id=arxiv_id,
                    model=model,
                    rubric_version=rubric_version,
                ):
                    score_repo.upsert_score(
                        arxiv_id=arxiv_id,
                        model=model,
                        rubric_version=rubric_version,
                        content={
                            "score_total": 0,
                            "score_relevance": 0,
                            "score_novelty": 0,
                            "score_technical_depth": 0,
                            "score_evidence": 0,
                            "score_actionability": 0,
                            "recommended_action": "skip",
                            "rationale": error,
                        },
                        status="failed",
                    )

    return {
        "requested": len(candidate_ids),
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "template_id": template_id_value,
        "template_version": template_version,
        "rubric_version": rubric_version,
    }


def complete_ai_triage_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    template_id: int | None = None,
    template_name: str | None = None,
    model: str = "local",
    batch_size: int = 20,
    max_rounds: int | None = None,
    rubric_version: str = "reading_priority_v1",
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    round_count = 0
    if llm_client is None and not llm_api_configured():
        return {
            "date": date,
            "status": "not_configured",
            "rounds": 0,
            "summary": _summary_coverage(
                connection,
                date=date,
                template_id=template_id,
                template_name=template_name,
                model=model,
            ),
            "score": _score_coverage(connection, date=date, model=model, rubric_version=rubric_version),
            "runs": runs,
        }
    if TemplateRepository(connection).get_template(template_id=template_id, name=template_name) is None:
        return {
            "date": date,
            "status": "template_missing",
            "rounds": 0,
            "summary": _summary_coverage(
                connection,
                date=date,
                template_id=template_id,
                template_name=template_name,
                model=model,
            ),
            "score": _score_coverage(connection, date=date, model=model, rubric_version=rubric_version),
            "runs": runs,
        }

    while max_rounds is None or round_count < max_rounds:
        summary = _summary_coverage(
            connection,
            date=date,
            template_id=template_id,
            template_name=template_name,
            model=model,
        )
        score = _score_coverage(connection, date=date, model=model, rubric_version=rubric_version)
        if summary["eligible"] == summary["complete"] and score["eligible"] == score["complete"]:
            return {
                "date": date,
                "status": "complete",
                "rounds": round_count,
                "summary": summary,
                "score": score,
                "runs": runs,
            }

        result = generate_ai_triage_for_date(
            connection,
            date=date,
            template_id=template_id,
            template_name=template_name,
            model=model,
            limit=batch_size,
            force=False,
            rubric_version=rubric_version,
            llm_client=llm_client,
        )
        runs.append(result)
        round_count += 1

        if result["requested"] == 0:
            break
        if result["completed"] == 0 and result["failed"] > 0:
            return {
                "date": date,
                "status": "failed",
                "rounds": round_count,
                "summary": _summary_coverage(
                    connection,
                    date=date,
                    template_id=template_id,
                    template_name=template_name,
                    model=model,
                ),
                "score": _score_coverage(connection, date=date, model=model, rubric_version=rubric_version),
                "runs": runs,
            }

    summary = _summary_coverage(
        connection,
        date=date,
        template_id=template_id,
        template_name=template_name,
        model=model,
    )
    score = _score_coverage(connection, date=date, model=model, rubric_version=rubric_version)
    status = "complete" if summary["eligible"] == summary["complete"] and score["eligible"] == score["complete"] else "max_rounds"
    return {
        "date": date,
        "status": status,
        "rounds": round_count,
        "summary": summary,
        "score": score,
        "runs": runs,
    }


def _daily_metadata_counts(connection: sqlite3.Connection, *, date: str) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT
            COUNT(DISTINCT p.arxiv_id) AS total,
            COUNT(DISTINCT CASE WHEN p.metadata_status = 'complete' THEN p.arxiv_id END) AS complete,
            COUNT(DISTINCT CASE WHEN p.metadata_status = 'pending' THEN p.arxiv_id END) AS pending,
            COUNT(DISTINCT CASE WHEN p.metadata_status = 'failed' THEN p.arxiv_id END) AS failed,
            COUNT(DISTINCT CASE WHEN p.metadata_status = 'retryable' THEN p.arxiv_id END) AS retryable
        FROM papers p
        JOIN daily_events e ON e.arxiv_id = p.arxiv_id
        WHERE e.date = ?
        """,
        (date,),
    ).fetchone()
    return {key: int(row[key] or 0) for key in ["total", "complete", "pending", "failed", "retryable"]}


def _summary_coverage(
    connection: sqlite3.Connection,
    *,
    date: str,
    template_id: int | None,
    template_name: str | None,
    model: str,
) -> dict[str, Any]:
    template = TemplateRepository(connection).get_template(template_id=template_id, name=template_name)
    if template is None:
        eligible = _eligible_daily_paper_count(connection, date=date)
        return {
            "eligible": eligible,
            "complete": 0,
            "failed": 0,
            "missing": eligible,
            "template_id": template_id,
            "template_version": None,
            "template_name": template_name,
            "template_missing": True,
            "required_fields": [],
        }

    fields = enabled_template_fields(template)
    rows = connection.execute(
        """
        SELECT
            p.arxiv_id,
            MAX(CASE WHEN s.status = 'complete' THEN 1 ELSE 0 END) AS has_complete,
            MAX(CASE WHEN s.status = 'failed' THEN 1 ELSE 0 END) AS has_failed
        FROM papers p
        JOIN daily_events e ON e.arxiv_id = p.arxiv_id
        LEFT JOIN summaries s
            ON s.arxiv_id = p.arxiv_id
           AND s.template_id = ?
           AND s.template_version = ?
           AND s.model = ?
           AND s.input_scope = ?
        WHERE e.date = ?
          AND p.metadata_status = 'complete'
          AND COALESCE(p.abstract, '') != ''
        GROUP BY p.arxiv_id
        """,
        (int(template["id"]), int(template["version"]), model, template["input_scope"], date),
    ).fetchall()
    complete = sum(1 for row in rows if int(row["has_complete"] or 0) == 1)
    failed = sum(1 for row in rows if int(row["has_complete"] or 0) == 0 and int(row["has_failed"] or 0) == 1)
    eligible = len(rows)
    return {
        "eligible": eligible,
        "complete": complete,
        "failed": failed,
        "missing": eligible - complete - failed,
        "template_id": int(template["id"]),
        "template_version": int(template["version"]),
        "template_name": template["name"],
        "template_missing": False,
        "required_fields": [field["key"] for field in fields],
    }


def _score_coverage(
    connection: sqlite3.Connection,
    *,
    date: str,
    model: str,
    rubric_version: str,
) -> dict[str, int | str]:
    rows = connection.execute(
        """
        SELECT
            p.arxiv_id,
            MAX(CASE WHEN ps.status = 'complete' THEN 1 ELSE 0 END) AS has_complete,
            MAX(CASE WHEN ps.status = 'failed' THEN 1 ELSE 0 END) AS has_failed
        FROM papers p
        JOIN daily_events e ON e.arxiv_id = p.arxiv_id
        LEFT JOIN paper_scores ps
            ON ps.arxiv_id = p.arxiv_id
           AND ps.model = ?
           AND ps.rubric_version = ?
        WHERE e.date = ?
          AND p.metadata_status = 'complete'
          AND COALESCE(p.abstract, '') != ''
        GROUP BY p.arxiv_id
        """,
        (model, rubric_version, date),
    ).fetchall()
    complete = sum(1 for row in rows if int(row["has_complete"] or 0) == 1)
    failed = sum(1 for row in rows if int(row["has_complete"] or 0) == 0 and int(row["has_failed"] or 0) == 1)
    eligible = len(rows)
    return {
        "eligible": eligible,
        "complete": complete,
        "failed": failed,
        "missing": eligible - complete - failed,
        "rubric_version": rubric_version,
    }


def _eligible_daily_paper_count(connection: sqlite3.Connection, *, date: str) -> int:
    row = connection.execute(
        """
        SELECT COUNT(DISTINCT p.arxiv_id) AS count
        FROM papers p
        JOIN daily_events e ON e.arxiv_id = p.arxiv_id
        WHERE e.date = ?
          AND p.metadata_status = 'complete'
          AND COALESCE(p.abstract, '') != ''
        """,
        (date,),
    ).fetchone()
    return int(row["count"] or 0)


def _daily_pipeline_blockers(
    *,
    crawl: dict[str, Any],
    metadata: dict[str, int],
    summary: dict[str, Any],
    score: dict[str, int | str],
) -> list[str]:
    blockers: list[str] = []
    if crawl["status"] == "waiting":
        blockers.append("crawl_waiting_for_arxiv_update")
    elif crawl["status"] == "no_run":
        blockers.append("crawl_no_run")
    elif crawl["status"] != "complete":
        blockers.append("crawl_incomplete")
    if metadata["pending"]:
        blockers.append("metadata_pending")
    if metadata["failed"]:
        blockers.append("metadata_failed")
    if metadata["retryable"]:
        blockers.append("metadata_retryable")
    if summary["template_missing"]:
        blockers.append("summary_template_missing")
    if summary["failed"]:
        blockers.append("summary_failed")
    if summary["missing"]:
        blockers.append("summary_missing")
    if score["failed"]:
        blockers.append("score_failed")
    if score["missing"]:
        blockers.append("score_missing")
    return blockers


def get_daily_pipeline_status(
    connection: sqlite3.Connection,
    *,
    date: str,
    template_id: int | None = None,
    template_name: str | None = None,
    model: str = "local",
    expected_categories: list[str] | None = None,
    rubric_version: str = "reading_priority_v1",
) -> dict[str, Any]:
    crawl = get_crawl_completeness_for_date(
        connection,
        date=date,
        expected_categories=expected_categories,
    )
    metadata = _daily_metadata_counts(connection, date=date)
    summary = _summary_coverage(
        connection,
        date=date,
        template_id=template_id,
        template_name=template_name,
        model=model,
    )
    score = _score_coverage(
        connection,
        date=date,
        model=model,
        rubric_version=rubric_version,
    )
    preflight = PreflightRepository(connection).latest_for_date(date) or {
        "date": date,
        "status": "not_started",
        "category_count": 0,
        "source_count": 0,
        "listing_entry_count": 0,
        "distinct_paper_count": 0,
        "missing_count": 0,
        "error_counts": {},
        "sources": [],
    }
    automation = DailyAutomationRepository(connection).latest_for_date(date) or {
        "date": date,
        "status": "not_started",
        "current_step": "idle",
        "crawl_mode": "auto",
        "started_at": None,
        "updated_at": None,
        "finished_at": None,
        "error": None,
    }
    blockers = _daily_pipeline_blockers(crawl=crawl, metadata=metadata, summary=summary, score=score)
    if metadata["total"] == 0 and crawl["status"] == "no_run":
        status = "not_started"
    else:
        status = "complete" if not blockers else "partial"
    return {
        "date": date,
        "status": status,
        "blockers": blockers,
        "crawl": crawl,
        "automation": automation,
        "preflight": preflight,
        "metadata": metadata,
        "summary": summary,
        "score": score,
    }


def run_daily_pipeline(
    connection: sqlite3.Connection,
    *,
    date: str,
    categories: list[str] | None = None,
    expected_categories: list[str] | None = None,
    template_id: int | None = None,
    template_name: str | None = None,
    model: str = "local",
    force_summary: bool = False,
    force_score: bool = False,
    oai_max_pages: int = 1,
    crawl_runner: Any | None = None,
    crawl_retry_runner: Any | None = None,
    metadata_runner: Any | None = None,
    summary_runner: Any | None = None,
    score_runner: Any | None = None,
) -> dict[str, Any]:
    if crawl_runner is None:
        from arxiv_local_daily.crawler.live import run_live_daily_crawl

        crawl_runner = run_live_daily_crawl
    metadata_runner = metadata_runner or enrich_metadata_for_date_unified
    summary_runner = summary_runner or generate_summaries_for_date
    score_runner = score_runner or score_papers_for_date

    steps: dict[str, Any] = {}
    crawl_run_id = crawl_runner(connection, date=date, categories=categories)
    crawl_audit = get_crawl_completeness_for_date(
        connection,
        date=date,
        expected_categories=expected_categories,
    )
    steps["crawl"] = {"run_id": crawl_run_id, "audit": crawl_audit}

    if crawl_audit["retry_categories"]:
        if crawl_retry_runner is None:
            retry_result = retry_incomplete_crawl_categories_for_date(
                connection,
                date=date,
                expected_categories=expected_categories,
            )
        else:
            retry_result = crawl_retry_runner(
                connection,
                date=date,
                expected_categories=expected_categories,
            )
        steps["retry"] = retry_result
        steps["crawl"]["audit_after_retry"] = get_crawl_completeness_for_date(
            connection,
            date=date,
            expected_categories=expected_categories,
        )

    steps["metadata"] = metadata_runner(
        connection,
        date=date,
        limit=None,
        oai_max_pages=oai_max_pages,
    )

    try:
        steps["summary"] = summary_runner(
            connection,
            date=date,
            template_id=template_id,
            template_name=template_name,
            model=model,
            limit=None,
            force=force_summary,
        )
    except ValueError as exc:
        steps["summary"] = {
            "requested": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "error": str(exc),
        }

    steps["score"] = score_runner(
        connection,
        date=date,
        model=model,
        limit=None,
        force=force_score,
    )

    daily_status = get_daily_pipeline_status(
        connection,
        date=date,
        template_id=template_id,
        template_name=template_name,
        model=model,
        expected_categories=expected_categories,
    )
    return {
        "date": date,
        "status": daily_status["status"],
        "steps": steps,
        "daily_status": daily_status,
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
