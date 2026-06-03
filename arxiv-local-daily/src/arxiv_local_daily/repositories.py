import json
import sqlite3

from arxiv_local_daily.models import PaperMetadata, ParsedDailyEvent, SummaryTemplateInput


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
                (
                    metadata.arxiv_id,
                    version.version,
                    version.updated_at,
                    version.comment,
                    version.source_hash,
                ),
            )

    def mark_metadata_status(self, arxiv_id: str, status: str) -> None:
        self.ensure_pending_paper(arxiv_id)
        self.connection.execute(
            """
            UPDATE papers
            SET metadata_status = ?, updated_row_at = CURRENT_TIMESTAMP
            WHERE arxiv_id = ?
            """,
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
