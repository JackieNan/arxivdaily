from dataclasses import dataclass
import threading
import time
from collections.abc import Callable
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.models import PaperMetadata

OAI = "{http://www.openarchives.org/OAI/2.0/}"
ARXIV = "{http://arxiv.org/OAI/arXiv/}"


@dataclass(frozen=True)
class OaiListRecordsPage:
    papers: list[PaperMetadata]
    resumption_token: str | None = None
    complete_list_size: int | None = None


def build_oai_list_records_url(
    *,
    base_url: str = "https://oaipmh.arxiv.org/oai",
    metadata_prefix: str = "arXiv",
    from_date: str | None = None,
    until_date: str | None = None,
    set_spec: str | None = None,
    resumption_token: str | None = None,
) -> str:
    if resumption_token:
        params = {"verb": "ListRecords", "resumptionToken": resumption_token}
    else:
        params = {"verb": "ListRecords", "metadataPrefix": metadata_prefix}
        if from_date:
            params["from"] = from_date
        if until_date:
            params["until"] = until_date
        if set_spec:
            params["set"] = set_spec
    return f"{base_url}?{urlencode(params)}"


def parse_oai_list_records(xml: str) -> OaiListRecordsPage:
    root = ET.fromstring(xml)
    list_records = root.find(f"{OAI}ListRecords")
    if list_records is None:
        return OaiListRecordsPage(papers=[])

    papers: list[PaperMetadata] = []
    for record in list_records.findall(f"{OAI}record"):
        header = record.find(f"{OAI}header")
        if header is not None and header.attrib.get("status") == "deleted":
            continue
        metadata = record.find(f"{OAI}metadata/{ARXIV}arXiv")
        if metadata is None:
            continue
        paper = _parse_arxiv_metadata(metadata)
        if paper is not None:
            papers.append(paper)

    token_node = list_records.find(f"{OAI}resumptionToken")
    token = _text(token_node)
    complete_list_size = None
    if token_node is not None and token_node.attrib.get("completeListSize"):
        complete_list_size = int(token_node.attrib["completeListSize"])
    return OaiListRecordsPage(
        papers=papers,
        resumption_token=token or None,
        complete_list_size=complete_list_size,
    )


def _parse_arxiv_metadata(node: ET.Element) -> PaperMetadata | None:
    arxiv_id = _text(node.find(f"{ARXIV}id"))
    if arxiv_id is None:
        return None
    categories = (_text(node.find(f"{ARXIV}categories")) or "").split()
    created = _text(node.find(f"{ARXIV}created"))
    updated = _text(node.find(f"{ARXIV}updated")) or created
    return PaperMetadata(
        arxiv_id=arxiv_id,
        title=_text(node.find(f"{ARXIV}title")) or "",
        abstract=_text(node.find(f"{ARXIV}abstract")) or "",
        authors=_parse_authors(node),
        primary_category=categories[0] if categories else None,
        categories=categories,
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        published_at=created,
        updated_at=updated,
    )


def _parse_authors(node: ET.Element) -> list[str]:
    authors: list[str] = []
    for author in node.findall(f"{ARXIV}authors/{ARXIV}author"):
        parts = [
            _text(author.find(f"{ARXIV}forenames")),
            _text(author.find(f"{ARXIV}keyname")),
            _text(author.find(f"{ARXIV}suffix")),
        ]
        name = " ".join(part for part in parts if part)
        if name:
            authors.append(name)
    return authors


def _text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    return " ".join(element.text.split())


class OaiPmhMetadataClient:
    _rate_limit_lock = threading.Lock()
    _last_request_at_by_key: dict[str, float] = {}

    def __init__(
        self,
        *,
        http_client: ArxivHttpClient | None = None,
        base_url: str = "https://oaipmh.arxiv.org/oai",
        min_request_interval_seconds: float = 3.0,
        rate_limit_key: str = "arxiv-oai-pmh",
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.http_client = http_client or ArxivHttpClient()
        self.base_url = base_url
        self.min_request_interval_seconds = min_request_interval_seconds
        self.rate_limit_key = rate_limit_key
        self.clock = clock
        self.sleep = sleep

    def fetch_list_records(
        self,
        *,
        metadata_prefix: str = "arXiv",
        from_date: str | None = None,
        until_date: str | None = None,
        set_spec: str | None = None,
        resumption_token: str | None = None,
    ) -> OaiListRecordsPage:
        self._wait_for_rate_limit()
        response = self.http_client.fetch_text(
            build_oai_list_records_url(
                base_url=self.base_url,
                metadata_prefix=metadata_prefix,
                from_date=from_date,
                until_date=until_date,
                set_spec=set_spec,
                resumption_token=resumption_token,
            )
        )
        if response.status_code != 200:
            raise ValueError(f"OAI-PMH metadata fetch failed: HTTP {response.status_code}")
        return parse_oai_list_records(response.text)

    def _wait_for_rate_limit(self) -> None:
        if self.min_request_interval_seconds <= 0:
            return
        with self._rate_limit_lock:
            now = self.clock()
            last_request_at = self._last_request_at_by_key.get(self.rate_limit_key)
            if last_request_at is not None:
                wait_seconds = self.min_request_interval_seconds - (now - last_request_at)
                if wait_seconds > 0:
                    self.sleep(wait_seconds)
                    now = self.clock()
            self._last_request_at_by_key[self.rate_limit_key] = now
