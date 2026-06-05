import sqlite3
from typing import Any

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.crawler.live import build_daily_listing_url, discover_categories
from arxiv_local_daily.crawler.parser import (
    parse_daily_listing,
    parse_daily_listing_count,
    parse_daily_listing_date,
    parse_daily_listing_has_no_updates,
)
from arxiv_local_daily.db import transaction
from arxiv_local_daily.repositories import PreflightRepository


def _source_error_counts(sources: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source in sources:
        if source["status"] == "complete":
            continue
        counts[source["status"]] = counts.get(source["status"], 0) + 1
    return counts


def run_daily_listing_preflight(
    connection: sqlite3.Connection,
    *,
    date: str,
    categories: list[str] | None = None,
    http_client: ArxivHttpClient | None = None,
    base_url: str = "https://arxiv.org",
) -> dict[str, Any]:
    client = http_client or ArxivHttpClient()
    crawl_categories = categories if categories is not None else discover_categories(client, base_url=base_url)
    sources: list[dict[str, Any]] = []
    all_ids: set[str] = set()

    for category in crawl_categories:
        url = build_daily_listing_url(base_url, category)
        try:
            response = client.fetch_text(url)
        except Exception as exc:
            sources.append(
                {
                    "category": category,
                    "url": url,
                    "status": "failed",
                    "http_status": None,
                    "listing_date": None,
                    "parsed_count": 0,
                    "expected_count": None,
                    "distinct_count": 0,
                    "missing_count": 0,
                    "arxiv_ids": [],
                    "error": str(exc),
                }
            )
            continue

        if response.status_code != 200:
            sources.append(
                {
                    "category": category,
                    "url": url,
                    "status": "failed",
                    "http_status": response.status_code,
                    "listing_date": None,
                    "parsed_count": 0,
                    "expected_count": None,
                    "distinct_count": 0,
                    "missing_count": 0,
                    "arxiv_ids": [],
                    "error": f"HTTP {response.status_code}",
                }
            )
            continue

        listing_date = parse_daily_listing_date(response.text)
        if listing_date != date:
            sources.append(
                {
                    "category": category,
                    "url": url,
                    "status": "date_mismatch",
                    "http_status": response.status_code,
                    "listing_date": listing_date,
                    "parsed_count": 0,
                    "expected_count": parse_daily_listing_count(response.text),
                    "distinct_count": 0,
                    "missing_count": 0,
                    "arxiv_ids": [],
                    "error": (
                        f"arXiv listing date {listing_date or 'unknown'} does not match requested date {date}; "
                        "preflight cannot certify this daily list"
                    ),
                }
            )
            continue

        events = parse_daily_listing(response.text, listing_category=category, source_url=url)
        arxiv_ids = sorted({event.arxiv_id for event in events})
        expected_count = parse_daily_listing_count(response.text)
        parsed_count = len(events)
        if expected_count is None and parsed_count == 0 and parse_daily_listing_has_no_updates(response.text):
            expected_count = 0
            source_status = "complete"
            missing_count = 0
            error = None
        elif expected_count is None:
            source_status = "count_missing"
            missing_count = 0
            error = "declared count not found; preflight cannot certify this category"
        else:
            missing_count = max(expected_count - parsed_count, 0)
            source_status = "incomplete" if missing_count else "complete"
            error = "parsed count below declared count" if missing_count else None
        if source_status == "complete":
            all_ids.update(arxiv_ids)
        sources.append(
            {
                "category": category,
                "url": url,
                "status": source_status,
                "http_status": response.status_code,
                "listing_date": listing_date,
                "parsed_count": parsed_count,
                "expected_count": expected_count,
                "distinct_count": len(arxiv_ids),
                "missing_count": missing_count,
                "arxiv_ids": arxiv_ids,
                "error": error,
            }
        )

    error_counts = _source_error_counts(sources)
    status = "complete" if not error_counts else "partial"
    listing_entry_count = sum(int(source["parsed_count"] or 0) for source in sources)
    missing_count = sum(int(source["missing_count"] or 0) for source in sources)

    with transaction(connection):
        repo = PreflightRepository(connection)
        run_id = repo.create_run(
            date=date,
            mode="daily",
            status="running",
            category_count=len(crawl_categories),
        )
        for source in sources:
            repo.record_source(run_id=run_id, **source)
        repo.finish_run(
            run_id,
            status=status,
            source_count=len(sources),
            listing_entry_count=listing_entry_count,
            distinct_paper_count=len(all_ids),
            missing_count=missing_count,
            error_counts=error_counts,
        )
        report = repo.latest_for_date(date)
        if report is None:
            raise RuntimeError("preflight report was not persisted")
        return report
