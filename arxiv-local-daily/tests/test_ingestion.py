from pathlib import Path

from arxiv_local_daily.services import ingest_daily_listing_html


def test_ingestion_persists_run_source_papers_and_events(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    run_id = ingest_daily_listing_html(
        db,
        date="2026-06-03",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
        html=html,
    )

    run = db.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    source = db.execute("SELECT * FROM crawl_run_sources WHERE run_id = ?", (run_id,)).fetchone()
    papers = db.execute("SELECT arxiv_id, metadata_status FROM papers ORDER BY arxiv_id").fetchall()
    events = db.execute(
        "SELECT arxiv_id, event_type, listing_category FROM daily_events ORDER BY arxiv_id"
    ).fetchall()

    assert run["status"] == "complete"
    assert source["parsed_count"] == 3
    assert [(row["arxiv_id"], row["metadata_status"]) for row in papers] == [
        ("2606.00001", "pending"),
        ("2606.00002", "pending"),
        ("2606.00003", "pending"),
    ]
    assert [(row["arxiv_id"], row["event_type"], row["listing_category"]) for row in events] == [
        ("2606.00001", "new", "cs.AI"),
        ("2606.00002", "cross-list", "cs.AI"),
        ("2606.00003", "replacement", "cs.AI"),
    ]


def test_ingestion_rerun_does_not_duplicate_events(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    ingest_daily_listing_html(
        db,
        date="2026-06-03",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
        html=html,
    )
    ingest_daily_listing_html(
        db,
        date="2026-06-03",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
        html=html,
    )

    event_count = db.execute("SELECT COUNT(*) AS count FROM daily_events").fetchone()["count"]
    run_count = db.execute("SELECT COUNT(*) AS count FROM crawl_runs").fetchone()["count"]

    assert event_count == 3
    assert run_count == 2
