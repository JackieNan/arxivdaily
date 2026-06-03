import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from arxiv_local_daily.crawler.audit import build_crawl_completeness_report
from arxiv_local_daily.crawler.metadata import ArxivMetadataClient
from arxiv_local_daily.crawler.oai import OaiPmhMetadataClient
from arxiv_local_daily.crawler.parser import parse_daily_listing, parse_daily_listing_count
from arxiv_local_daily.db import transaction
from arxiv_local_daily.models import CrawlSourceInput, PaperMetadata
from arxiv_local_daily.repositories import (
    CrawlRepository,
    MetadataEnrichmentRepository,
    MetadataSyncRepository,
    PaperRepository,
    ScoreRepository,
    SummaryRepository,
    TemplateRepository,
)
from arxiv_local_daily.summary import (
    LLMClient,
    OpenAICompatibleChatClient,
    build_score_messages,
    build_summary_messages,
    enabled_template_fields,
    parse_score_response,
    parse_summary_response,
)

METADATA_RATE_LIMIT_BACKOFF_SECONDS = 10 * 60


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


def enrich_metadata_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    metadata_client: ArxivMetadataClient | None = None,
    limit: int = 100,
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
    limit: int = 100,
    oai_max_pages: int = 1,
) -> dict[str, Any]:
    paper_repo = PaperRepository(connection)
    enrich_repo = MetadataEnrichmentRepository(connection)
    id_client = metadata_client or ArxivMetadataClient()
    oai = oai_client or OaiPmhMetadataClient()
    crawl_ids = paper_repo.list_daily_ids_for_date(date, limit=limit)
    with transaction(connection):
        run_id = enrich_repo.create_run(date=date)

    id_api_papers: list[PaperMetadata] = []
    oai_papers: list[PaperMetadata] = []
    error: str | None = None
    try:
        if crawl_ids:
            id_api_papers = id_client.fetch_by_ids(crawl_ids)
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
        error = str(exc)

    id_api_by_id = {paper.arxiv_id: paper for paper in id_api_papers}
    oai_by_id = {paper.arxiv_id: paper for paper in oai_papers}
    crawl_id_set = set(crawl_ids)
    id_api_id_set = set(id_api_by_id)
    oai_id_set = set(oai_by_id)
    merged_count = 0
    missing_after_merge: list[str] = []
    oai_missing = sorted(crawl_id_set - oai_id_set)
    oai_extra = sorted(oai_id_set - crawl_id_set)
    mismatch_count = 0

    with transaction(connection):
        for paper in id_api_papers:
            enrich_repo.record_source(run_id=run_id, source="id_api", metadata=paper)
        for paper in oai_papers:
            enrich_repo.record_source(run_id=run_id, source="oai", metadata=paper)

        for arxiv_id in crawl_ids:
            chosen = _choose_metadata(arxiv_id, id_api_by_id=id_api_by_id, oai_by_id=oai_by_id)
            if chosen is None:
                missing_after_merge.append(arxiv_id)
                paper_repo.mark_metadata_status(arxiv_id, "failed", error="not returned by metadata sources")
                enrich_repo.record_report(
                    run_id=run_id,
                    report_type="missing_after_merge",
                    arxiv_id=arxiv_id,
                    details={"sources_checked": ["id_api", "oai"]},
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

        status = "failed" if error and merged_count == 0 else "partial" if error or missing_after_merge else "complete"
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
        "oai_missing_count": len(oai_missing),
        "oai_extra_count": len(oai_extra),
        "mismatch_count": mismatch_count,
        "error": error,
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


def score_papers_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    model: str = "local",
    limit: int = 20,
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
