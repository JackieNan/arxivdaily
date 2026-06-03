from arxiv_local_daily.crawler.oai import OaiListRecordsPage
from arxiv_local_daily.models import PaperMetadata
from arxiv_local_daily.repositories import MetadataSyncRepository
from arxiv_local_daily.services import run_oai_metadata_sync


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


def _paper(arxiv_id: str = "2606.00001") -> PaperMetadata:
    return PaperMetadata(
        arxiv_id=arxiv_id,
        title="OAI synced paper",
        abstract="OAI abstract.",
        authors=["Ada Lovelace"],
        primary_category="cs.AI",
        categories=["cs.AI", "cs.LG"],
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        published_at="2026-06-03",
        updated_at="2026-06-03",
    )


def test_oai_metadata_sync_persists_run_and_papers(db):
    repo = MetadataSyncRepository(db)
    run_id = repo.create_run(
        source="oai-pmh",
        from_date="2026-06-03",
        until_date="2026-06-03",
        set_spec="cs:cs:AI",
        max_pages=1,
    )
    db.commit()
    client = FakeOaiClient(
        [
            OaiListRecordsPage(
                papers=[_paper()],
                resumption_token="next-token",
                complete_list_size=2,
            )
        ]
    )

    result = run_oai_metadata_sync(
        db,
        sync_run_id=run_id,
        from_date="2026-06-03",
        until_date="2026-06-03",
        set_spec="cs:cs:AI",
        max_pages=1,
        oai_client=client,
    )

    run = repo.get_run(run_id)
    assert result["status"] == "complete"
    assert result["records_seen"] == 1
    assert result["records_upserted"] == 1
    assert result["pages_fetched"] == 1
    assert result["resumption_token"] == "next-token"
    assert run is not None
    assert run["status"] == "complete"
    assert run["records_seen"] == 1
    assert run["records_upserted"] == 1
    assert run["pages_fetched"] == 1
    assert run["resumption_token"] == "next-token"
    assert client.calls == [
        {
            "metadata_prefix": "arXiv",
            "from_date": "2026-06-03",
            "until_date": "2026-06-03",
            "set_spec": "cs:cs:AI",
            "resumption_token": None,
        }
    ]
    paper = db.execute("SELECT * FROM papers WHERE arxiv_id = ?", ("2606.00001",)).fetchone()
    assert paper["title"] == "OAI synced paper"
    assert paper["abstract"] == "OAI abstract."
    assert paper["metadata_status"] == "complete"


def test_oai_metadata_sync_records_failure(db):
    repo = MetadataSyncRepository(db)
    run_id = repo.create_run(source="oai-pmh", max_pages=1)
    db.commit()

    class FailingClient:
        def fetch_list_records(self, **kwargs):
            raise ValueError("OAI-PMH metadata fetch failed: HTTP 503")

    result = run_oai_metadata_sync(
        db,
        sync_run_id=run_id,
        max_pages=1,
        oai_client=FailingClient(),
    )

    run = repo.get_run(run_id)
    assert result["status"] == "failed"
    assert result["error"] == "OAI-PMH metadata fetch failed: HTTP 503"
    assert run is not None
    assert run["status"] == "failed"
    assert run["error"] == "OAI-PMH metadata fetch failed: HTTP 503"
