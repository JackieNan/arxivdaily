import httpx

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.crawler.preflight import run_daily_listing_preflight


LISTING_HTML = """
<html>
  <body>
    <div id="dlpage">
      <h3>New submissions for Wed, 3 Jun 2026 (showing 1 through 3 of 3 entries)</h3>
      <dl>
        <dt><span class="list-identifier"><a title="Abstract" href="/abs/2606.00001">arXiv:2606.00001</a></span></dt>
        <dd><div class="list-title">Title: First Paper</div></dd>
        <dt><span class="list-identifier"><a title="Abstract" href="/abs/2606.00002">arXiv:2606.00002</a></span></dt>
        <dd><div class="list-title">Title: Second Paper</div></dd>
      </dl>
      <h3>Cross-lists for Wed, 3 Jun 2026</h3>
      <dl>
        <dt><span class="list-identifier"><a title="Abstract" href="/abs/2606.00003">arXiv:2606.00003</a></span></dt>
        <dd><div class="list-title">Title: Third Paper</div></dd>
      </dl>
    </div>
  </body>
</html>
"""


def test_daily_listing_preflight_records_distinct_paper_count_and_evidence(db):
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=LISTING_HTML)

    client = ArxivHttpClient(transport=httpx.MockTransport(handler), retry_sleep_seconds=0)

    report = run_daily_listing_preflight(
        db,
        date="2026-06-03",
        categories=["cs.AI", "cs.LG"],
        http_client=client,
    )

    assert requested_urls == [
        "https://arxiv.org/list/cs.AI/new",
        "https://arxiv.org/list/cs.LG/new",
    ]
    assert report["status"] == "complete"
    assert report["category_count"] == 2
    assert report["source_count"] == 2
    assert report["listing_entry_count"] == 6
    assert report["distinct_paper_count"] == 3
    assert report["missing_count"] == 0
    assert report["sources"][0]["status"] == "complete"
    assert report["sources"][0]["listing_date"] == "2026-06-03"
    assert report["sources"][0]["parsed_count"] == 3
    assert report["sources"][0]["expected_count"] == 3
    assert report["sources"][0]["distinct_count"] == 3
    assert report["sources"][0]["arxiv_ids"] == ["2606.00001", "2606.00002", "2606.00003"]


def test_daily_listing_preflight_is_partial_when_declared_count_is_missing(db):
    html = LISTING_HTML.replace(" (showing 1 through 3 of 3 entries)", "")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    client = ArxivHttpClient(transport=httpx.MockTransport(handler), retry_sleep_seconds=0)

    report = run_daily_listing_preflight(
        db,
        date="2026-06-03",
        categories=["cs.AI"],
        http_client=client,
    )

    assert report["status"] == "partial"
    assert report["sources"][0]["status"] == "count_missing"
    assert report["sources"][0]["parsed_count"] == 3
    assert report["sources"][0]["expected_count"] is None
    assert "declared count" in report["sources"][0]["error"]


def test_daily_listing_preflight_treats_explicit_no_updates_as_complete_zero_count(db):
    html = """
    <html>
      <body>
        <div id="dlpage">
          <h3>Showing new listings for Wed, 3 Jun 2026</h3>
          <p>No updates today.</p>
        </div>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    client = ArxivHttpClient(transport=httpx.MockTransport(handler), retry_sleep_seconds=0)

    report = run_daily_listing_preflight(
        db,
        date="2026-06-03",
        categories=["cs.GL"],
        http_client=client,
    )

    assert report["status"] == "complete"
    assert report["listing_entry_count"] == 0
    assert report["distinct_paper_count"] == 0
    assert report["sources"][0]["status"] == "complete"
    assert report["sources"][0]["parsed_count"] == 0
    assert report["sources"][0]["expected_count"] == 0
    assert report["sources"][0]["error"] is None
