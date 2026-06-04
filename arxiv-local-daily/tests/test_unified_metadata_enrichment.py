from arxiv_local_daily.crawler.oai import OaiListRecordsPage
from arxiv_local_daily.models import CrawlSourceInput, PaperMetadata
from arxiv_local_daily.services import (
    complete_metadata_for_date,
    enrich_metadata_for_date_unified,
    ingest_daily_crawl_sources,
)


class FakeMetadataClient:
    def __init__(self, papers: list[PaperMetadata]):
        self.papers = papers
        self.calls: list[list[str]] = []

    def fetch_by_ids(self, ids: list[str]) -> list[PaperMetadata]:
        self.calls.append(ids)
        return self.papers


class EchoMetadataClient:
    def __init__(self):
        self.calls: list[list[str]] = []

    def fetch_by_ids(self, ids: list[str]) -> list[PaperMetadata]:
        self.calls.append(ids)
        return [_metadata(arxiv_id, title=f"Metadata {arxiv_id}") for arxiv_id in ids]


class RateLimitedMetadataClient:
    def fetch_by_ids(self, ids: list[str]) -> list[PaperMetadata]:
        raise RuntimeError("HTTP 429 Too Many Requests")


class FakeOaiClient:
    def __init__(self, pages: list[OaiListRecordsPage]):
        self.pages = pages
        self.calls: list[dict] = []

    def fetch_list_records(self, **kwargs) -> OaiListRecordsPage:
        self.calls.append(kwargs)
        return self.pages.pop(0)


def _metadata(
    arxiv_id: str,
    *,
    title: str,
    abstract: str = "Abstract.",
    authors: list[str] | None = None,
    categories: list[str] | None = None,
) -> PaperMetadata:
    return PaperMetadata(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=authors or ["Ada Lovelace"],
        primary_category=(categories or ["cs.AI"])[0],
        categories=categories or ["cs.AI"],
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        published_at="2026-06-03",
        updated_at="2026-06-03",
    )


def test_unified_metadata_enrichment_merges_sources_and_records_report(db):
    html = """
    <div id="dlpage">
      <h3>New submissions for Wed, 3 Jun 2026</h3>
      <dl>
        <dt><span class="list-identifier"><a title="Abstract" href="/abs/2606.00001">arXiv:2606.00001</a></span></dt>
        <dd><div class="list-title">Title: Listing title one</div></dd>
        <dt><span class="list-identifier"><a title="Abstract" href="/abs/2606.00002">arXiv:2606.00002</a></span></dt>
        <dd><div class="list-title">Title: Listing title two</div></dd>
      </dl>
    </div>
    """
    ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
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
    id_client = FakeMetadataClient(
        [
            _metadata("2606.00001", title="ID API title one", abstract="Long ID abstract one."),
            _metadata("2606.00002", title="ID API title two", abstract="Long ID abstract two."),
        ]
    )
    oai_client = FakeOaiClient(
        [
            OaiListRecordsPage(
                papers=[
                    _metadata("2606.00001", title="OAI title one", abstract="Short."),
                    _metadata("2606.99999", title="OAI extra paper"),
                ]
            )
        ]
    )

    result = enrich_metadata_for_date_unified(
        db,
        date="2026-06-03",
        metadata_client=id_client,
        oai_client=oai_client,
        limit=10,
        oai_max_pages=1,
    )

    assert result["status"] == "complete"
    assert result["crawl_count"] == 2
    assert result["id_api_count"] == 2
    assert result["oai_count"] == 2
    assert result["merged"] == 2
    assert result["missing_after_merge"] == 0
    assert result["oai_missing_count"] == 1
    assert result["oai_extra_count"] == 1
    assert result["mismatch_count"] == 1
    assert id_client.calls == [["2606.00001", "2606.00002"]]

    run = db.execute("SELECT * FROM metadata_enrichment_runs WHERE id = ?", (result["run_id"],)).fetchone()
    assert run["status"] == "complete"
    assert run["merged_count"] == 2
    assert run["mismatch_count"] == 1

    paper = db.execute("SELECT title, abstract, metadata_status FROM papers WHERE arxiv_id = ?", ("2606.00001",)).fetchone()
    assert paper["title"] == "ID API title one"
    assert paper["abstract"] == "Long ID abstract one."
    assert paper["metadata_status"] == "complete"

    reports = db.execute(
        "SELECT report_type, arxiv_id FROM metadata_merge_reports WHERE run_id = ? ORDER BY report_type, arxiv_id",
        (result["run_id"],),
    ).fetchall()
    assert [(row["report_type"], row["arxiv_id"]) for row in reports] == [
        ("mismatch", "2606.00001"),
        ("oai_extra", "2606.99999"),
        ("oai_missing", "2606.00002"),
    ]


def test_unified_metadata_enrichment_marks_retryable_source_errors(db):
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
                html="""
                <div id="dlpage">
                  <h3>New submissions</h3>
                  <dl>
                    <dt><span class="list-identifier"><a title="Abstract" href="/abs/2606.00001">arXiv:2606.00001</a></span></dt>
                    <dd><div class="list-title">Title: Paper one</div></dd>
                    <dt><span class="list-identifier"><a title="Abstract" href="/abs/2606.00002">arXiv:2606.00002</a></span></dt>
                    <dd><div class="list-title">Title: Paper two</div></dd>
                  </dl>
                </div>
                """,
            )
        ],
    )

    result = enrich_metadata_for_date_unified(
        db,
        date="2026-06-04",
        metadata_client=RateLimitedMetadataClient(),
        oai_client=FakeOaiClient([]),
        only_incomplete=True,
        oai_max_pages=0,
    )

    assert result["status"] == "retryable"
    rows = db.execute(
        """
        SELECT metadata_status, metadata_attempts, metadata_next_run_at, metadata_error
        FROM papers
        ORDER BY arxiv_id
        """
    ).fetchall()
    assert [row["metadata_status"] for row in rows] == ["retryable", "retryable"]
    assert [row["metadata_attempts"] for row in rows] == [1, 1]
    assert rows[0]["metadata_next_run_at"] is not None
    assert "HTTP 429" in rows[0]["metadata_error"]


def test_complete_metadata_for_date_runs_batches_until_all_complete(db):
    html = """
    <div id="dlpage">
      <h3>New submissions</h3>
      <dl>
        <dt><span class="list-identifier"><a title="Abstract" href="/abs/2606.00001">arXiv:2606.00001</a></span></dt>
        <dd><div class="list-title">Title: Paper one</div></dd>
        <dt><span class="list-identifier"><a title="Abstract" href="/abs/2606.00002">arXiv:2606.00002</a></span></dt>
        <dd><div class="list-title">Title: Paper two</div></dd>
        <dt><span class="list-identifier"><a title="Abstract" href="/abs/2606.00003">arXiv:2606.00003</a></span></dt>
        <dd><div class="list-title">Title: Paper three</div></dd>
      </dl>
    </div>
    """
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
    id_client = EchoMetadataClient()

    result = complete_metadata_for_date(
        db,
        date="2026-06-04",
        batch_size=2,
        max_rounds=5,
        metadata_client=id_client,
        oai_client=FakeOaiClient([]),
        oai_max_pages=0,
        sleep_fn=lambda seconds: None,
    )

    assert result["status"] == "complete"
    assert result["rounds"] == 2
    assert result["metadata"]["complete"] == 3
    assert id_client.calls == [["2606.00001", "2606.00002"], ["2606.00003"]]
