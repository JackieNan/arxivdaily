from pathlib import Path

from arxiv_local_daily.crawler.metadata import parse_arxiv_atom_feed
from arxiv_local_daily.models import PaperMetadata, PaperVersionInput
from arxiv_local_daily.repositories import PaperRepository
from arxiv_local_daily.services import enrich_metadata_for_date, ingest_daily_listing_html


def test_upsert_metadata_updates_paper_and_versions(db):
    repo = PaperRepository(db)
    metadata = PaperMetadata(
        arxiv_id="2606.00001",
        title="Title",
        abstract="Abstract",
        authors=["Ada Lovelace"],
        primary_category="cs.AI",
        categories=["cs.AI", "cs.LG"],
        abs_url="http://arxiv.org/abs/2606.00001v1",
        pdf_url="http://arxiv.org/pdf/2606.00001v1",
        published_at="2026-06-02T00:00:00Z",
        updated_at="2026-06-03T00:00:00Z",
        versions=[
            PaperVersionInput(
                version="v1",
                updated_at="2026-06-03T00:00:00Z",
                comment="12 pages",
            )
        ],
    )

    repo.upsert_metadata(metadata)

    paper = db.execute("SELECT * FROM papers WHERE arxiv_id = ?", ("2606.00001",)).fetchone()
    version = db.execute("SELECT * FROM paper_versions WHERE arxiv_id = ?", ("2606.00001",)).fetchone()

    assert paper["metadata_status"] == "complete"
    assert paper["title"] == "Title"
    assert paper["authors_json"] == '["Ada Lovelace"]'
    assert paper["categories_json"] == '["cs.AI", "cs.LG"]'
    assert version["version"] == "v1"
    assert version["comment"] == "12 pages"


class FakeMetadataClient:
    def __init__(self, papers):
        self.papers = papers
        self.seen_ids = []

    def fetch_by_ids(self, ids):
        self.seen_ids.append(ids)
        return self.papers


class FailingMetadataClient:
    def fetch_by_ids(self, ids):
        raise RuntimeError("api unavailable")


class RateLimitedMetadataClient:
    def __init__(self):
        self.seen_ids = []

    def fetch_by_ids(self, ids):
        self.seen_ids.append(ids)
        raise RuntimeError("arXiv API metadata fetch failed: HTTP 429")


class TimeoutMetadataClient:
    def fetch_by_ids(self, ids):
        raise RuntimeError("The read operation timed out")


def test_enrich_metadata_for_date_updates_pending_daily_papers(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()
    xml = Path("tests/fixtures/arxiv_api_feed.xml").read_text()
    ingest_daily_listing_html(
        db,
        date="2026-06-03",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
        html=html,
    )
    papers = parse_arxiv_atom_feed(xml)[:1]
    client = FakeMetadataClient(papers)

    result = enrich_metadata_for_date(
        db,
        date="2026-06-03",
        metadata_client=client,
        limit=2,
    )

    paper = db.execute("SELECT * FROM papers WHERE arxiv_id = ?", ("2606.00001",)).fetchone()
    missing = db.execute("SELECT * FROM papers WHERE arxiv_id = ?", ("2606.00002",)).fetchone()

    assert client.seen_ids == [["2606.00001", "2606.00002"]]
    assert result == {"requested": 2, "updated": 1, "missing": 1, "failed": 0, "retryable": 0}
    assert paper["metadata_status"] == "complete"
    assert paper["title"] == "First paper title"
    assert missing["metadata_status"] == "failed"


def test_enrich_metadata_for_date_marks_batch_failed_when_client_errors(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()
    ingest_daily_listing_html(
        db,
        date="2026-06-03",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
        html=html,
    )

    result = enrich_metadata_for_date(
        db,
        date="2026-06-03",
        metadata_client=FailingMetadataClient(),
        limit=2,
    )

    statuses = db.execute(
        "SELECT arxiv_id, metadata_status FROM papers ORDER BY arxiv_id LIMIT 2"
    ).fetchall()

    assert result == {
        "requested": 2,
        "updated": 0,
        "missing": 0,
        "failed": 2,
        "retryable": 0,
        "error": "api unavailable",
    }
    assert [(row["arxiv_id"], row["metadata_status"]) for row in statuses] == [
        ("2606.00001", "failed"),
        ("2606.00002", "failed"),
    ]


def test_enrich_metadata_for_date_marks_rate_limits_retryable(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()
    ingest_daily_listing_html(
        db,
        date="2026-06-03",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
        html=html,
    )
    client = RateLimitedMetadataClient()

    result = enrich_metadata_for_date(
        db,
        date="2026-06-03",
        metadata_client=client,
        limit=2,
    )

    rows = db.execute(
        """
        SELECT arxiv_id, metadata_status, metadata_error, metadata_attempts, metadata_next_run_at
        FROM papers
        ORDER BY arxiv_id
        LIMIT 2
        """
    ).fetchall()

    assert result["requested"] == 2
    assert result["retryable"] == 2
    assert result["failed"] == 0
    assert result["next_run_at"] is not None
    assert client.seen_ids == [["2606.00001", "2606.00002"]]
    assert [
        (row["arxiv_id"], row["metadata_status"], row["metadata_attempts"])
        for row in rows
    ] == [
        ("2606.00001", "retryable", 1),
        ("2606.00002", "retryable", 1),
    ]
    assert rows[0]["metadata_error"] == "arXiv API metadata fetch failed: HTTP 429"
    assert rows[0]["metadata_next_run_at"] == result["next_run_at"]

    second_result = enrich_metadata_for_date(
        db,
        date="2026-06-03",
        metadata_client=client,
        limit=2,
    )

    assert second_result["requested"] == 1
    assert second_result["retryable"] == 1
    assert client.seen_ids == [["2606.00001", "2606.00002"], ["2606.00003"]]


def test_enrich_metadata_for_date_marks_timeouts_retryable(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()
    ingest_daily_listing_html(
        db,
        date="2026-06-03",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
        html=html,
    )

    result = enrich_metadata_for_date(
        db,
        date="2026-06-03",
        metadata_client=TimeoutMetadataClient(),
        limit=1,
    )

    row = db.execute(
        """
        SELECT metadata_status, metadata_error, metadata_attempts, metadata_next_run_at
        FROM papers
        WHERE arxiv_id = ?
        """,
        ("2606.00001",),
    ).fetchone()

    assert result["retryable"] == 1
    assert result["failed"] == 0
    assert result["next_run_at"] is not None
    assert row["metadata_status"] == "retryable"
    assert row["metadata_error"] == "The read operation timed out"
    assert row["metadata_attempts"] == 1
    assert row["metadata_next_run_at"] == result["next_run_at"]
