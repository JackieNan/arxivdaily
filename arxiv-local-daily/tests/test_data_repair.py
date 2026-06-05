from pathlib import Path

from arxiv_local_daily.models import CrawlSourceInput, PaperMetadata, ParsedDailyEvent
from arxiv_local_daily.repositories import CrawlRepository, PaperRepository
from arxiv_local_daily.services import (
    ingest_daily_crawl_sources,
    repair_contaminated_daily_listing_dates,
)


def test_repair_contaminated_daily_listing_dates_removes_daily_listing_rows_but_preserves_historical(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()
    ingest_daily_crawl_sources(
        db,
        date="2026-06-04",
        mode="all-categories",
        sources=[
            CrawlSourceInput(
                category="cs.AI",
                url="https://arxiv.org/list/cs.AI/new",
                status="complete",
                http_status=200,
                html=html,
            )
        ],
    )
    paper_repo = PaperRepository(db)
    crawl_repo = CrawlRepository(db)
    paper_repo.upsert_metadata(
        PaperMetadata(
            arxiv_id="2606.99999",
            title="Historical OAI Paper",
            abstract="A historical metadata record.",
            authors=["Ada Lovelace"],
            primary_category="cs.AI",
            categories=["cs.AI"],
            abs_url="https://arxiv.org/abs/2606.99999",
            pdf_url="https://arxiv.org/pdf/2606.99999",
            published_at="2026-06-04T00:00:00Z",
            updated_at="2026-06-04T00:00:00Z",
        )
    )
    paper_repo.upsert_daily_event(
        date="2026-06-04",
        event=ParsedDailyEvent(
            arxiv_id="2606.99999",
            event_type="historical",
            listing_category="cs.AI",
            primary_category="cs.AI",
            title="Historical OAI Paper",
            source_url="oai-pmh:2026-06-04",
        ),
    )
    historical_run_id = crawl_repo.create_run(date="2026-06-04", mode="historical-oai", status="running")
    crawl_repo.record_source(
        run_id=historical_run_id,
        category="historical",
        event_section="historical",
        url="oai-pmh:2026-06-04",
        status="complete",
        http_status=200,
        parsed_count=1,
    )
    crawl_repo.finish_run(historical_run_id, status="complete", summary_counts={"historical": 1})
    db.commit()

    result = repair_contaminated_daily_listing_dates(db, dates=["2026-06-04"])

    assert result["dates"] == ["2026-06-04"]
    assert result["daily_events_deleted"] == 3
    assert result["crawl_runs_deleted"] == 1
    remaining_events = db.execute(
        """
        SELECT arxiv_id, event_type
        FROM daily_events
        WHERE date = ?
        ORDER BY arxiv_id
        """,
        ("2026-06-04",),
    ).fetchall()
    assert [dict(row) for row in remaining_events] == [{"arxiv_id": "2606.99999", "event_type": "historical"}]
    remaining_runs = db.execute(
        """
        SELECT mode
        FROM crawl_runs
        WHERE date = ?
        ORDER BY id
        """,
        ("2026-06-04",),
    ).fetchall()
    assert [row["mode"] for row in remaining_runs] == ["historical-oai"]
