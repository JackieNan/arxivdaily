from pathlib import Path

import httpx

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.crawler.oai import (
    OaiPmhMetadataClient,
    build_oai_list_records_url,
    parse_oai_list_records,
)


def test_build_oai_list_records_url_uses_filters():
    url = build_oai_list_records_url(
        base_url="https://oaipmh.arxiv.org/oai",
        metadata_prefix="arXiv",
        from_date="2026-06-03",
        until_date="2026-06-04",
        set_spec="cs:cs:AI",
    )

    assert url == (
        "https://oaipmh.arxiv.org/oai?"
        "verb=ListRecords&metadataPrefix=arXiv&from=2026-06-03&until=2026-06-04&set=cs%3Acs%3AAI"
    )


def test_build_oai_list_records_url_uses_resumption_token_only():
    url = build_oai_list_records_url(
        base_url="https://oaipmh.arxiv.org/oai",
        resumption_token="abc 123",
    )

    assert url == "https://oaipmh.arxiv.org/oai?verb=ListRecords&resumptionToken=abc+123"


def test_parse_oai_list_records_extracts_arxiv_metadata():
    xml = Path("tests/fixtures/oai_list_records_arxiv.xml").read_text()

    page = parse_oai_list_records(xml)

    assert page.resumption_token == "next-token"
    assert page.complete_list_size == 3
    assert len(page.papers) == 1
    paper = page.papers[0]
    assert paper.arxiv_id == "2606.00001"
    assert paper.title == "First paper title from OAI"
    assert paper.abstract == "First abstract from OAI with whitespace."
    assert paper.authors == ["Ada Lovelace", "Alan Turing Jr."]
    assert paper.primary_category == "cs.AI"
    assert paper.categories == ["cs.AI", "cs.LG"]
    assert paper.abs_url == "https://arxiv.org/abs/2606.00001"
    assert paper.pdf_url == "https://arxiv.org/pdf/2606.00001"
    assert paper.published_at == "2026-06-03"
    assert paper.updated_at == "2026-06-03"


def test_oai_client_fetches_list_records_page():
    xml = Path("tests/fixtures/oai_list_records_arxiv.xml").read_text()
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=xml)

    http_client = ArxivHttpClient(
        transport=httpx.MockTransport(handler),
        retry_sleep_seconds=0,
    )
    client = OaiPmhMetadataClient(
        http_client=http_client,
        min_request_interval_seconds=0,
    )

    page = client.fetch_list_records(from_date="2026-06-03", set_spec="cs:cs:AI")

    assert requested_urls == [
        "https://oaipmh.arxiv.org/oai?verb=ListRecords&metadataPrefix=arXiv&from=2026-06-03&set=cs%3Acs%3AAI"
    ]
    assert [paper.arxiv_id for paper in page.papers] == ["2606.00001"]
