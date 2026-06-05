from pathlib import Path

import httpx

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.crawler.live import (
    build_category_taxonomy_url,
    build_daily_listing_url,
    build_historical_listing_url,
    run_historical_listing_crawl,
    run_live_daily_crawl,
)
from arxiv_local_daily.models import CrawlSourceInput, PaperMetadata, ParsedDailyEvent
from arxiv_local_daily.repositories import PaperRepository
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


def test_build_historical_listing_url_uses_month_archive_and_pagination():
    assert build_historical_listing_url("https://arxiv.org", "cs.AI", "2026-06-05", skip=2000, show=2000) == (
        "https://arxiv.org/list/cs.AI/2606?skip=2000&show=2000"
    )


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


def test_run_historical_listing_crawl_fetches_archive_page_and_replaces_historical_events(db):
    archive_html = """
    <div id="dlpage">
      <h3>Fri, 5 Jun 2026</h3>
      <h4>New submissions</h4>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.00010">arXiv:2606.00010</a></dt>
        <dd><div class="list-title">Title: Exact Historical Paper</div></dd>
      </dl>
      <h4>Cross submissions</h4>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.00011">arXiv:2606.00011</a></dt>
        <dd><div class="list-title">Title: Exact Cross Paper</div></dd>
      </dl>
    </div>
    """
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=archive_html)

    paper_repo = PaperRepository(db)
    paper_repo.upsert_metadata(
        PaperMetadata(
            arxiv_id="2606.99999",
            title="Metadata Only Historical Paper",
            abstract="This metadata should survive exact listing cleanup.",
            authors=["Test Author"],
            primary_category="cs.AI",
            categories=["cs.AI"],
        )
    )
    paper_repo.upsert_daily_event(
        date="2026-06-05",
        event=ParsedDailyEvent(
            arxiv_id="2606.99999",
            event_type="historical",
            listing_category="cs.AI",
            primary_category="cs.AI",
            title="Metadata Only Historical Paper",
            source_url="oai-pmh:2026-06-05",
        ),
    )
    db.commit()
    client = ArxivHttpClient(transport=httpx.MockTransport(handler), retry_sleep_seconds=0)

    run_id = run_historical_listing_crawl(
        db,
        date="2026-06-05",
        categories=["cs.AI"],
        http_client=client,
    )

    assert requested_urls == ["https://arxiv.org/list/cs.AI/2606?skip=0&show=2000"]
    run = db.execute("SELECT mode, status FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    source = db.execute("SELECT category, status, parsed_count FROM crawl_run_sources WHERE run_id = ?", (run_id,)).fetchone()
    events = db.execute(
        """
        SELECT arxiv_id, event_type, listing_category
        FROM daily_events
        WHERE date = ?
        ORDER BY arxiv_id, event_type
        """,
        ("2026-06-05",),
    ).fetchall()
    metadata_row = db.execute("SELECT title, metadata_status FROM papers WHERE arxiv_id = ?", ("2606.99999",)).fetchone()

    assert dict(run) == {"mode": "historical-listing", "status": "complete"}
    assert dict(source) == {"category": "cs.AI", "status": "complete", "parsed_count": 2}
    assert [(row["arxiv_id"], row["event_type"], row["listing_category"]) for row in events] == [
        ("2606.00010", "new", "cs.AI"),
        ("2606.00011", "cross-list", "cs.AI"),
    ]
    assert dict(metadata_row) == {"title": "Metadata Only Historical Paper", "metadata_status": "complete"}


def test_run_historical_listing_crawl_paginates_until_page_dates_are_older_than_target(db):
    page_with_newer_date = """
    <div id="dlpage">
      <h3>Sat, 6 Jun 2026</h3>
      <h4>New submissions</h4>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.09999">arXiv:2606.09999</a></dt>
        <dd><div class="list-title">Title: Newer Paper</div></dd>
      </dl>
    </div>
    """
    page_with_older_date = """
    <div id="dlpage">
      <h3>Thu, 4 Jun 2026</h3>
      <h4>New submissions</h4>
      <dl>
        <dt><a title="Abstract" href="/abs/2606.00001">arXiv:2606.00001</a></dt>
        <dd><div class="list-title">Title: Older Paper</div></dd>
      </dl>
    </div>
    """
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if "skip=0" in str(request.url):
            return httpx.Response(200, text=page_with_newer_date)
        return httpx.Response(200, text=page_with_older_date)

    client = ArxivHttpClient(transport=httpx.MockTransport(handler), retry_sleep_seconds=0)

    run_id = run_historical_listing_crawl(
        db,
        date="2026-06-05",
        categories=["cs.AI"],
        http_client=client,
        page_size=2000,
        max_pages=5,
    )

    source = db.execute("SELECT status, parsed_count, expected_count FROM crawl_run_sources WHERE run_id = ?", (run_id,)).fetchone()
    event_count = db.execute("SELECT COUNT(*) AS count FROM daily_events WHERE date = ?", ("2026-06-05",)).fetchone()["count"]

    assert requested_urls == [
        "https://arxiv.org/list/cs.AI/2606?skip=0&show=2000",
        "https://arxiv.org/list/cs.AI/2606?skip=2000&show=2000",
    ]
    assert dict(source) == {"status": "complete", "parsed_count": 0, "expected_count": 0}
    assert event_count == 0
