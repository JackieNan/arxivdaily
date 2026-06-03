# arXiv Local Daily Phase 2 Live Crawler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested live crawler that discovers arXiv categories, fetches daily listing pages, persists all parsed daily events in one crawl run, and reports complete/partial crawl health.

**Architecture:** Keep live network behavior behind small injectable interfaces so tests use offline fixtures and fake transports. The crawler should discover categories from arXiv taxonomy HTML by default, but every orchestration function accepts explicit category lists for deterministic tests and manual limited runs. A daily crawl run records one `crawl_runs` row and one `crawl_run_sources` row per requested category, with failed sources making the run `partial`.

**Tech Stack:** Python 3.12+, stdlib `sqlite3`, httpx, BeautifulSoup4, pytest, FastAPI.

---

## File Structure

- Create `arxiv-local-daily/src/arxiv_local_daily/crawler/taxonomy.py`: parse arXiv category taxonomy pages into category IDs.
- Create `arxiv-local-daily/src/arxiv_local_daily/crawler/http.py`: small HTTP client wrapper with retries, timeout, and user agent.
- Create `arxiv-local-daily/src/arxiv_local_daily/crawler/live.py`: live crawl orchestration for category discovery and daily page fetching.
- Create `arxiv-local-daily/src/arxiv_local_daily/cli.py`: local command entrypoint for manual daily crawls.
- Modify `arxiv-local-daily/src/arxiv_local_daily/models.py`: add crawl source and crawl result models used by service/API boundaries.
- Modify `arxiv-local-daily/src/arxiv_local_daily/repositories.py`: add source failure/upsert helpers and run detail listing.
- Modify `arxiv-local-daily/src/arxiv_local_daily/services.py`: add multi-source daily crawl ingestion while preserving existing single-source ingestion.
- Modify `arxiv-local-daily/src/arxiv_local_daily/api.py`: add `POST /api/crawl/run` and richer crawl run status fields.
- Modify `arxiv-local-daily/pyproject.toml`: add console script `arxiv-local-daily`.
- Modify `arxiv-local-daily/README.md`: document live crawl command, API endpoint, and completeness semantics.
- Create `arxiv-local-daily/tests/fixtures/category_taxonomy.html`: offline taxonomy fixture.
- Create `arxiv-local-daily/tests/test_taxonomy.py`: taxonomy parser tests.
- Create `arxiv-local-daily/tests/test_http.py`: retry/client tests with fake transport.
- Create `arxiv-local-daily/tests/test_live_crawl.py`: multi-category crawl orchestration tests.
- Modify `arxiv-local-daily/tests/test_api.py`: crawl trigger endpoint tests.

---

### Task 1: Category Taxonomy Parser

**Files:**
- Create: `arxiv-local-daily/src/arxiv_local_daily/crawler/taxonomy.py`
- Create: `arxiv-local-daily/tests/fixtures/category_taxonomy.html`
- Create: `arxiv-local-daily/tests/test_taxonomy.py`

- [ ] **Step 1: Write taxonomy fixture**

Create `tests/fixtures/category_taxonomy.html` with representative category headings:

```html
<html>
  <body>
    <div id="category_taxonomy_list">
      <h4>cs.AI (Artificial Intelligence)</h4>
      <h4>cs.LG (Machine Learning)</h4>
      <h4>hep-th (High Energy Physics - Theory)</h4>
      <h4>cond-mat.mtrl-sci (Materials Science)</h4>
      <h4>Not a category heading</h4>
    </div>
  </body>
</html>
```

- [ ] **Step 2: Write failing parser tests**

Create `tests/test_taxonomy.py`:

```python
from pathlib import Path

from arxiv_local_daily.crawler.taxonomy import parse_category_taxonomy


def test_parse_category_taxonomy_extracts_modern_and_legacy_categories():
    html = Path("tests/fixtures/category_taxonomy.html").read_text()

    categories = parse_category_taxonomy(html)

    assert categories == ["cond-mat.mtrl-sci", "cs.AI", "cs.LG", "hep-th"]


def test_parse_category_taxonomy_deduplicates_categories():
    html = "<h4>cs.AI (Artificial Intelligence)</h4><h4>cs.AI (Artificial Intelligence)</h4>"

    categories = parse_category_taxonomy(html)

    assert categories == ["cs.AI"]
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/test_taxonomy.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `arxiv_local_daily.crawler.taxonomy`.

- [ ] **Step 4: Implement taxonomy parser**

Create `src/arxiv_local_daily/crawler/taxonomy.py`:

```python
import re

from bs4 import BeautifulSoup

CATEGORY_HEADING_RE = re.compile(r"^([a-z]+(?:-[a-z]+)*(?:\.[A-Za-z0-9-]+)?)\s+\(")


def parse_category_taxonomy(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    categories: set[str] = set()
    for heading in soup.find_all(["h3", "h4", "li", "a"]):
        text = heading.get_text(" ", strip=True)
        match = CATEGORY_HEADING_RE.match(text)
        if match is not None:
            categories.add(match.group(1))
    return sorted(categories)
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
uv run pytest tests/test_taxonomy.py -v
uv run pytest -v
```

Commit:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/crawler/taxonomy.py arxiv-local-daily/tests/fixtures/category_taxonomy.html arxiv-local-daily/tests/test_taxonomy.py
git commit -m "feat: parse arxiv category taxonomy"
```

---

### Task 2: Retryable HTTP Fetcher

**Files:**
- Create: `arxiv-local-daily/src/arxiv_local_daily/crawler/http.py`
- Create: `arxiv-local-daily/tests/test_http.py`

- [ ] **Step 1: Write failing HTTP tests**

Create `tests/test_http.py`:

```python
import httpx

from arxiv_local_daily.crawler.http import ArxivHttpClient


def test_fetch_text_retries_transient_server_errors():
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(503, text="temporary")
        return httpx.Response(200, text="ok")

    client = ArxivHttpClient(
        transport=httpx.MockTransport(handler),
        retry_sleep_seconds=0,
    )

    response = client.fetch_text("https://arxiv.org/list/cs.AI/new")

    assert response.status_code == 200
    assert response.text == "ok"
    assert len(attempts) == 2


def test_fetch_text_sends_polite_user_agent():
    seen_user_agent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_user_agent.append(request.headers["User-Agent"])
        return httpx.Response(200, text="ok")

    client = ArxivHttpClient(
        transport=httpx.MockTransport(handler),
        retry_sleep_seconds=0,
    )

    client.fetch_text("https://arxiv.org/list/cs.AI/new")

    assert seen_user_agent == ["arxiv-local-daily/0.1"]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/test_http.py -v
```

Expected: FAIL with missing `arxiv_local_daily.crawler.http`.

- [ ] **Step 3: Implement HTTP client**

Create `src/arxiv_local_daily/crawler/http.py`:

```python
from dataclasses import dataclass
import time

import httpx


@dataclass(frozen=True)
class FetchResponse:
    url: str
    status_code: int
    text: str


class ArxivHttpClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        max_attempts: int = 3,
        retry_sleep_seconds: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.max_attempts = max_attempts
        self.retry_sleep_seconds = retry_sleep_seconds
        self.client = httpx.Client(
            timeout=timeout_seconds,
            transport=transport,
            headers={"User-Agent": "arxiv-local-daily/0.1"},
            follow_redirects=True,
        )

    def fetch_text(self, url: str) -> FetchResponse:
        last_response: httpx.Response | None = None
        for attempt in range(1, self.max_attempts + 1):
            response = self.client.get(url)
            last_response = response
            if response.status_code < 500:
                return FetchResponse(url=str(response.url), status_code=response.status_code, text=response.text)
            if attempt < self.max_attempts:
                time.sleep(self.retry_sleep_seconds)
        assert last_response is not None
        return FetchResponse(url=str(last_response.url), status_code=last_response.status_code, text=last_response.text)

    def close(self) -> None:
        self.client.close()
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/test_http.py -v
uv run pytest -v
```

Commit:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/crawler/http.py arxiv-local-daily/tests/test_http.py
git commit -m "feat: add retryable arxiv http client"
```

---

### Task 3: Multi-Source Daily Crawl Ingestion

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/models.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/repositories.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/services.py`
- Create: `arxiv-local-daily/tests/test_live_crawl.py`

- [ ] **Step 1: Write failing multi-source ingestion tests**

Create the first half of `tests/test_live_crawl.py`:

```python
from pathlib import Path

from arxiv_local_daily.models import CrawlSourceInput
from arxiv_local_daily.services import ingest_daily_crawl_sources


def test_ingest_daily_crawl_sources_records_complete_run(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    run_id = ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
        mode="all-categories",
        sources=[
            CrawlSourceInput(
                category="cs.AI",
                event_section="all",
                url="https://arxiv.org/list/cs.AI/new",
                status="complete",
                http_status=200,
                html=html,
            )
        ],
    )

    run = db.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    source = db.execute("SELECT * FROM crawl_run_sources WHERE run_id = ?", (run_id,)).fetchone()
    event_count = db.execute("SELECT COUNT(*) AS count FROM daily_events").fetchone()["count"]

    assert run["status"] == "complete"
    assert source["status"] == "complete"
    assert source["parsed_count"] == 3
    assert event_count == 3


def test_ingest_daily_crawl_sources_marks_run_partial_when_source_fails(db):
    run_id = ingest_daily_crawl_sources(
        db,
        date="2026-06-03",
        mode="all-categories",
        sources=[
            CrawlSourceInput(
                category="cs.AI",
                event_section="all",
                url="https://arxiv.org/list/cs.AI/new",
                status="failed",
                http_status=503,
                html=None,
                error="HTTP 503",
            )
        ],
    )

    run = db.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    source = db.execute("SELECT * FROM crawl_run_sources WHERE run_id = ?", (run_id,)).fetchone()

    assert run["status"] == "partial"
    assert source["status"] == "failed"
    assert source["parsed_count"] == 0
    assert source["error"] == "HTTP 503"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/test_live_crawl.py -v
```

Expected: FAIL because `CrawlSourceInput` and `ingest_daily_crawl_sources` do not exist.

- [ ] **Step 3: Add crawl source model**

Modify `src/arxiv_local_daily/models.py`:

```python
class CrawlSourceInput(BaseModel):
    category: str
    event_section: str = "all"
    url: str
    status: str
    http_status: int | None = None
    html: str | None = None
    error: str | None = None
    retry_count: int = 0
```

- [ ] **Step 4: Add ingestion service**

Modify `src/arxiv_local_daily/services.py`:

```python
from arxiv_local_daily.models import CrawlSourceInput


def ingest_daily_crawl_sources(
    connection: sqlite3.Connection,
    *,
    date: str,
    mode: str,
    sources: list[CrawlSourceInput],
) -> int:
    summary_counts: dict[str, int] = {}
    failed_count = 0
    with transaction(connection):
        crawl_repo = CrawlRepository(connection)
        paper_repo = PaperRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode=mode, status="running")
        for source in sources:
            parsed_count = 0
            if source.status == "complete" and source.html is not None:
                events = parse_daily_listing(
                    source.html,
                    listing_category=source.category,
                    source_url=source.url,
                )
                parsed_count = len(events)
                for event in events:
                    summary_counts[event.event_type] = summary_counts.get(event.event_type, 0) + 1
                    paper_repo.upsert_daily_event(date=date, event=event)
            else:
                failed_count += 1
            crawl_repo.record_source(
                run_id=run_id,
                category=source.category,
                event_section=source.event_section,
                url=source.url,
                status=source.status,
                http_status=source.http_status,
                parsed_count=parsed_count,
                error=source.error,
                retry_count=source.retry_count,
            )
        final_status = "complete" if failed_count == 0 else "partial"
        crawl_repo.finish_run(run_id, status=final_status, summary_counts=summary_counts)
        return run_id
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
uv run pytest tests/test_live_crawl.py -v
uv run pytest -v
```

Commit:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/models.py arxiv-local-daily/src/arxiv_local_daily/services.py arxiv-local-daily/tests/test_live_crawl.py
git commit -m "feat: ingest multi-source daily crawl runs"
```

---

### Task 4: Live Crawl Orchestrator

**Files:**
- Create: `arxiv-local-daily/src/arxiv_local_daily/crawler/live.py`
- Modify: `arxiv-local-daily/tests/test_live_crawl.py`

- [ ] **Step 1: Add failing orchestrator tests**

Append to `tests/test_live_crawl.py`:

```python
import httpx

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.crawler.live import build_daily_listing_url, run_live_daily_crawl


def test_build_daily_listing_url_encodes_category():
    assert build_daily_listing_url("https://arxiv.org", "cond-mat.mtrl-sci") == (
        "https://arxiv.org/list/cond-mat.mtrl-sci/new"
    )


def test_run_live_daily_crawl_fetches_each_requested_category(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=html)

    client = ArxivHttpClient(
        transport=httpx.MockTransport(handler),
        retry_sleep_seconds=0,
    )

    run_id = run_live_daily_crawl(
        db,
        date="2026-06-03",
        categories=["cs.AI", "cs.LG"],
        http_client=client,
    )

    source_rows = db.execute(
        "SELECT category, status, parsed_count FROM crawl_run_sources WHERE run_id = ? ORDER BY category",
        (run_id,),
    ).fetchall()

    assert requested_urls == [
        "https://arxiv.org/list/cs.AI/new",
        "https://arxiv.org/list/cs.LG/new",
    ]
    assert [(row["category"], row["status"], row["parsed_count"]) for row in source_rows] == [
        ("cs.AI", "complete", 3),
        ("cs.LG", "complete", 3),
    ]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/test_live_crawl.py -v
```

Expected: FAIL with missing `arxiv_local_daily.crawler.live`.

- [ ] **Step 3: Implement live orchestrator**

Create `src/arxiv_local_daily/crawler/live.py`:

```python
import sqlite3

from arxiv_local_daily.crawler.http import ArxivHttpClient
from arxiv_local_daily.models import CrawlSourceInput
from arxiv_local_daily.services import ingest_daily_crawl_sources


def build_daily_listing_url(base_url: str, category: str) -> str:
    return f"{base_url.rstrip('/')}/list/{category}/new"


def run_live_daily_crawl(
    connection: sqlite3.Connection,
    *,
    date: str,
    categories: list[str],
    http_client: ArxivHttpClient | None = None,
    base_url: str = "https://arxiv.org",
) -> int:
    client = http_client or ArxivHttpClient()
    sources: list[CrawlSourceInput] = []
    for category in categories:
        url = build_daily_listing_url(base_url, category)
        response = client.fetch_text(url)
        if response.status_code == 200:
            sources.append(
                CrawlSourceInput(
                    category=category,
                    url=url,
                    status="complete",
                    http_status=response.status_code,
                    html=response.text,
                )
            )
        else:
            sources.append(
                CrawlSourceInput(
                    category=category,
                    url=url,
                    status="failed",
                    http_status=response.status_code,
                    html=None,
                    error=f"HTTP {response.status_code}",
                )
            )
    return ingest_daily_crawl_sources(connection, date=date, mode="all-categories", sources=sources)
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/test_live_crawl.py -v
uv run pytest -v
```

Commit:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/crawler/live.py arxiv-local-daily/tests/test_live_crawl.py
git commit -m "feat: run live category crawls"
```

---

### Task 5: API Crawl Trigger and Run Details

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/repositories.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/api.py`
- Modify: `arxiv-local-daily/tests/test_api.py`

- [ ] **Step 1: Write failing API test**

Append to `tests/test_api.py`:

```python
def test_get_crawl_runs_includes_source_details(tmp_path):
    client = _client_with_seed_data(tmp_path)

    response = client.get("/api/crawl/runs/2026-06-03")

    assert response.status_code == 200
    data = response.json()
    assert data["runs"][0]["source_count"] == 1
    assert data["runs"][0]["sources"][0]["category"] == "cs.AI"
    assert data["runs"][0]["sources"][0]["parsed_count"] == 3
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/test_api.py::test_get_crawl_runs_includes_source_details -v
```

Expected: FAIL with missing `sources` key.

- [ ] **Step 3: Add repository run detail method**

Add to `CrawlRepository` in `src/arxiv_local_daily/repositories.py`:

```python
    def list_runs_for_date(self, date: str) -> list[dict]:
        runs = self.connection.execute(
            """
            SELECT
                r.id,
                r.date,
                r.mode,
                r.status,
                r.started_at,
                r.finished_at,
                r.summary_counts_json,
                COUNT(s.id) AS source_count
            FROM crawl_runs r
            LEFT JOIN crawl_run_sources s ON s.run_id = r.id
            WHERE r.date = ?
            GROUP BY r.id
            ORDER BY r.id DESC
            """,
            (date,),
        ).fetchall()
        results: list[dict] = []
        for run in runs:
            sources = self.connection.execute(
                """
                SELECT category, event_section, url, status, http_status, parsed_count, error, retry_count
                FROM crawl_run_sources
                WHERE run_id = ?
                ORDER BY category, url
                """,
                (run["id"],),
            ).fetchall()
            item = dict(run)
            item["sources"] = [dict(source) for source in sources]
            results.append(item)
        return results
```

- [ ] **Step 4: Update API endpoint to use repository method**

Modify `list_crawl_runs` in `src/arxiv_local_daily/api.py`:

```python
    @app.get("/api/crawl/runs/{date}")
    def list_crawl_runs(date: str):
        connection = get_connection()
        try:
            repo = CrawlRepository(connection)
            return {"runs": repo.list_runs_for_date(date)}
        finally:
            connection.close()
```

Also import `CrawlRepository`.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
uv run pytest tests/test_api.py -v
uv run pytest -v
```

Commit:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/repositories.py arxiv-local-daily/src/arxiv_local_daily/api.py arxiv-local-daily/tests/test_api.py
git commit -m "feat: expose crawl source details"
```

---

### Task 6: CLI Manual Crawl

**Files:**
- Create: `arxiv-local-daily/src/arxiv_local_daily/cli.py`
- Modify: `arxiv-local-daily/pyproject.toml`
- Create: `arxiv-local-daily/tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_cli.py`:

```python
from arxiv_local_daily.cli import parse_args


def test_parse_args_accepts_date_and_category():
    args = parse_args(["crawl", "--date", "2026-06-03", "--category", "cs.AI"])

    assert args.command == "crawl"
    assert args.date == "2026-06-03"
    assert args.category == ["cs.AI"]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/test_cli.py -v
```

Expected: FAIL with missing `arxiv_local_daily.cli`.

- [ ] **Step 3: Implement CLI parser and command**

Create `src/arxiv_local_daily/cli.py`:

```python
import argparse

from arxiv_local_daily.config import default_settings
from arxiv_local_daily.crawler.live import run_live_daily_crawl
from arxiv_local_daily.db import connect, initialize_schema


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="arxiv-local-daily")
    subparsers = parser.add_subparsers(dest="command", required=True)
    crawl = subparsers.add_parser("crawl")
    crawl.add_argument("--date", required=True)
    crawl.add_argument("--category", action="append", required=True)
    crawl.add_argument("--db", default=str(default_settings().database_path))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "crawl":
        connection = connect(args.db)
        initialize_schema(connection)
        try:
            run_id = run_live_daily_crawl(connection, date=args.date, categories=args.category)
        finally:
            connection.close()
        print(f"crawl_run_id={run_id}")
        return 0
    raise ValueError(f"unknown command: {args.command}")
```

Modify `pyproject.toml`:

```toml
[project.scripts]
arxiv-local-daily = "arxiv_local_daily.cli:main"
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/test_cli.py -v
uv run pytest -v
```

Commit:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/cli.py arxiv-local-daily/pyproject.toml arxiv-local-daily/tests/test_cli.py
git commit -m "feat: add manual crawl cli"
```

---

### Task 7: Documentation and Final Verification

**Files:**
- Modify: `arxiv-local-daily/README.md`

- [ ] **Step 1: Update README**

Add:

```markdown
## Run Limited Live Crawl

```bash
PYTHONPATH=src uv run arxiv-local-daily crawl --date 2026-06-03 --category cs.AI
```

The CLI persists one crawl run and one source row per requested category. A run is `complete` when all requested category pages fetch successfully; it is `partial` when one or more requested sources fail.
```

- [ ] **Step 2: Final verification**

Run:

```bash
uv run pytest -v
PYTHONPATH=src uv run python -c "from arxiv_local_daily.crawler.live import build_daily_listing_url; print(build_daily_listing_url('https://arxiv.org', 'cs.AI'))"
```

Expected:

```text
19+ passed
https://arxiv.org/list/cs.AI/new
```

- [ ] **Step 3: Commit**

Run:

```bash
git add arxiv-local-daily/README.md
git commit -m "docs: document live crawl workflow"
```

