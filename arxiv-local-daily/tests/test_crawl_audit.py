from pathlib import Path

from arxiv_local_daily.crawler.audit import build_crawl_completeness_report
from arxiv_local_daily.models import CrawlSourceInput
from arxiv_local_daily.services import ingest_daily_crawl_sources, retry_incomplete_crawl_categories_for_date


def _complete_source(category: str) -> CrawlSourceInput:
    return CrawlSourceInput(
        category=category,
        event_section="all",
        url=f"https://arxiv.org/list/{category}/new",
        status="complete",
        http_status=200,
        html=Path("tests/fixtures/list_cs_ai_new.html").read_text(),
    )


def _incomplete_source(category: str) -> CrawlSourceInput:
    return CrawlSourceInput(
        category=category,
        event_section="all",
        url=f"https://arxiv.org/list/{category}/new",
        status="complete",
        http_status=200,
        html=Path("tests/fixtures/list_cs_ai_new.html").read_text(),
        expected_count=4,
    )


def _failed_source(category: str) -> CrawlSourceInput:
    return CrawlSourceInput(
        category=category,
        event_section="all",
        url=f"https://arxiv.org/list/{category}/new",
        status="failed",
        http_status=503,
        html=None,
        error="HTTP 503",
    )


def test_crawl_completeness_report_returns_no_run_for_empty_date(db):
    report = build_crawl_completeness_report(db, date="2026-06-03")

    assert report["status"] == "no_run"
    assert report["expected_category_count"] == 0
    assert report["attempted_category_count"] == 0
    assert report["retry_categories"] == []


def test_crawl_completeness_report_marks_all_complete_sources_complete(db):
    ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
        mode="all-categories",
        sources=[_complete_source("cs.AI"), _complete_source("cs.LG")],
    )

    report = build_crawl_completeness_report(
        db,
        date="2026-06-03",
        expected_categories=["cs.AI", "cs.LG"],
    )

    assert report["status"] == "complete"
    assert report["expected_category_count"] == 2
    assert report["complete_category_count"] == 2
    assert report["failed_category_count"] == 0
    assert report["missing_category_count"] == 0
    assert report["retry_categories"] == []


def test_crawl_completeness_report_lists_failed_retry_categories(db):
    ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
        mode="all-categories",
        sources=[_complete_source("cs.AI"), _failed_source("cs.LG")],
    )

    report = build_crawl_completeness_report(
        db,
        date="2026-06-03",
        expected_categories=["cs.AI", "cs.LG"],
    )

    assert report["status"] == "partial"
    assert report["complete_category_count"] == 1
    assert report["failed_category_count"] == 1
    assert report["retry_categories"] == ["cs.LG"]
    assert report["categories"][1]["category"] == "cs.LG"
    assert report["categories"][1]["status"] == "failed"


def test_crawl_completeness_report_marks_count_mismatch_incomplete(db):
    ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
        mode="all-categories",
        sources=[_incomplete_source("cs.AI")],
    )

    report = build_crawl_completeness_report(
        db,
        date="2026-06-03",
        expected_categories=["cs.AI"],
    )

    assert report["status"] == "partial"
    assert report["incomplete_category_count"] == 1
    assert report["retry_categories"] == ["cs.AI"]
    assert report["categories"][0]["status"] == "incomplete"
    assert report["categories"][0]["parsed_count"] == 3
    assert report["categories"][0]["expected_count"] == 4
    assert report["categories"][0]["missing_count"] == 1


def test_crawl_completeness_report_detects_missing_expected_categories(db):
    ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
        mode="all-categories",
        sources=[_complete_source("cs.AI")],
    )

    report = build_crawl_completeness_report(
        db,
        date="2026-06-03",
        expected_categories=["cs.AI", "cs.LG"],
    )

    assert report["status"] == "partial"
    assert report["missing_category_count"] == 1
    assert report["missing_categories"] == ["cs.LG"]
    assert report["retry_categories"] == ["cs.LG"]


def test_crawl_completeness_report_combines_later_successful_retry(db):
    ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
        mode="all-categories",
        sources=[_complete_source("cs.AI"), _failed_source("cs.LG")],
    )
    ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
        mode="retry-incomplete",
        sources=[_complete_source("cs.LG")],
    )

    report = build_crawl_completeness_report(
        db,
        date="2026-06-03",
        expected_categories=["cs.AI", "cs.LG"],
    )

    assert report["status"] == "complete"
    assert report["complete_category_count"] == 2
    assert report["failed_category_count"] == 0
    assert report["retry_categories"] == []


def test_retry_incomplete_crawl_categories_for_date_calls_runner_with_retry_categories(db):
    ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
        mode="all-categories",
        sources=[_complete_source("cs.AI"), _failed_source("cs.LG")],
    )
    calls: list[list[str]] = []

    def fake_runner(connection, *, date: str, categories: list[str]):
        calls.append(categories)
        return 42

    result = retry_incomplete_crawl_categories_for_date(
        db,
        date="2026-06-03",
        expected_categories=["cs.AI", "cs.LG"],
        crawl_runner=fake_runner,
    )

    assert result == {"run_id": 42, "retried": 1, "categories": ["cs.LG"]}
    assert calls == [["cs.LG"]]


def test_retry_incomplete_crawl_categories_can_complete_combined_audit(db):
    ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
        mode="all-categories",
        sources=[_complete_source("cs.AI"), _failed_source("cs.LG")],
    )

    def fake_runner(connection, *, date: str, categories: list[str]):
        return ingest_daily_crawl_sources(
            connection,
            date=date,
            mode="retry-incomplete",
            sources=[_complete_source(category) for category in categories],
        )

    retry_incomplete_crawl_categories_for_date(
        db,
        date="2026-06-03",
        expected_categories=["cs.AI", "cs.LG"],
        crawl_runner=fake_runner,
    )

    report = build_crawl_completeness_report(
        db,
        date="2026-06-03",
        expected_categories=["cs.AI", "cs.LG"],
    )
    assert report["status"] == "complete"
    assert report["retry_categories"] == []
