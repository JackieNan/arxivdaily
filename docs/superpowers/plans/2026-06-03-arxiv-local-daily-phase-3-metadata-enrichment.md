# arXiv Local Daily Phase 3 Metadata Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich crawled arXiv IDs with title, authors, abstract, categories, URLs, timestamps, and version metadata from the official arXiv API.

**Architecture:** Keep Atom parsing, API fetching, persistence, and orchestration separate. Tests must use Atom XML fixtures and fake transports; live arXiv API checks are smoke tests only. Metadata enrichment must not weaken crawl completeness: daily events stay persisted even when metadata fetches fail or return missing IDs.

**Tech Stack:** Python 3.12+, stdlib `xml.etree.ElementTree`, stdlib `urllib.parse`, stdlib `sqlite3`, httpx, Pydantic, pytest, FastAPI.

---

## File Structure

- Create `arxiv-local-daily/src/arxiv_local_daily/crawler/metadata.py`: arXiv Atom parser, ID/version helpers, metadata client.
- Modify `arxiv-local-daily/src/arxiv_local_daily/models.py`: add `PaperMetadata` and `PaperVersionInput`.
- Modify `arxiv-local-daily/src/arxiv_local_daily/repositories.py`: add metadata upsert and pending-ID query methods.
- Modify `arxiv-local-daily/src/arxiv_local_daily/services.py`: add date/ID metadata enrichment service.
- Modify `arxiv-local-daily/src/arxiv_local_daily/api.py`: add `POST /api/metadata/run` with injectable runner.
- Modify `arxiv-local-daily/src/arxiv_local_daily/cli.py`: add `metadata --date`.
- Modify `arxiv-local-daily/README.md`: document metadata enrichment.
- Modify `docs/phases.md`: mark Phase 3 complete after implementation.
- Create `arxiv-local-daily/tests/fixtures/arxiv_api_feed.xml`: offline Atom fixture.
- Create `arxiv-local-daily/tests/test_metadata_parser.py`: parser and URL tests.
- Create `arxiv-local-daily/tests/test_metadata_enrichment.py`: repository/service tests.
- Modify `arxiv-local-daily/tests/test_api.py`: metadata trigger API test.
- Modify `arxiv-local-daily/tests/test_cli.py`: metadata CLI parsing test.

---

### Task 1: Atom Metadata Parser

**Files:**
- Create: `arxiv-local-daily/src/arxiv_local_daily/crawler/metadata.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/models.py`
- Create: `arxiv-local-daily/tests/fixtures/arxiv_api_feed.xml`
- Create: `arxiv-local-daily/tests/test_metadata_parser.py`

- [ ] **Step 1: Write Atom fixture**

Create `tests/fixtures/arxiv_api_feed.xml` with two representative entries:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2606.00001v2</id>
    <updated>2026-06-03T12:34:56Z</updated>
    <published>2026-06-02T00:00:00Z</published>
    <title> First paper title </title>
    <summary> First abstract with
      whitespace. </summary>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
    <arxiv:primary_category term="cs.AI"/>
    <category term="cs.AI"/>
    <category term="cs.LG"/>
    <link href="http://arxiv.org/abs/2606.00001v2" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2606.00001v2" rel="related" type="application/pdf"/>
    <arxiv:comment>12 pages</arxiv:comment>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/hep-th/9901001v1</id>
    <updated>1999-01-02T00:00:00Z</updated>
    <published>1999-01-01T00:00:00Z</published>
    <title>Legacy title</title>
    <summary>Legacy abstract.</summary>
    <author><name>Legacy Author</name></author>
    <arxiv:primary_category term="hep-th"/>
    <category term="hep-th"/>
    <link href="http://arxiv.org/abs/hep-th/9901001v1" rel="alternate" type="text/html"/>
  </entry>
</feed>
```

- [ ] **Step 2: Write failing parser tests**

Create `tests/test_metadata_parser.py`:

```python
from pathlib import Path

from arxiv_local_daily.crawler.metadata import (
    build_arxiv_api_query_url,
    extract_arxiv_id_and_version,
    parse_arxiv_atom_feed,
)


def test_extract_arxiv_id_and_version_handles_modern_and_legacy_ids():
    assert extract_arxiv_id_and_version("http://arxiv.org/abs/2606.00001v2") == ("2606.00001", "v2")
    assert extract_arxiv_id_and_version("http://arxiv.org/abs/hep-th/9901001v1") == ("hep-th/9901001", "v1")


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
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_metadata_parser.py -v
```

Expected: FAIL because `arxiv_local_daily.crawler.metadata` does not exist.

- [ ] **Step 4: Add metadata models**

Modify `src/arxiv_local_daily/models.py`:

```python
class PaperVersionInput(BaseModel):
    version: str
    updated_at: str | None = None
    comment: str | None = None
    source_hash: str | None = None


class PaperMetadata(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    primary_category: str | None = None
    categories: list[str] = Field(default_factory=list)
    abs_url: str | None = None
    pdf_url: str | None = None
    published_at: str | None = None
    updated_at: str | None = None
    versions: list[PaperVersionInput] = Field(default_factory=list)
```

- [ ] **Step 5: Implement parser and URL builder**

Create `src/arxiv_local_daily/crawler/metadata.py`:

```python
import re
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from arxiv_local_daily.models import PaperMetadata, PaperVersionInput

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
VERSION_RE = re.compile(r"(v\\d+)$")


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


def build_arxiv_api_query_url(ids: list[str], *, base_url: str = "https://export.arxiv.org/api/query") -> str:
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
        categories = [category.attrib["term"] for category in entry.findall(f"{ATOM}category") if "term" in category.attrib]
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
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
uv run pytest tests/test_metadata_parser.py -v
uv run pytest -v
```

Commit:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/crawler/metadata.py arxiv-local-daily/src/arxiv_local_daily/models.py arxiv-local-daily/tests/fixtures/arxiv_api_feed.xml arxiv-local-daily/tests/test_metadata_parser.py
git commit -m "feat: parse arxiv api metadata"
```

---

### Task 2: Metadata Fetch Client

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/crawler/metadata.py`
- Modify: `arxiv-local-daily/tests/test_metadata_parser.py`

- [ ] **Step 1: Add failing client test**

Append to `tests/test_metadata_parser.py`:

```python
import httpx

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.crawler.metadata import ArxivMetadataClient


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
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
uv run pytest tests/test_metadata_parser.py::test_metadata_client_fetches_and_parses_ids -v
```

Expected: FAIL because `ArxivMetadataClient` does not exist.

- [ ] **Step 3: Implement metadata client**

Add to `src/arxiv_local_daily/crawler/metadata.py`:

```python
from arxiv_local_daily.crawler.http import ArxivHttpClient


class ArxivMetadataClient:
    def __init__(self, *, http_client: ArxivHttpClient | None = None):
        self.http_client = http_client or ArxivHttpClient()

    def fetch_by_ids(self, ids: list[str]) -> list[PaperMetadata]:
        if not ids:
            return []
        response = self.http_client.fetch_text(build_arxiv_api_query_url(ids))
        if response.status_code != 200:
            raise ValueError(f"arXiv API metadata fetch failed: HTTP {response.status_code}")
        return parse_arxiv_atom_feed(response.text)
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/test_metadata_parser.py -v
uv run pytest -v
```

Commit:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/crawler/metadata.py arxiv-local-daily/tests/test_metadata_parser.py
git commit -m "feat: fetch arxiv metadata by id"
```

---

### Task 3: Persist Metadata

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/repositories.py`
- Create: `arxiv-local-daily/tests/test_metadata_enrichment.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/test_metadata_enrichment.py`:

```python
from arxiv_local_daily.models import PaperMetadata, PaperVersionInput
from arxiv_local_daily.repositories import PaperRepository


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
        versions=[PaperVersionInput(version="v1", updated_at="2026-06-03T00:00:00Z", comment="12 pages")],
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
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
uv run pytest tests/test_metadata_enrichment.py -v
```

Expected: FAIL because `PaperRepository.upsert_metadata` does not exist.

- [ ] **Step 3: Implement metadata repository methods**

Add to `PaperRepository` in `src/arxiv_local_daily/repositories.py`:

```python
    def upsert_metadata(self, metadata: PaperMetadata) -> None:
        self.connection.execute(
            """
            INSERT INTO papers
                (arxiv_id, title, abstract, authors_json, primary_category, categories_json, abs_url, pdf_url,
                 published_at, updated_at, metadata_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'complete')
            ON CONFLICT(arxiv_id) DO UPDATE SET
                title = excluded.title,
                abstract = excluded.abstract,
                authors_json = excluded.authors_json,
                primary_category = excluded.primary_category,
                categories_json = excluded.categories_json,
                abs_url = excluded.abs_url,
                pdf_url = excluded.pdf_url,
                published_at = excluded.published_at,
                updated_at = excluded.updated_at,
                metadata_status = 'complete',
                updated_row_at = CURRENT_TIMESTAMP
            """,
            (
                metadata.arxiv_id,
                metadata.title,
                metadata.abstract,
                json.dumps(metadata.authors, ensure_ascii=False),
                metadata.primary_category,
                json.dumps(metadata.categories, ensure_ascii=False),
                metadata.abs_url,
                metadata.pdf_url,
                metadata.published_at,
                metadata.updated_at,
            ),
        )
        for version in metadata.versions:
            self.connection.execute(
                """
                INSERT INTO paper_versions (arxiv_id, version, updated_at, comment, source_hash)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(arxiv_id, version) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    comment = excluded.comment,
                    source_hash = excluded.source_hash
                """,
                (metadata.arxiv_id, version.version, version.updated_at, version.comment, version.source_hash),
            )

    def mark_metadata_status(self, arxiv_id: str, status: str) -> None:
        self.ensure_pending_paper(arxiv_id)
        self.connection.execute(
            "UPDATE papers SET metadata_status = ?, updated_row_at = CURRENT_TIMESTAMP WHERE arxiv_id = ?",
            (status, arxiv_id),
        )

    def list_metadata_pending_ids_for_date(self, date: str, *, limit: int) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT DISTINCT p.arxiv_id
            FROM papers p
            JOIN daily_events e ON e.arxiv_id = p.arxiv_id
            WHERE e.date = ? AND p.metadata_status != 'complete'
            ORDER BY p.arxiv_id
            LIMIT ?
            """,
            (date, limit),
        ).fetchall()
        return [row["arxiv_id"] for row in rows]
```

Also import `PaperMetadata`.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/test_metadata_enrichment.py -v
uv run pytest -v
```

Commit:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/repositories.py arxiv-local-daily/tests/test_metadata_enrichment.py
git commit -m "feat: persist arxiv metadata"
```

---

### Task 4: Metadata Enrichment Service

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/services.py`
- Modify: `arxiv-local-daily/tests/test_metadata_enrichment.py`

- [ ] **Step 1: Add failing service test**

Append to `tests/test_metadata_enrichment.py`:

```python
from pathlib import Path

from arxiv_local_daily.crawler.metadata import parse_arxiv_atom_feed
from arxiv_local_daily.services import enrich_metadata_for_date, ingest_daily_listing_html


class FakeMetadataClient:
    def __init__(self, papers):
        self.papers = papers
        self.seen_ids = []

    def fetch_by_ids(self, ids):
        self.seen_ids.append(ids)
        return self.papers


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
    assert result == {"requested": 2, "updated": 1, "missing": 1, "failed": 0}
    assert paper["metadata_status"] == "complete"
    assert paper["title"] == "First paper title"
    assert missing["metadata_status"] == "failed"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
uv run pytest tests/test_metadata_enrichment.py::test_enrich_metadata_for_date_updates_pending_daily_papers -v
```

Expected: FAIL because `enrich_metadata_for_date` does not exist.

- [ ] **Step 3: Implement service**

Add to `src/arxiv_local_daily/services.py`:

```python
from arxiv_local_daily.crawler.metadata import ArxivMetadataClient


def enrich_metadata_for_date(
    connection: sqlite3.Connection,
    *,
    date: str,
    metadata_client: ArxivMetadataClient | None = None,
    limit: int = 100,
) -> dict[str, int]:
    client = metadata_client or ArxivMetadataClient()
    repo = PaperRepository(connection)
    ids = repo.list_metadata_pending_ids_for_date(date, limit=limit)
    if not ids:
        return {"requested": 0, "updated": 0, "missing": 0, "failed": 0}
    try:
        papers = client.fetch_by_ids(ids)
    except Exception:
        with transaction(connection):
            for arxiv_id in ids:
                repo.mark_metadata_status(arxiv_id, "failed")
        return {"requested": len(ids), "updated": 0, "missing": 0, "failed": len(ids)}
    returned_by_id = {paper.arxiv_id: paper for paper in papers}
    with transaction(connection):
        for paper in papers:
            repo.upsert_metadata(paper)
        missing_ids = sorted(set(ids) - set(returned_by_id))
        for arxiv_id in missing_ids:
            repo.mark_metadata_status(arxiv_id, "failed")
    return {"requested": len(ids), "updated": len(papers), "missing": len(missing_ids), "failed": 0}
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/test_metadata_enrichment.py -v
uv run pytest -v
```

Commit:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/services.py arxiv-local-daily/tests/test_metadata_enrichment.py
git commit -m "feat: enrich daily paper metadata"
```

---

### Task 5: API and CLI Metadata Triggers

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/api.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/cli.py`
- Modify: `arxiv-local-daily/tests/test_api.py`
- Modify: `arxiv-local-daily/tests/test_cli.py`

- [ ] **Step 1: Add failing API and CLI tests**

Append to `tests/test_api.py`:

```python
def test_post_metadata_run_uses_injected_runner(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[tuple[str, int]] = []

    def fake_metadata_runner(connection, *, date: str, limit: int):
        calls.append((date, limit))
        return {"requested": 2, "updated": 2, "missing": 0, "failed": 0}

    client = TestClient(create_app(database_path=db_path, metadata_runner=fake_metadata_runner))

    response = client.post("/api/metadata/run", json={"date": "2026-06-03", "limit": 2})

    assert response.status_code == 200
    assert response.json() == {"requested": 2, "updated": 2, "missing": 0, "failed": 0}
    assert calls == [("2026-06-03", 2)]
```

Append to `tests/test_cli.py`:

```python
def test_parse_args_accepts_metadata_date_and_limit():
    args = parse_args(["metadata", "--date", "2026-06-03", "--limit", "25"])

    assert args.command == "metadata"
    assert args.date == "2026-06-03"
    assert args.limit == 25
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_api.py::test_post_metadata_run_uses_injected_runner tests/test_cli.py::test_parse_args_accepts_metadata_date_and_limit -v
```

Expected: FAIL because API and CLI metadata commands do not exist.

- [ ] **Step 3: Implement API and CLI trigger**

Modify `create_app` in `src/arxiv_local_daily/api.py` to accept `metadata_runner=enrich_metadata_for_date`.

Add request model:

```python
class MetadataRunRequest(BaseModel):
    date: str
    limit: int = 100
```

Add endpoint:

```python
    @app.post("/api/metadata/run")
    def run_metadata(request: MetadataRunRequest):
        connection = get_connection()
        try:
            return metadata_runner(connection, date=request.date, limit=request.limit)
        finally:
            connection.close()
```

Modify `src/arxiv_local_daily/cli.py`:

```python
from arxiv_local_daily.services import enrich_metadata_for_date

metadata = subparsers.add_parser("metadata")
metadata.add_argument("--date", required=True)
metadata.add_argument("--limit", type=int, default=100)
metadata.add_argument("--db", default=str(default_settings().database_path))
```

Handle command:

```python
    if args.command == "metadata":
        connection = connect(args.db)
        initialize_schema(connection)
        try:
            result = enrich_metadata_for_date(connection, date=args.date, limit=args.limit)
        finally:
            connection.close()
        print(result)
        return 0
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/test_api.py tests/test_cli.py -v
uv run pytest -v
```

Commit:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/api.py arxiv-local-daily/src/arxiv_local_daily/cli.py arxiv-local-daily/tests/test_api.py arxiv-local-daily/tests/test_cli.py
git commit -m "feat: expose metadata enrichment controls"
```

---

### Task 6: Documentation and Phase Log

**Files:**
- Modify: `arxiv-local-daily/README.md`
- Modify: `docs/phases.md`

- [ ] **Step 1: Update README**

Add:

```markdown
## Run Metadata Enrichment

```bash
uv run --with-editable . arxiv-local-daily metadata --date 2026-06-03 --limit 100
```

Metadata enrichment uses the official arXiv API `id_list` query for crawled paper IDs. Daily crawl events remain in the database even when metadata is missing or failed.
```

- [ ] **Step 2: Update phase log**

Mark Phase 3 as complete after implementation and include verification results.

- [ ] **Step 3: Final verification**

Run:

```bash
uv run pytest -v
PYTHONPATH=src uv run python -c "from arxiv_local_daily.crawler.metadata import build_arxiv_api_query_url; print(build_arxiv_api_query_url(['2606.00001']))"
```

Expected:

```text
35+ passed
https://export.arxiv.org/api/query?id_list=2606.00001&start=0&max_results=1
```

- [ ] **Step 4: Commit**

Run:

```bash
git add arxiv-local-daily/README.md docs/phases.md
git commit -m "docs: document metadata enrichment phase"
```

