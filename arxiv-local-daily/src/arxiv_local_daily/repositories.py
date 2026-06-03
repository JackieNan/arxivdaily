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
                json.dumps([field.model_dump() for field in template.fields], sort_keys=True, ensure_ascii=False),
                template.system_prompt,
                template.input_scope,
                1 if template.is_default else 0,
            ),
        )
        return int(cursor.lastrowid)

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
