import re
import threading
import time
from collections.abc import Callable
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.models import PaperMetadata, PaperVersionInput

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
VERSION_RE = re.compile(r"(v\d+)$")


def _text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    return " ".join(element.text.split())


def extract_arxiv_id_and_version(abs_url: str) -> tuple[str, str | None]:
    arxiv_id = abs_url.rsplit("/abs/", 1)[1]
    match = VERSION_RE.search(arxiv_id)
    version = match.group(1) if match else None
    if version is not None:
        arxiv_id = arxiv_id[: -len(version)]
    return arxiv_id, version


def build_arxiv_api_query_url(
    ids: list[str],
    *,
    base_url: str = "https://export.arxiv.org/api/query",
) -> str:
    params = urlencode({"id_list": ",".join(ids), "start": 0, "max_results": len(ids)})
    return f"{base_url}?{params}"


def parse_arxiv_atom_feed(xml: str) -> list[PaperMetadata]:
    root = ET.fromstring(xml)
    papers: list[PaperMetadata] = []
    for entry in root.findall(f"{ATOM}entry"):
        entry_id = _text(entry.find(f"{ATOM}id"))
        if entry_id is None:
            continue
        arxiv_id, version = extract_arxiv_id_and_version(entry_id)
        categories = [
            category.attrib["term"]
            for category in entry.findall(f"{ATOM}category")
            if "term" in category.attrib
        ]
        primary = entry.find(f"{ARXIV}primary_category")
        primary_category = primary.attrib.get("term") if primary is not None else None
        abs_url = None
        pdf_url = None
        for link in entry.findall(f"{ATOM}link"):
            if link.attrib.get("type") == "text/html":
                abs_url = link.attrib.get("href")
            if link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href")
        updated_at = _text(entry.find(f"{ATOM}updated"))
        papers.append(
            PaperMetadata(
                arxiv_id=arxiv_id,
                title=_text(entry.find(f"{ATOM}title")) or "",
                abstract=_text(entry.find(f"{ATOM}summary")) or "",
                authors=[
                    name
                    for author in entry.findall(f"{ATOM}author")
                    if (name := _text(author.find(f"{ATOM}name"))) is not None
                ],
                primary_category=primary_category,
                categories=categories,
                abs_url=abs_url,
                pdf_url=pdf_url,
                published_at=_text(entry.find(f"{ATOM}published")),
                updated_at=updated_at,
                versions=[
                    PaperVersionInput(
                        version=version,
                        updated_at=updated_at,
                        comment=_text(entry.find(f"{ARXIV}comment")),
                    )
                ]
                if version is not None
                else [],
            )
        )
    return papers


class ArxivMetadataClient:
    _rate_limit_lock = threading.Lock()
    _last_request_at_by_key: dict[str, float] = {}

    def __init__(
        self,
        *,
        http_client: ArxivHttpClient | None = None,
        min_request_interval_seconds: float = 3.0,
        rate_limit_key: str = "arxiv-api",
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.http_client = http_client or ArxivHttpClient()
        self.min_request_interval_seconds = min_request_interval_seconds
        self.rate_limit_key = rate_limit_key
        self.clock = clock
        self.sleep = sleep

    @classmethod
    def reset_rate_limit(cls, key: str) -> None:
        with cls._rate_limit_lock:
            cls._last_request_at_by_key.pop(key, None)

    def fetch_by_ids(self, ids: list[str]) -> list[PaperMetadata]:
        if not ids:
            return []
        self._wait_for_rate_limit()
        response = self.http_client.fetch_text(build_arxiv_api_query_url(ids))
        if response.status_code != 200:
            raise ValueError(f"arXiv API metadata fetch failed: HTTP {response.status_code}")
        return parse_arxiv_atom_feed(response.text)

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
