from pathlib import Path

import httpx

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.crawler.live import (
    build_category_taxonomy_url,
    build_daily_listing_url,
    run_live_daily_crawl,
)
from arxiv_local_daily.models import CrawlSourceInput
from arxiv_local_daily.services import ingest_daily_crawl_sources


def test_ingest_daily_crawl_sources_records_complete_run(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    run_id = ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
        mode="all-categories",
        sources=[
            CrawlSourceInput(
                category="cs.AI",
                event_section="all",
                url="https://arxiv.org/list/cs.AI/new",
                status="complete",
                http_status=200,
                html=html,
            )
        ],
    )

    run = db.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    source = db.execute("SELECT * FROM crawl_run_sources WHERE run_id = ?", (run_id,)).fetchone()
    event_count = db.execute("SELECT COUNT(*) AS count FROM daily_events").fetchone()["count"]

    assert run["status"] == "complete"
    assert source["status"] == "complete"
    assert source["parsed_count"] == 3
    assert event_count == 3


def test_ingest_daily_crawl_sources_marks_run_partial_when_source_fails(db):
    run_id = ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
        mode="all-categories",
        sources=[
            CrawlSourceInput(
                category="cs.AI",
                event_section="all",
                url="https://arxiv.org/list/cs.AI/new",
                status="failed",
                http_status=503,
                html=None,
                error="HTTP 503",
            )
        ],
    )

    run = db.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    source = db.execute("SELECT * FROM crawl_run_sources WHERE run_id = ?", (run_id,)).fetchone()

    assert run["status"] == "partial"
    assert source["status"] == "failed"
    assert source["parsed_count"] == 0
    assert source["error"] == "HTTP 503"


def test_build_daily_listing_url_encodes_category():
    assert build_daily_listing_url("https://arxiv.org", "cond-mat.mtrl-sci") == (
        "https://arxiv.org/list/cond-mat.mtrl-sci/new"
    )


def test_build_category_taxonomy_url():
    assert build_category_taxonomy_url("https://arxiv.org") == "https://arxiv.org/category_taxonomy"


def test_run_live_daily_crawl_fetches_each_requested_category(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=html)

    client = ArxivHttpClient(
        transport=httpx.MockTransport(handler),
        retry_sleep_seconds=0,
    )

    run_id = run_live_daily_crawl(
        db,
        date="2026-06-03",
        categories=["cs.AI", "cs.LG"],
        http_client=client,
    )

    source_rows = db.execute(
        "SELECT category, status, parsed_count FROM crawl_run_sources WHERE run_id = ? ORDER BY category",
        (run_id,),
    ).fetchall()

    assert requested_urls == [
        "https://arxiv.org/list/cs.AI/new",
        "https://arxiv.org/list/cs.LG/new",
    ]
    assert [(row["category"], row["status"], row["parsed_count"]) for row in source_rows] == [
        ("cs.AI", "complete", 3),
        ("cs.LG", "complete", 3),
    ]


def test_run_live_daily_crawl_rejects_listing_date_mismatch(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    client = ArxivHttpClient(
        transport=httpx.MockTransport(handler),
        retry_sleep_seconds=0,
    )

    run_id = run_live_daily_crawl(
        db,
        date="2026-06-04",
        categories=["cs.AI"],
        http_client=client,
    )

    run = db.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    source = db.execute("SELECT * FROM crawl_run_sources WHERE run_id = ?", (run_id,)).fetchone()
    event_count = db.execute("SELECT COUNT(*) AS count FROM daily_events").fetchone()["count"]

    assert run["status"] == "partial"
    assert source["status"] == "date_mismatch"
    assert source["parsed_count"] == 0
    assert "2026-06-03" in source["error"]
    assert "2026-06-04" in source["error"]
    assert event_count == 0


def test_run_live_daily_crawl_records_failed_http_source(db):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="temporary")

    client = ArxivHttpClient(
        transport=httpx.MockTransport(handler),
        retry_sleep_seconds=0,
    )

    run_id = run_live_daily_crawl(
        db,
        date="2026-06-03",
        categories=["cs.AI"],
        http_client=client,
    )

    run = db.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    source = db.execute("SELECT * FROM crawl_run_sources WHERE run_id = ?", (run_id,)).fetchone()

    assert run["status"] == "partial"
    assert source["status"] == "failed"
    assert source["http_status"] == 503
    assert source["error"] == "HTTP 503"


def test_run_live_daily_crawl_records_network_exception_source(db):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("cannot connect", request=request)

    client = ArxivHttpClient(
        transport=httpx.MockTransport(handler),
        retry_sleep_seconds=0,
    )

    run_id = run_live_daily_crawl(
        db,
        date="2026-06-03",
        categories=["cs.AI"],
        http_client=client,
    )

    run = db.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    source = db.execute("SELECT * FROM crawl_run_sources WHERE run_id = ?", (run_id,)).fetchone()

    assert run["status"] == "partial"
    assert source["status"] == "failed"
    assert source["http_status"] is None
    assert source["error"] == "cannot connect"


def test_run_live_daily_crawl_discovers_categories_when_not_provided(db):
    taxonomy_html = Path("tests/fixtures/category_taxonomy.html").read_text()
    listing_html = Path("tests/fixtures/list_cs_ai_new.html").read_text()
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if str(request.url) == "https://arxiv.org/category_taxonomy":
            return httpx.Response(200, text=taxonomy_html)
        return httpx.Response(200, text=listing_html)

    client = ArxivHttpClient(
        transport=httpx.MockTransport(handler),
        retry_sleep_seconds=0,
    )

    run_id = run_live_daily_crawl(
        db,
        date="2026-06-03",
        http_client=client,
    )

    source_rows = db.execute(
        "SELECT category, status, parsed_count FROM crawl_run_sources WHERE run_id = ? ORDER BY category",
        (run_id,),
    ).fetchall()

    assert requested_urls == [
        "https://arxiv.org/category_taxonomy",
        "https://arxiv.org/list/cond-mat.mtrl-sci/new",
        "https://arxiv.org/list/cs.AI/new",
        "https://arxiv.org/list/cs.LG/new",
        "https://arxiv.org/list/hep-th/new",
    ]
    assert [(row["category"], row["status"], row["parsed_count"]) for row in source_rows] == [
        ("cond-mat.mtrl-sci", "complete", 3),
        ("cs.AI", "complete", 3),
        ("cs.LG", "complete", 3),
        ("hep-th", "complete", 3),
    ]
