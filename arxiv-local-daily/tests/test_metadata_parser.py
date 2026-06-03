from pathlib import Path

import httpx

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.crawler.metadata import (
    ArxivMetadataClient,
    build_arxiv_api_query_url,
    extract_arxiv_id_and_version,
    parse_arxiv_atom_feed,
)


def test_extract_arxiv_id_and_version_handles_modern_and_legacy_ids():
    assert extract_arxiv_id_and_version("http://arxiv.org/abs/2606.00001v2") == (
        "2606.00001",
        "v2",
    )
    assert extract_arxiv_id_and_version("http://arxiv.org/abs/hep-th/9901001v1") == (
        "hep-th/9901001",
        "v1",
    )


def test_build_arxiv_api_query_url_uses_id_list():
    url = build_arxiv_api_query_url(["2606.00001", "hep-th/9901001"])

    assert url == (
        "https://export.arxiv.org/api/query?"
        "id_list=2606.00001%2Chep-th%2F9901001&start=0&max_results=2"
    )


def test_parse_arxiv_atom_feed_extracts_paper_metadata():
    xml = Path("tests/fixtures/arxiv_api_feed.xml").read_text()

    papers = parse_arxiv_atom_feed(xml)

    assert [paper.arxiv_id for paper in papers] == ["2606.00001", "hep-th/9901001"]
    assert papers[0].title == "First paper title"
    assert papers[0].authors == ["Ada Lovelace", "Alan Turing"]
    assert papers[0].abstract == "First abstract with whitespace."
    assert papers[0].primary_category == "cs.AI"
    assert papers[0].categories == ["cs.AI", "cs.LG"]
    assert papers[0].abs_url == "http://arxiv.org/abs/2606.00001v2"
    assert papers[0].pdf_url == "http://arxiv.org/pdf/2606.00001v2"
    assert papers[0].versions[0].version == "v2"
    assert papers[0].versions[0].comment == "12 pages"
    assert papers[1].arxiv_id == "hep-th/9901001"


def test_metadata_client_fetches_and_parses_ids():
    xml = Path("tests/fixtures/arxiv_api_feed.xml").read_text()
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=xml)

    http_client = ArxivHttpClient(
        transport=httpx.MockTransport(handler),
        retry_sleep_seconds=0,
    )
    client = ArxivMetadataClient(http_client=http_client)

    papers = client.fetch_by_ids(["2606.00001", "hep-th/9901001"])

    assert requested_urls == [
        "https://export.arxiv.org/api/query?id_list=2606.00001%2Chep-th%2F9901001&start=0&max_results=2"
    ]
    assert [paper.arxiv_id for paper in papers] == ["2606.00001", "hep-th/9901001"]
