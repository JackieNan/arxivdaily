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
            metadata_error TEXT,
            metadata_attempts INTEGER NOT NULL DEFAULT 0,
            metadata_next_run_at TEXT,
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

        CREATE TABLE IF NOT EXISTS metadata_sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            from_date TEXT,
            until_date TEXT,
            set_spec TEXT,
            max_pages INTEGER NOT NULL DEFAULT 1,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            records_seen INTEGER NOT NULL DEFAULT 0,
            records_upserted INTEGER NOT NULL DEFAULT 0,
            pages_fetched INTEGER NOT NULL DEFAULT 0,
            resumption_token TEXT,
            error TEXT
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

        CREATE TABLE IF NOT EXISTS paper_discussions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arxiv_id TEXT NOT NULL REFERENCES papers(arxiv_id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tags_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    _ensure_column(connection, "papers", "metadata_error", "TEXT")
    _ensure_column(connection, "papers", "metadata_attempts", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "papers", "metadata_next_run_at", "TEXT")
    connection.commit()


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
