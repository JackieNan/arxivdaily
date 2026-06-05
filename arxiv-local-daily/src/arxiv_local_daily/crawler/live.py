import sqlite3

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.crawler.parser import (
    parse_daily_listing_date,
    parse_historical_listing_for_date,
    parse_listing_dates,
)
from arxiv_local_daily.crawler.taxonomy import parse_category_taxonomy
from arxiv_local_daily.db import transaction
from arxiv_local_daily.models import CrawlSourceInput, ParsedDailyEvent
from arxiv_local_daily.repositories import CrawlRepository, PaperRepository
from arxiv_local_daily.services import ingest_daily_crawl_sources


def build_daily_listing_url(base_url: str, category: str) -> str:
    return f"{base_url.rstrip('/')}/list/{category}/new"


def build_historical_listing_url(base_url: str, category: str, date: str, *, skip: int = 0, show: int = 2000) -> str:
    month_code = f"{date[2:4]}{date[5:7]}"
    return f"{base_url.rstrip('/')}/list/{category}/{month_code}?skip={skip}&show={show}"


def build_category_taxonomy_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/category_taxonomy"


def fetch_current_arxiv_listing_date(
    *,
    http_client: ArxivHttpClient | None = None,
    categories: list[str] | None = None,
    base_url: str = "https://arxiv.org",
) -> str | None:
    client = http_client or ArxivHttpClient()
    probe_categories = categories if categories else ["cs.AI"]
    for category in probe_categories:
        url = build_daily_listing_url(base_url, category)
        try:
            response = client.fetch_text(url)
        except Exception:
            continue
        if response.status_code != 200:
            continue
        listing_date = parse_daily_listing_date(response.text)
        if listing_date is not None:
            return listing_date
    return None


def discover_categories(http_client: ArxivHttpClient, *, base_url: str = "https://arxiv.org") -> list[str]:
    response = http_client.fetch_text(build_category_taxonomy_url(base_url))
    if response.status_code != 200:
        raise ValueError(f"category taxonomy fetch failed: HTTP {response.status_code}")
    categories = parse_category_taxonomy(response.text)
    if not categories:
        raise ValueError("category taxonomy did not contain categories")
    return categories


def run_live_daily_crawl(
    connection: sqlite3.Connection,
    *,
    date: str,
    categories: list[str] | None = None,
    http_client: ArxivHttpClient | None = None,
    base_url: str = "https://arxiv.org",
) -> int:
    client = http_client or ArxivHttpClient()
    crawl_categories = categories if categories is not None else discover_categories(client, base_url=base_url)
    sources: list[CrawlSourceInput] = []
    for category in crawl_categories:
        url = build_daily_listing_url(base_url, category)
        try:
            response = client.fetch_text(url)
        except Exception as exc:
            sources.append(
                CrawlSourceInput(
                    category=category,
                    url=url,
                    status="failed",
                    http_status=None,
                    html=None,
                    error=str(exc),
                )
            )
            continue
        if response.status_code == 200:
            listing_date = parse_daily_listing_date(response.text)
            if listing_date != date:
                error = (
                    f"arXiv listing date {listing_date or 'unknown'} does not match requested date {date}; "
                    "not storing this /new page under the wrong date"
                )
                sources.append(
                    CrawlSourceInput(
                        category=category,
                        url=url,
                        status="date_mismatch",
                        http_status=response.status_code,
                        html=None,
                        error=error,
                    )
                )
                continue
            sources.append(
                CrawlSourceInput(
                    category=category,
                    url=url,
                    status="complete",
                    http_status=response.status_code,
                    html=response.text,
                )
            )
        else:
            sources.append(
                CrawlSourceInput(
                    category=category,
                    url=url,
                    status="failed",
                    http_status=response.status_code,
                    html=None,
                    error=f"HTTP {response.status_code}",
                )
            )
    return ingest_daily_crawl_sources(connection, date=date, mode="all-categories", sources=sources)


def _historical_page_has_passed_target(dates_seen: list[str], target_date: str) -> bool:
    if not dates_seen:
        return True
    sorted_dates = sorted(dates_seen)
    return sorted_dates[-1] < target_date or (sorted_dates[0] < target_date < sorted_dates[-1])


def _record_preparsed_crawl_sources(
    connection: sqlite3.Connection,
    *,
    date: str,
    mode: str,
    sources: list[tuple[CrawlSourceInput, list[ParsedDailyEvent]]],
    historical_cleanup_categories: list[str],
) -> int:
    summary_counts: dict[str, int] = {}
    failed_count = 0
    with transaction(connection):
        crawl_repo = CrawlRepository(connection)
        paper_repo = PaperRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode=mode, status="running")
        for source, events in sources:
            for event in events:
                summary_counts[event.event_type] = summary_counts.get(event.event_type, 0) + 1
                paper_repo.upsert_daily_event(date=date, event=event)
            if source.status != "complete":
                failed_count += 1
            crawl_repo.record_source(
                run_id=run_id,
                category=source.category,
                event_section=source.event_section,
                url=source.url,
                status=source.status,
                http_status=source.http_status,
                parsed_count=len(events),
                expected_count=source.expected_count,
                missing_count=source.missing_count,
                error=source.error,
                retry_count=source.retry_count,
            )
        if historical_cleanup_categories:
            placeholders = ", ".join("?" for _ in historical_cleanup_categories)
            connection.execute(
                f"""
                DELETE FROM daily_events
                WHERE date = ?
                  AND event_type = 'historical'
                  AND listing_category IN ({placeholders})
                """,
                (date, *historical_cleanup_categories),
            )
        final_status = "complete" if failed_count == 0 else "partial"
        crawl_repo.finish_run(run_id, status=final_status, summary_counts=summary_counts)
        return run_id


def run_historical_listing_crawl(
    connection: sqlite3.Connection,
    *,
    date: str,
    categories: list[str] | None = None,
    http_client: ArxivHttpClient | None = None,
    base_url: str = "https://arxiv.org",
    page_size: int = 2000,
    max_pages: int = 5,
) -> int:
    client = http_client or ArxivHttpClient()
    crawl_categories = categories if categories is not None else discover_categories(client, base_url=base_url)
    sources: list[tuple[CrawlSourceInput, list[ParsedDailyEvent]]] = []
    cleanup_categories: list[str] = []

    for category in crawl_categories:
        first_url = build_historical_listing_url(base_url, category, date, skip=0, show=page_size)
        category_events: list[ParsedDailyEvent] = []
        source_status = "complete"
        http_status: int | None = None
        error: str | None = None
        expected_count = 0
        reached_terminal_page = False

        for page_index in range(max_pages):
            skip = page_index * page_size
            url = build_historical_listing_url(base_url, category, date, skip=skip, show=page_size)
            try:
                response = client.fetch_text(url)
            except Exception as exc:
                source_status = "failed"
                error = str(exc)
                http_status = None
                reached_terminal_page = True
                break
            http_status = response.status_code
            if response.status_code == 404:
                error = "archive page not found; treated as no submissions"
                reached_terminal_page = True
                break
            if response.status_code != 200:
                source_status = "failed"
                error = f"HTTP {response.status_code}"
                reached_terminal_page = True
                break

            page_events = parse_historical_listing_for_date(
                response.text,
                date=date,
                listing_category=category,
                source_url=url,
            )
            if page_events:
                category_events.extend(page_events)
                expected_count = len(category_events)
                reached_terminal_page = True
                break

            dates_seen = parse_listing_dates(response.text)
            if date in dates_seen or _historical_page_has_passed_target(dates_seen, date):
                reached_terminal_page = True
                break

        if source_status == "complete" and not reached_terminal_page:
            source_status = "incomplete"
            error = f"historical listing crawl reached max_pages={max_pages} before finding or passing {date}"

        if source_status == "complete":
            cleanup_categories.append(category)
            expected_count = len(category_events)

        sources.append(
            (
                CrawlSourceInput(
                    category=category,
                    event_section="archive",
                    url=first_url,
                    status=source_status,
                    http_status=http_status,
                    expected_count=expected_count if source_status == "complete" else None,
                    missing_count=0,
                    error=error,
                ),
                category_events,
            )
        )

    return _record_preparsed_crawl_sources(
        connection,
        date=date,
        mode="historical-listing",
        sources=sources,
        historical_cleanup_categories=cleanup_categories,
    )
