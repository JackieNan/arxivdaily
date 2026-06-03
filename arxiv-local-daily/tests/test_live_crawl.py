from pathlib import Path

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
