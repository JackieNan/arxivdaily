from arxiv_local_daily.crawler.oai import OaiListRecordsPage
from arxiv_local_daily.models import PaperMetadata
from arxiv_local_daily.services import run_historical_metadata_crawl


class FakeOaiClient:
    def __init__(self, pages: list[OaiListRecordsPage]):
        self.pages = pages
        self.calls: list[dict] = []

    def fetch_list_records(
        self,
        *,
        metadata_prefix: str = "arXiv",
        from_date: str | None = None,
        until_date: str | None = None,
        set_spec: str | None = None,
        resumption_token: str | None = None,
    ) -> OaiListRecordsPage:
        self.calls.append(
            {
                "metadata_prefix": metadata_prefix,
                "from_date": from_date,
                "until_date": until_date,
                "set_spec": set_spec,
                "resumption_token": resumption_token,
            }
        )
        return self.pages.pop(0)


def _paper(arxiv_id: str, categories: list[str]) -> PaperMetadata:
    return PaperMetadata(
        arxiv_id=arxiv_id,
        title=f"Historical paper {arxiv_id}",
        abstract="Historical OAI abstract.",
        authors=["Ada Lovelace"],
        primary_category=categories[0],
        categories=categories,
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        published_at="2026-06-03",
        updated_at="2026-06-03",
    )


def test_historical_metadata_crawl_persists_metadata_and_historical_events(db):
    client = FakeOaiClient(
        [
            OaiListRecordsPage(
                papers=[
                    _paper("2606.00001", ["cs.AI", "cs.LG"]),
                    _paper("2606.00002", ["math.NT"]),
                ],
                complete_list_size=2,
            )
        ]
    )

    result = run_historical_metadata_crawl(
        db,
        date="2026-06-03",
        categories=["cs.AI"],
        max_pages=10,
        oai_client=client,
    )

    assert result["status"] == "complete"
    assert result["records_seen"] == 2
    assert result["papers_upserted"] == 1
    assert client.calls == [
        {
            "metadata_prefix": "arXiv",
            "from_date": "2026-06-03",
            "until_date": "2026-06-03",
            "set_spec": None,
            "resumption_token": None,
        }
    ]

    paper = db.execute("SELECT * FROM papers WHERE arxiv_id = ?", ("2606.00001",)).fetchone()
    event = db.execute("SELECT * FROM daily_events WHERE arxiv_id = ?", ("2606.00001",)).fetchone()
    skipped = db.execute("SELECT * FROM papers WHERE arxiv_id = ?", ("2606.00002",)).fetchone()
    source = db.execute("SELECT * FROM crawl_run_sources WHERE run_id = ?", (result["run_id"],)).fetchone()

    assert paper["metadata_status"] == "complete"
    assert paper["title"] == "Historical paper 2606.00001"
    assert event["date"] == "2026-06-03"
    assert event["event_type"] == "historical"
    assert event["listing_category"] == "cs.AI"
    assert skipped is None
    assert source["category"] == "historical"
    assert source["status"] == "complete"
    assert source["parsed_count"] == 1
