# arXiv Local Daily Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable vertical slice of `arxiv-local-daily`: project scaffold, SQLite schema, daily listing parser, event ingestion, summary template storage, and minimal FastAPI endpoints.

**Architecture:** This phase creates an independent Python app under `arxiv-local-daily/`. The app keeps domain models, database access, crawler parsing, ingestion services, and API routes in separate focused modules. All crawler behavior is testable offline with fixture HTML; live network fetching is deliberately deferred until the parser and persistence semantics are solid.

**Tech Stack:** Python 3.12+, uv, FastAPI, Pydantic, httpx, BeautifulSoup4, pytest, SQLite via stdlib `sqlite3`.

---

## File Structure

Create these files:

- `arxiv-local-daily/pyproject.toml`: package metadata, runtime dependencies, pytest config.
- `arxiv-local-daily/README.md`: local run/test instructions for phase 1.
- `arxiv-local-daily/src/arxiv_local_daily/__init__.py`: package marker.
- `arxiv-local-daily/src/arxiv_local_daily/config.py`: app settings and database path defaults.
- `arxiv-local-daily/src/arxiv_local_daily/db.py`: SQLite connection, schema creation, transaction helper.
- `arxiv-local-daily/src/arxiv_local_daily/models.py`: Pydantic/domain models for papers, events, crawl runs, templates.
- `arxiv-local-daily/src/arxiv_local_daily/crawler/__init__.py`: crawler package marker.
- `arxiv-local-daily/src/arxiv_local_daily/crawler/parser.py`: arXiv daily listing parser.
- `arxiv-local-daily/src/arxiv_local_daily/repositories.py`: database repositories for crawl runs, events, papers, templates.
- `arxiv-local-daily/src/arxiv_local_daily/services.py`: ingestion service that ties parser output to persistence.
- `arxiv-local-daily/src/arxiv_local_daily/api.py`: FastAPI app and phase 1 endpoints.
- `arxiv-local-daily/tests/conftest.py`: temporary database fixture.
- `arxiv-local-daily/tests/fixtures/list_cs_ai_new.html`: offline arXiv-like daily listing fixture.
- `arxiv-local-daily/tests/test_db.py`: schema and uniqueness tests.
- `arxiv-local-daily/tests/test_parser.py`: listing parser tests.
- `arxiv-local-daily/tests/test_ingestion.py`: event ingestion and rerun tests.
- `arxiv-local-daily/tests/test_templates.py`: summary template tests.
- `arxiv-local-daily/tests/test_api.py`: FastAPI endpoint tests.

Do not modify the two reference projects in this phase.

---

### Task 1: Project Scaffold

**Files:**
- Create: `arxiv-local-daily/pyproject.toml`
- Create: `arxiv-local-daily/README.md`
- Create: `arxiv-local-daily/src/arxiv_local_daily/__init__.py`
- Create: `arxiv-local-daily/src/arxiv_local_daily/config.py`
- Create: `arxiv-local-daily/tests/test_project_import.py`

- [ ] **Step 1: Write the failing import test**

Create `arxiv-local-daily/tests/test_project_import.py`:

```python
def test_package_imports():
    import arxiv_local_daily

    assert arxiv_local_daily.__version__ == "0.1.0"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_project_import.py -v
```

Expected: FAIL because `arxiv_local_daily` does not exist.

- [ ] **Step 3: Create package scaffold**

Create `arxiv-local-daily/pyproject.toml`:

```toml
[project]
name = "arxiv-local-daily"
version = "0.1.0"
description = "Local-first arXiv daily crawler, database, AI summary, and discussion app"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "beautifulsoup4>=4.12.3",
    "fastapi>=0.115.0",
    "httpx>=0.27.0",
    "pydantic>=2.8.0",
    "uvicorn>=0.30.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Create `arxiv-local-daily/README.md`:

```markdown
# arxiv-local-daily

Local-first arXiv daily crawler, SQLite database, AI summary, search, and discussion app.

## Phase 1

Phase 1 provides:

- offline-tested arXiv daily listing parsing
- SQLite schema and repositories
- daily event ingestion
- summary template persistence
- minimal FastAPI endpoints

## Run Tests

```bash
uv run pytest
```

## Run API

```bash
uv run uvicorn arxiv_local_daily.api:create_app --factory --reload
```
```

Create `arxiv-local-daily/src/arxiv_local_daily/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `arxiv-local-daily/src/arxiv_local_daily/config.py`:

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path("data/arxiv-local-daily.sqlite3")


def default_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_project_import.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add arxiv-local-daily/pyproject.toml arxiv-local-daily/README.md arxiv-local-daily/src/arxiv_local_daily/__init__.py arxiv-local-daily/src/arxiv_local_daily/config.py arxiv-local-daily/tests/test_project_import.py
git commit -m "feat: scaffold arxiv local daily app"
```

---

### Task 2: SQLite Schema

**Files:**
- Create: `arxiv-local-daily/src/arxiv_local_daily/db.py`
- Create: `arxiv-local-daily/tests/conftest.py`
- Create: `arxiv-local-daily/tests/test_db.py`

- [ ] **Step 1: Write failing schema tests**

Create `arxiv-local-daily/tests/conftest.py`:

```python
from collections.abc import Iterator
from pathlib import Path

import pytest

from arxiv_local_daily.db import connect, initialize_schema


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.sqlite3"


@pytest.fixture
def db(db_path: Path) -> Iterator:
    connection = connect(db_path)
    initialize_schema(connection)
    try:
        yield connection
    finally:
        connection.close()
```

Create `arxiv-local-daily/tests/test_db.py`:

```python
def test_schema_creates_core_tables(db):
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    table_names = {row["name"] for row in rows}

    assert {
        "ai_jobs",
        "crawl_run_sources",
        "crawl_runs",
        "daily_events",
        "papers",
        "summary_templates",
        "summaries",
    }.issubset(table_names)


def test_daily_events_are_unique_per_date_id_type_and_listing_category(db):
    db.execute(
        """
        INSERT INTO papers (arxiv_id, metadata_status)
        VALUES (?, ?)
        """,
        ("2606.00001", "pending"),
    )
    db.execute(
        """
        INSERT INTO daily_events
            (date, arxiv_id, event_type, listing_category, seen_source_url)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("2026-06-03", "2606.00001", "new", "cs.AI", "https://arxiv.org/list/cs.AI/new"),
    )

    try:
        db.execute(
            """
            INSERT INTO daily_events
                (date, arxiv_id, event_type, listing_category, seen_source_url)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("2026-06-03", "2606.00001", "new", "cs.AI", "https://arxiv.org/list/cs.AI/new"),
        )
    except Exception as exc:
        assert "UNIQUE" in str(exc)
    else:
        raise AssertionError("duplicate daily event insert should fail")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_db.py -v
```

Expected: FAIL because `arxiv_local_daily.db` is missing.

- [ ] **Step 3: Implement SQLite connection and schema**

Create `arxiv-local-daily/src/arxiv_local_daily/db.py`:

```python
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS papers (
            arxiv_id TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            authors_json TEXT,
            primary_category TEXT,
            categories_json TEXT,
            abs_url TEXT,
            pdf_url TEXT,
            published_at TEXT,
            updated_at TEXT,
            metadata_status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_row_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS paper_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arxiv_id TEXT NOT NULL REFERENCES papers(arxiv_id) ON DELETE CASCADE,
            version TEXT NOT NULL,
            updated_at TEXT,
            comment TEXT,
            source_hash TEXT,
            UNIQUE (arxiv_id, version)
        );

        CREATE TABLE IF NOT EXISTS crawl_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            summary_counts_json TEXT NOT NULL DEFAULT '{}',
            error_counts_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS crawl_run_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
            category TEXT NOT NULL,
            event_section TEXT NOT NULL,
            url TEXT NOT NULL,
            status TEXT NOT NULL,
            http_status INTEGER,
            parsed_count INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            UNIQUE (run_id, category, event_section, url)
        );

        CREATE TABLE IF NOT EXISTS daily_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            arxiv_id TEXT NOT NULL REFERENCES papers(arxiv_id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            listing_category TEXT NOT NULL,
            primary_category TEXT,
            seen_source_url TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (date, arxiv_id, event_type, listing_category)
        );

        CREATE TABLE IF NOT EXISTS summary_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            language TEXT NOT NULL,
            version INTEGER NOT NULL,
            fields_json TEXT NOT NULL,
            system_prompt TEXT NOT NULL,
            input_scope TEXT NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (name, version)
        );

        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arxiv_id TEXT NOT NULL REFERENCES papers(arxiv_id) ON DELETE CASCADE,
            template_id INTEGER NOT NULL REFERENCES summary_templates(id),
            template_version INTEGER NOT NULL,
            model TEXT NOT NULL,
            language TEXT NOT NULL,
            input_scope TEXT NOT NULL,
            content_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (arxiv_id, template_id, template_version, model, input_scope)
        );

        CREATE TABLE IF NOT EXISTS ai_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type TEXT NOT NULL,
            arxiv_id TEXT REFERENCES papers(arxiv_id) ON DELETE CASCADE,
            status TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 100,
            attempts INTEGER NOT NULL DEFAULT 0,
            next_run_at TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    connection.commit()
```

- [ ] **Step 4: Run schema tests to verify they pass**

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_db.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/db.py arxiv-local-daily/tests/conftest.py arxiv-local-daily/tests/test_db.py
git commit -m "feat: add sqlite schema"
```

---

### Task 3: arXiv Daily Listing Parser

**Files:**
- Create: `arxiv-local-daily/src/arxiv_local_daily/models.py`
- Create: `arxiv-local-daily/src/arxiv_local_daily/crawler/__init__.py`
- Create: `arxiv-local-daily/src/arxiv_local_daily/crawler/parser.py`
- Create: `arxiv-local-daily/tests/fixtures/list_cs_ai_new.html`
- Create: `arxiv-local-daily/tests/test_parser.py`

- [ ] **Step 1: Write failing parser fixture and tests**

Create `arxiv-local-daily/tests/fixtures/list_cs_ai_new.html`:

```html
<html>
  <body>
    <div id="dlpage">
      <h3>New submissions for Wed, 3 Jun 2026</h3>
      <dl>
        <dt>
          <a name="item1"></a>
          <span class="list-identifier"><a title="Abstract" href="/abs/2606.00001">arXiv:2606.00001</a></span>
        </dt>
        <dd>
          <div class="meta">
            <div class="list-title mathjax">Title: First AI Paper</div>
            <div class="list-subjects">
              <span class="primary-subject">Artificial Intelligence (cs.AI)</span>
            </div>
          </div>
        </dd>
      </dl>
      <h3>Cross-lists for Wed, 3 Jun 2026</h3>
      <dl>
        <dt>
          <a name="item2"></a>
          <span class="list-identifier"><a title="Abstract" href="/abs/2606.00002">arXiv:2606.00002</a></span>
        </dt>
        <dd>
          <div class="meta">
            <div class="list-title mathjax">Title: Cross Listed Paper</div>
            <div class="list-subjects">
              <span class="primary-subject">Machine Learning (cs.LG)</span>, Artificial Intelligence (cs.AI)
            </div>
          </div>
        </dd>
      </dl>
      <h3>Replacements for Wed, 3 Jun 2026</h3>
      <dl>
        <dt>
          <a name="item3"></a>
          <span class="list-identifier"><a title="Abstract" href="/abs/2606.00003">arXiv:2606.00003</a></span>
        </dt>
        <dd>
          <div class="meta">
            <div class="list-title mathjax">Title: Replacement Paper</div>
            <div class="list-subjects">
              <span class="primary-subject">Artificial Intelligence (cs.AI)</span>
            </div>
          </div>
        </dd>
      </dl>
    </div>
  </body>
</html>
```

Create `arxiv-local-daily/tests/test_parser.py`:

```python
from pathlib import Path

from arxiv_local_daily.crawler.parser import parse_daily_listing


def test_parse_daily_listing_extracts_all_event_types():
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    events = parse_daily_listing(
        html,
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
    )

    assert [(event.arxiv_id, event.event_type) for event in events] == [
        ("2606.00001", "new"),
        ("2606.00002", "cross-list"),
        ("2606.00003", "replacement"),
    ]


def test_parse_daily_listing_extracts_primary_category():
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    events = parse_daily_listing(
        html,
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
    )

    assert events[0].primary_category == "cs.AI"
    assert events[1].primary_category == "cs.LG"
```

- [ ] **Step 2: Run parser tests to verify they fail**

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_parser.py -v
```

Expected: FAIL because parser module is missing.

- [ ] **Step 3: Implement parser models and parser**

Create `arxiv-local-daily/src/arxiv_local_daily/models.py`:

```python
from pydantic import BaseModel, Field


class ParsedDailyEvent(BaseModel):
    arxiv_id: str
    event_type: str
    listing_category: str
    primary_category: str | None = None
    source_url: str


class CrawlSourceResult(BaseModel):
    category: str
    event_section: str
    url: str
    status: str
    http_status: int | None = None
    parsed_count: int = 0
    error: str | None = None
    retry_count: int = 0


class SummaryTemplateField(BaseModel):
    key: str
    label: str
    order: int
    prompt: str
    field_type: str
    enabled: bool = True


class SummaryTemplateInput(BaseModel):
    name: str
    language: str = "Chinese"
    fields: list[SummaryTemplateField] = Field(default_factory=list)
    system_prompt: str
    input_scope: str = "abstract"
    is_default: bool = False
```

Create `arxiv-local-daily/src/arxiv_local_daily/crawler/__init__.py`:

```python
"""Crawler utilities for arXiv daily listings."""
```

Create `arxiv-local-daily/src/arxiv_local_daily/crawler/parser.py`:

```python
import re
from bs4 import BeautifulSoup, Tag

from arxiv_local_daily.models import ParsedDailyEvent

EVENT_HEADING_MAP = {
    "new submissions": "new",
    "cross-lists": "cross-list",
    "replacements": "replacement",
}

CATEGORY_RE = re.compile(r"\(([a-z-]+\.[A-Z]{2})\)")


def _heading_to_event_type(text: str) -> str | None:
    normalized = " ".join(text.lower().split())
    for marker, event_type in EVENT_HEADING_MAP.items():
        if marker in normalized:
            return event_type
    return None


def _extract_arxiv_id(dt: Tag) -> str | None:
    abstract_link = dt.select_one("a[title='Abstract']")
    if abstract_link is None:
        return None
    href = abstract_link.get("href", "")
    if "/abs/" not in href:
        return None
    return href.rsplit("/", 1)[-1].strip()


def _extract_primary_category(dd: Tag | None) -> str | None:
    if dd is None:
        return None
    primary = dd.select_one(".primary-subject")
    subject_text = primary.get_text(" ", strip=True) if primary else dd.get_text(" ", strip=True)
    match = CATEGORY_RE.search(subject_text)
    return match.group(1) if match else None


def parse_daily_listing(
    html: str,
    *,
    listing_category: str,
    source_url: str,
) -> list[ParsedDailyEvent]:
    soup = BeautifulSoup(html, "html.parser")
    dlpage = soup.select_one("#dlpage") or soup
    events: list[ParsedDailyEvent] = []
    current_event_type: str | None = None

    for node in dlpage.children:
        if not isinstance(node, Tag):
            continue
        if node.name in {"h2", "h3", "h4"}:
            detected = _heading_to_event_type(node.get_text(" ", strip=True))
            if detected is not None:
                current_event_type = detected
            continue
        if node.name != "dl" or current_event_type is None:
            continue
        for dt in node.select(":scope > dt"):
            arxiv_id = _extract_arxiv_id(dt)
            if arxiv_id is None:
                continue
            dd = dt.find_next_sibling("dd")
            events.append(
                ParsedDailyEvent(
                    arxiv_id=arxiv_id,
                    event_type=current_event_type,
                    listing_category=listing_category,
                    primary_category=_extract_primary_category(dd),
                    source_url=source_url,
                )
            )
    return events
```

- [ ] **Step 4: Run parser tests to verify they pass**

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_parser.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/models.py arxiv-local-daily/src/arxiv_local_daily/crawler/__init__.py arxiv-local-daily/src/arxiv_local_daily/crawler/parser.py arxiv-local-daily/tests/fixtures/list_cs_ai_new.html arxiv-local-daily/tests/test_parser.py
git commit -m "feat: parse arxiv daily listing events"
```

---

### Task 4: Event Ingestion Repositories

**Files:**
- Create: `arxiv-local-daily/src/arxiv_local_daily/repositories.py`
- Create: `arxiv-local-daily/src/arxiv_local_daily/services.py`
- Create: `arxiv-local-daily/tests/test_ingestion.py`

- [ ] **Step 1: Write failing ingestion tests**

Create `arxiv-local-daily/tests/test_ingestion.py`:

```python
from pathlib import Path

from arxiv_local_daily.services import ingest_daily_listing_html


def test_ingestion_persists_run_source_papers_and_events(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    run_id = ingest_daily_listing_html(
        db,
        date="2026-06-03",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
        html=html,
    )

    run = db.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    source = db.execute("SELECT * FROM crawl_run_sources WHERE run_id = ?", (run_id,)).fetchone()
    papers = db.execute("SELECT arxiv_id, metadata_status FROM papers ORDER BY arxiv_id").fetchall()
    events = db.execute("SELECT arxiv_id, event_type, listing_category FROM daily_events ORDER BY arxiv_id").fetchall()

    assert run["status"] == "complete"
    assert source["parsed_count"] == 3
    assert [(row["arxiv_id"], row["metadata_status"]) for row in papers] == [
        ("2606.00001", "pending"),
        ("2606.00002", "pending"),
        ("2606.00003", "pending"),
    ]
    assert [(row["arxiv_id"], row["event_type"], row["listing_category"]) for row in events] == [
        ("2606.00001", "new", "cs.AI"),
        ("2606.00002", "cross-list", "cs.AI"),
        ("2606.00003", "replacement", "cs.AI"),
    ]


def test_ingestion_rerun_does_not_duplicate_events(db):
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()

    ingest_daily_listing_html(
        db,
        date="2026-06-03",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
        html=html,
    )
    ingest_daily_listing_html(
        db,
        date="2026-06-03",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
        html=html,
    )

    event_count = db.execute("SELECT COUNT(*) AS count FROM daily_events").fetchone()["count"]
    run_count = db.execute("SELECT COUNT(*) AS count FROM crawl_runs").fetchone()["count"]

    assert event_count == 3
    assert run_count == 2
```

- [ ] **Step 2: Run ingestion tests to verify they fail**

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_ingestion.py -v
```

Expected: FAIL because service and repository modules are missing.

- [ ] **Step 3: Implement repositories and ingestion service**

Create `arxiv-local-daily/src/arxiv_local_daily/repositories.py`:

```python
import json
import sqlite3

from arxiv_local_daily.models import ParsedDailyEvent, SummaryTemplateInput


class CrawlRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create_run(self, *, date: str, mode: str, status: str) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO crawl_runs (date, mode, status)
            VALUES (?, ?, ?)
            """,
            (date, mode, status),
        )
        return int(cursor.lastrowid)

    def finish_run(self, run_id: int, *, status: str, summary_counts: dict[str, int]) -> None:
        self.connection.execute(
            """
            UPDATE crawl_runs
            SET status = ?, finished_at = CURRENT_TIMESTAMP, summary_counts_json = ?
            WHERE id = ?
            """,
            (status, json.dumps(summary_counts, sort_keys=True), run_id),
        )

    def record_source(
        self,
        *,
        run_id: int,
        category: str,
        event_section: str,
        url: str,
        status: str,
        http_status: int | None,
        parsed_count: int,
        error: str | None = None,
        retry_count: int = 0,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO crawl_run_sources
                (run_id, category, event_section, url, status, http_status, parsed_count, error, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, category, event_section, url, status, http_status, parsed_count, error, retry_count),
        )


class PaperRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def ensure_pending_paper(self, arxiv_id: str) -> None:
        self.connection.execute(
            """
            INSERT INTO papers (arxiv_id, metadata_status)
            VALUES (?, 'pending')
            ON CONFLICT(arxiv_id) DO NOTHING
            """,
            (arxiv_id,),
        )

    def upsert_daily_event(self, *, date: str, event: ParsedDailyEvent) -> None:
        self.ensure_pending_paper(event.arxiv_id)
        self.connection.execute(
            """
            INSERT INTO daily_events
                (date, arxiv_id, event_type, listing_category, primary_category, seen_source_url)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, arxiv_id, event_type, listing_category) DO UPDATE SET
                primary_category = excluded.primary_category,
                seen_source_url = excluded.seen_source_url
            """,
            (
                date,
                event.arxiv_id,
                event.event_type,
                event.listing_category,
                event.primary_category,
                event.source_url,
            ),
        )


class TemplateRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create_template(self, template: SummaryTemplateInput) -> int:
        current = self.connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM summary_templates WHERE name = ?",
            (template.name,),
        ).fetchone()
        version = int(current["version"]) + 1
        cursor = self.connection.execute(
            """
            INSERT INTO summary_templates
                (name, language, version, fields_json, system_prompt, input_scope, is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template.name,
                template.language,
                version,
                json.dumps([field.model_dump() for field in template.fields], sort_keys=True),
                template.system_prompt,
                template.input_scope,
                1 if template.is_default else 0,
            ),
        )
        return int(cursor.lastrowid)
```

Create `arxiv-local-daily/src/arxiv_local_daily/services.py`:

```python
import sqlite3

from arxiv_local_daily.crawler.parser import parse_daily_listing
from arxiv_local_daily.db import transaction
from arxiv_local_daily.repositories import CrawlRepository, PaperRepository


def ingest_daily_listing_html(
    connection: sqlite3.Connection,
    *,
    date: str,
    listing_category: str,
    source_url: str,
    html: str,
) -> int:
    events = parse_daily_listing(
        html,
        listing_category=listing_category,
        source_url=source_url,
    )
    counts: dict[str, int] = {}
    for event in events:
        counts[event.event_type] = counts.get(event.event_type, 0) + 1

    with transaction(connection):
        crawl_repo = CrawlRepository(connection)
        paper_repo = PaperRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode="single-source", status="running")
        for event in events:
            paper_repo.upsert_daily_event(date=date, event=event)
        crawl_repo.record_source(
            run_id=run_id,
            category=listing_category,
            event_section="all",
            url=source_url,
            status="complete",
            http_status=200,
            parsed_count=len(events),
        )
        crawl_repo.finish_run(run_id, status="complete", summary_counts=counts)
        return run_id
```

- [ ] **Step 4: Run ingestion tests to verify they pass**

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_ingestion.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/repositories.py arxiv-local-daily/src/arxiv_local_daily/services.py arxiv-local-daily/tests/test_ingestion.py
git commit -m "feat: ingest parsed arxiv daily events"
```

---

### Task 5: Summary Template Storage

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/repositories.py`
- Create: `arxiv-local-daily/tests/test_templates.py`

- [ ] **Step 1: Write failing summary template tests**

Create `arxiv-local-daily/tests/test_templates.py`:

```python
from arxiv_local_daily.models import SummaryTemplateField, SummaryTemplateInput
from arxiv_local_daily.repositories import TemplateRepository


def _template(name: str, label: str) -> SummaryTemplateInput:
    return SummaryTemplateInput(
        name=name,
        language="Chinese",
        system_prompt="Summarize the paper using the configured fields.",
        input_scope="abstract",
        is_default=True,
        fields=[
            SummaryTemplateField(
                key="tldr",
                label=label,
                order=1,
                prompt="Give one sentence.",
                field_type="short_sentence",
                enabled=True,
            )
        ],
    )


def test_create_template_stores_fields_as_versioned_json(db):
    repo = TemplateRepository(db)

    template_id = repo.create_template(_template("default_research", "一句话结论"))
    db.commit()

    row = db.execute("SELECT * FROM summary_templates WHERE id = ?", (template_id,)).fetchone()

    assert row["name"] == "default_research"
    assert row["version"] == 1
    assert "一句话结论" in row["fields_json"]


def test_create_template_increments_version_for_same_name(db):
    repo = TemplateRepository(db)

    first_id = repo.create_template(_template("default_research", "一句话结论"))
    second_id = repo.create_template(_template("default_research", "核心方法"))
    db.commit()

    versions = db.execute(
        "SELECT version FROM summary_templates WHERE id IN (?, ?) ORDER BY version",
        (first_id, second_id),
    ).fetchall()

    assert [row["version"] for row in versions] == [1, 2]
```

- [ ] **Step 2: Run template tests to verify they fail or expose missing behavior**

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_templates.py -v
```

Expected: PASS if Task 4 already implemented `TemplateRepository` fully. If it passes immediately, add the list method test in the next step before changing production code.

- [ ] **Step 3: Add a failing list-default-template test**

Append to `arxiv-local-daily/tests/test_templates.py`:

```python
def test_list_templates_returns_latest_versions_first(db):
    repo = TemplateRepository(db)
    repo.create_template(_template("default_research", "一句话结论"))
    latest_id = repo.create_template(_template("default_research", "核心方法"))
    db.commit()

    rows = repo.list_templates()

    assert rows[0]["id"] == latest_id
    assert rows[0]["version"] == 2
```

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_templates.py::test_list_templates_returns_latest_versions_first -v
```

Expected: FAIL because `TemplateRepository.list_templates` is missing.

- [ ] **Step 4: Implement template listing**

Add this method to `TemplateRepository` in `arxiv-local-daily/src/arxiv_local_daily/repositories.py`:

```python
    def list_templates(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT *
                FROM summary_templates
                ORDER BY name ASC, version DESC
                """
            ).fetchall()
        )
```

- [ ] **Step 5: Run template tests to verify they pass**

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_templates.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add arxiv-local-daily/src/arxiv_local_daily/repositories.py arxiv-local-daily/tests/test_templates.py
git commit -m "feat: store versioned summary templates"
```

---

### Task 6: Minimal FastAPI Endpoints

**Files:**
- Create: `arxiv-local-daily/src/arxiv_local_daily/api.py`
- Modify: `arxiv-local-daily/pyproject.toml`
- Create: `arxiv-local-daily/tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Create `arxiv-local-daily/tests/test_api.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from arxiv_local_daily.api import create_app
from arxiv_local_daily.db import connect, initialize_schema
from arxiv_local_daily.services import ingest_daily_listing_html


def _client_with_seed_data(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "api.sqlite3"
    connection = connect(db_path)
    initialize_schema(connection)
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()
    ingest_daily_listing_html(
        connection,
        date="2026-06-03",
        listing_category="cs.AI",
        source_url="https://arxiv.org/list/cs.AI/new",
        html=html,
    )
    connection.close()
    return TestClient(create_app(database_path=db_path))


def test_get_day_papers_returns_ingested_events(tmp_path):
    client = _client_with_seed_data(tmp_path)

    response = client.get("/api/days/2026-06-03/papers")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    assert data["papers"][0]["arxiv_id"] == "2606.00001"
    assert data["papers"][0]["event_type"] == "new"


def test_get_crawl_runs_returns_status(tmp_path):
    client = _client_with_seed_data(tmp_path)

    response = client.get("/api/crawl/runs/2026-06-03")

    assert response.status_code == 200
    data = response.json()
    assert data["runs"][0]["status"] == "complete"
    assert data["runs"][0]["source_count"] == 1


def test_list_summary_templates_starts_empty(tmp_path):
    client = _client_with_seed_data(tmp_path)

    response = client.get("/api/summary-templates")

    assert response.status_code == 200
    assert response.json() == {"templates": []}
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_api.py -v
```

Expected: FAIL because `arxiv_local_daily.api` is missing or `fastapi.testclient` dependency is incomplete.

- [ ] **Step 3: Add test dependency**

Modify `arxiv-local-daily/pyproject.toml` dev dependencies:

```toml
[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "httpx>=0.27.0",
]
```

The runtime already includes `fastapi`; `httpx` is needed by `TestClient`.

- [ ] **Step 4: Implement FastAPI app**

Create `arxiv-local-daily/src/arxiv_local_daily/api.py`:

```python
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from arxiv_local_daily.config import default_settings
from arxiv_local_daily.db import connect, initialize_schema
from arxiv_local_daily.repositories import TemplateRepository


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def create_app(database_path: Path | str | None = None) -> FastAPI:
    app = FastAPI(title="arxiv-local-daily")
    db_path = Path(database_path) if database_path is not None else default_settings().database_path

    def get_connection():
        connection = connect(db_path)
        initialize_schema(connection)
        return connection

    @app.get("/api/days/{date}/papers")
    def list_day_papers(date: str):
        connection = get_connection()
        try:
            rows = connection.execute(
                """
                SELECT
                    p.arxiv_id,
                    p.title,
                    p.metadata_status,
                    e.event_type,
                    e.listing_category,
                    e.primary_category
                FROM daily_events e
                JOIN papers p ON p.arxiv_id = e.arxiv_id
                WHERE e.date = ?
                ORDER BY p.arxiv_id, e.event_type, e.listing_category
                """,
                (date,),
            ).fetchall()
            papers = [_row_to_dict(row) for row in rows]
            return {"count": len(papers), "papers": papers}
        finally:
            connection.close()

    @app.get("/api/crawl/runs/{date}")
    def list_crawl_runs(date: str):
        connection = get_connection()
        try:
            rows = connection.execute(
                """
                SELECT
                    r.id,
                    r.date,
                    r.mode,
                    r.status,
                    r.started_at,
                    r.finished_at,
                    COUNT(s.id) AS source_count
                FROM crawl_runs r
                LEFT JOIN crawl_run_sources s ON s.run_id = r.id
                WHERE r.date = ?
                GROUP BY r.id
                ORDER BY r.id DESC
                """,
                (date,),
            ).fetchall()
            return {"runs": [_row_to_dict(row) for row in rows]}
        finally:
            connection.close()

    @app.get("/api/summary-templates")
    def list_summary_templates():
        connection = get_connection()
        try:
            repo = TemplateRepository(connection)
            rows = repo.list_templates()
            return {"templates": [_row_to_dict(row) for row in rows]}
        finally:
            connection.close()

    return app
```

- [ ] **Step 5: Run API tests to verify they pass**

Run:

```bash
cd arxiv-local-daily
uv run pytest tests/test_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Run all phase 1 tests**

Run:

```bash
cd arxiv-local-daily
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add arxiv-local-daily/pyproject.toml arxiv-local-daily/src/arxiv_local_daily/api.py arxiv-local-daily/tests/test_api.py
git commit -m "feat: expose phase one api endpoints"
```

---

### Task 7: Phase 1 Documentation and Final Verification

**Files:**
- Modify: `arxiv-local-daily/README.md`
- Modify: `.gitignore`

- [ ] **Step 1: Write README update**

Replace `arxiv-local-daily/README.md` with:

```markdown
# arxiv-local-daily

Local-first arXiv daily crawler, SQLite database, AI summary, search, and discussion app.

## Phase 1 Status

Implemented:

- offline-tested arXiv daily listing parser for `new`, `cross-list`, and `replacement`
- SQLite schema for papers, daily events, crawl runs, summary templates, summaries, and AI jobs
- ingestion service that stores parsed daily events before metadata enrichment
- versioned summary template storage
- minimal FastAPI endpoints for day papers, crawl runs, and summary templates

Deferred to later phases:

- live all-category arXiv fetching
- arXiv API metadata enrichment
- AI workers
- full-text extraction
- deep paper-reading agent
- production web UI

## Run Tests

```bash
uv run pytest -v
```

## Run API

```bash
uv run uvicorn arxiv_local_daily.api:create_app --factory --reload
```

The API stores data at `data/arxiv-local-daily.sqlite3` by default.
```

- [ ] **Step 2: Ensure generated local data is ignored**

Append this line to `.gitignore` if it is not already present:

```gitignore
arxiv-local-daily/data/
```

- [ ] **Step 3: Run all tests**

Run:

```bash
cd arxiv-local-daily
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status -sb
git diff --stat
```

Expected: only README and `.gitignore` changes are unstaged.

- [ ] **Step 5: Commit**

Run:

```bash
git add .gitignore arxiv-local-daily/README.md
git commit -m "docs: document phase one app"
```

- [ ] **Step 6: Final verification**

Run:

```bash
git status -sb
cd arxiv-local-daily
uv run pytest -v
```

Expected:

- Git status shows clean `main`.
- All tests pass.

---

## Self-Review

Spec coverage for phase 1:

- Covered: independent project scaffold, SQLite schema, daily event model, daily listing parser for all three event types, auditable crawl run/source records, event-before-metadata persistence, summary template versioning, minimal API endpoints, offline tests.
- Deferred intentionally: live all-category crawl scheduler, arXiv API metadata enrichment, background workers, AI summaries, full-text extraction, deep reading agent, rich web UI, chat. These require later phase plans after the core persistence and parser slice is stable.

Placeholder scan:

- No `TBD`, `TODO`, or "implement later" placeholders are used in executable steps.
- Deferred items are explicitly listed as later phases, not hidden inside this phase.

Type consistency:

- `ParsedDailyEvent`, `SummaryTemplateInput`, and `SummaryTemplateField` are defined before use.
- `TemplateRepository.create_template` and `TemplateRepository.list_templates` are used consistently.
- API endpoints use the same table and column names defined in `db.py`.
