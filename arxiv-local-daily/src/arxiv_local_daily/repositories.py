import json
import sqlite3
from typing import Any

from arxiv_local_daily.models import (
    PaperDiscussionInput,
    PaperMetadata,
    ParsedDailyEvent,
    SummaryTemplateInput,
)


def _listing_category_filter(categories: list[str] | None, *, column: str = "e.listing_category") -> tuple[str, tuple[str, ...]]:
    if not categories:
        return "", ()
    placeholders = ", ".join("?" for _ in categories)
    return f" AND {column} IN ({placeholders})", tuple(categories)


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
        expected_count: int | None = None,
        missing_count: int = 0,
        error: str | None = None,
        retry_count: int = 0,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO crawl_run_sources
                (run_id, category, event_section, url, status, http_status, parsed_count,
                 expected_count, missing_count, error, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                category,
                event_section,
                url,
                status,
                http_status,
                parsed_count,
                expected_count,
                missing_count,
                error,
                retry_count,
            ),
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
                SELECT category, event_section, url, status, http_status, parsed_count,
                       expected_count, missing_count, error, retry_count
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

    def list_source_rows_for_date(self, date: str) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT
                r.id AS run_id,
                r.mode AS run_mode,
                r.status AS run_status,
                r.started_at,
                r.finished_at,
                s.category,
                s.event_section,
                s.url,
                s.status,
                s.http_status,
                s.parsed_count,
                s.expected_count,
                s.missing_count,
                s.error,
                s.retry_count
            FROM crawl_run_sources s
            JOIN crawl_runs r ON r.id = s.run_id
            WHERE r.date = ?
            ORDER BY r.id ASC, s.category ASC, s.url ASC
            """,
            (date,),
        ).fetchall()
        return [dict(row) for row in rows]


class PreflightRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create_run(self, *, date: str, mode: str, status: str, category_count: int) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO crawl_preflight_runs (date, mode, status, category_count)
            VALUES (?, ?, ?, ?)
            """,
            (date, mode, status, category_count),
        )
        return int(cursor.lastrowid)

    def record_source(
        self,
        *,
        run_id: int,
        category: str,
        url: str,
        status: str,
        http_status: int | None,
        listing_date: str | None,
        parsed_count: int,
        expected_count: int | None,
        distinct_count: int,
        missing_count: int,
        arxiv_ids: list[str],
        error: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO crawl_preflight_sources
                (run_id, category, url, status, http_status, listing_date,
                 parsed_count, expected_count, distinct_count, missing_count, error, arxiv_ids_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                category,
                url,
                status,
                http_status,
                listing_date,
                parsed_count,
                expected_count,
                distinct_count,
                missing_count,
                error,
                json.dumps(arxiv_ids, sort_keys=True),
            ),
        )

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        source_count: int,
        listing_entry_count: int,
        distinct_paper_count: int,
        missing_count: int,
        error_counts: dict[str, int],
    ) -> None:
        self.connection.execute(
            """
            UPDATE crawl_preflight_runs
            SET status = ?,
                finished_at = CURRENT_TIMESTAMP,
                source_count = ?,
                listing_entry_count = ?,
                distinct_paper_count = ?,
                missing_count = ?,
                error_counts_json = ?
            WHERE id = ?
            """,
            (
                status,
                source_count,
                listing_entry_count,
                distinct_paper_count,
                missing_count,
                json.dumps(error_counts, sort_keys=True),
                run_id,
            ),
        )

    def latest_for_date(self, date: str) -> dict[str, Any] | None:
        run = self.connection.execute(
            """
            SELECT *
            FROM crawl_preflight_runs
            WHERE date = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (date,),
        ).fetchone()
        if run is None:
            return None
        sources = self.connection.execute(
            """
            SELECT *
            FROM crawl_preflight_sources
            WHERE run_id = ?
            ORDER BY category ASC, url ASC
            """,
            (run["id"],),
        ).fetchall()
        item = dict(run)
        item["error_counts"] = json.loads(item.pop("error_counts_json") or "{}")
        item["sources"] = []
        for source in sources:
            source_item = dict(source)
            source_item["arxiv_ids"] = json.loads(source_item.pop("arxiv_ids_json") or "[]")
            item["sources"].append(source_item)
        return item


class DailyAutomationRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create_run(
        self,
        *,
        date: str,
        crawl_mode: str,
        template_name: str | None,
        model: str,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO daily_automation_runs
                (date, crawl_mode, status, current_step, template_name, model)
            VALUES (?, ?, 'queued', 'queued', ?, ?)
            """,
            (date, crawl_mode, template_name, model),
        )
        return int(cursor.lastrowid)

    def update_run(
        self,
        run_id: int,
        *,
        status: str,
        current_step: str,
        error: str | None = None,
        finished: bool = False,
    ) -> None:
        finished_sql = ", finished_at = CURRENT_TIMESTAMP" if finished else ""
        self.connection.execute(
            f"""
            UPDATE daily_automation_runs
            SET status = ?,
                current_step = ?,
                error = ?,
                updated_at = CURRENT_TIMESTAMP
                {finished_sql}
            WHERE id = ?
            """,
            (status, current_step, error, run_id),
        )

    def latest_for_date(self, date: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM daily_automation_runs
            WHERE date = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (date,),
        ).fetchone()
        return dict(row) if row is not None else None


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
        if event.title:
            self.connection.execute(
                """
                UPDATE papers
                SET title = COALESCE(title, ?), updated_row_at = CURRENT_TIMESTAMP
                WHERE arxiv_id = ?
                """,
                (event.title, event.arxiv_id),
            )
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
                metadata_error = NULL,
                metadata_attempts = 0,
                metadata_next_run_at = NULL,
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

    def mark_metadata_status(
        self,
        arxiv_id: str,
        status: str,
        *,
        error: str | None = None,
        next_run_at: str | None = None,
        increment_attempts: bool = False,
    ) -> None:
        self.ensure_pending_paper(arxiv_id)
        attempts_sql = "metadata_attempts + 1" if increment_attempts else "metadata_attempts"
        self.connection.execute(
            f"""
            UPDATE papers
            SET
                metadata_status = ?,
                metadata_error = ?,
                metadata_next_run_at = ?,
                metadata_attempts = {attempts_sql},
                updated_row_at = CURRENT_TIMESTAMP
            WHERE arxiv_id = ?
            """,
            (status, error, next_run_at, arxiv_id),
        )

    def list_metadata_pending_ids_for_date(
        self,
        date: str,
        *,
        limit: int | None,
        categories: list[str] | None = None,
    ) -> list[str]:
        category_sql, category_params = _listing_category_filter(categories)
        limit_sql = "" if limit is None else "LIMIT ?"
        params: tuple[Any, ...] = (date, *category_params) if limit is None else (date, *category_params, limit)
        rows = self.connection.execute(
            f"""
            SELECT DISTINCT p.arxiv_id
            FROM papers p
            JOIN daily_events e ON e.arxiv_id = p.arxiv_id
            WHERE e.date = ?
              {category_sql}
              AND p.metadata_status != 'complete'
              AND (
                p.metadata_next_run_at IS NULL
                OR datetime(p.metadata_next_run_at) <= CURRENT_TIMESTAMP
              )
            ORDER BY p.arxiv_id
            {limit_sql}
            """,
            params,
        ).fetchall()
        return [row["arxiv_id"] for row in rows]

    def list_daily_ids_for_date(
        self,
        date: str,
        *,
        limit: int | None = None,
        categories: list[str] | None = None,
    ) -> list[str]:
        category_sql, category_params = _listing_category_filter(categories, column="listing_category")
        limit_sql = "" if limit is None else "LIMIT ?"
        params: tuple[Any, ...] = (date, *category_params) if limit is None else (date, *category_params, limit)
        rows = self.connection.execute(
            f"""
            SELECT DISTINCT arxiv_id
            FROM daily_events
            WHERE date = ?
              {category_sql}
            ORDER BY arxiv_id
            {limit_sql}
            """,
            params,
        ).fetchall()
        return [row["arxiv_id"] for row in rows]


class MetadataSyncRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create_run(
        self,
        *,
        source: str,
        from_date: str | None = None,
        until_date: str | None = None,
        set_spec: str | None = None,
        max_pages: int = 1,
        status: str = "queued",
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO metadata_sync_runs
                (source, status, from_date, until_date, set_spec, max_pages)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source, status, from_date, until_date, set_spec, max_pages),
        )
        return int(cursor.lastrowid)

    def mark_running(self, run_id: int) -> None:
        self.connection.execute(
            """
            UPDATE metadata_sync_runs
            SET status = ?, error = NULL
            WHERE id = ?
            """,
            ("running", run_id),
        )

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        records_seen: int,
        records_upserted: int,
        pages_fetched: int,
        resumption_token: str | None = None,
        error: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            UPDATE metadata_sync_runs
            SET
                status = ?,
                finished_at = CURRENT_TIMESTAMP,
                records_seen = ?,
                records_upserted = ?,
                pages_fetched = ?,
                resumption_token = ?,
                error = ?
            WHERE id = ?
            """,
            (
                status,
                records_seen,
                records_upserted,
                pages_fetched,
                resumption_token,
                error,
                run_id,
            ),
        )

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM metadata_sync_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def list_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT *
            FROM metadata_sync_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


class MetadataEnrichmentRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create_run(self, *, date: str, status: str = "running") -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO metadata_enrichment_runs (date, status)
            VALUES (?, ?)
            """,
            (date, status),
        )
        return int(cursor.lastrowid)

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        crawl_count: int,
        id_api_count: int,
        oai_count: int,
        merged_count: int,
        missing_after_merge_count: int,
        oai_missing_count: int,
        oai_extra_count: int,
        mismatch_count: int,
        error: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            UPDATE metadata_enrichment_runs
            SET
                status = ?,
                finished_at = CURRENT_TIMESTAMP,
                crawl_count = ?,
                id_api_count = ?,
                oai_count = ?,
                merged_count = ?,
                missing_after_merge_count = ?,
                oai_missing_count = ?,
                oai_extra_count = ?,
                mismatch_count = ?,
                error = ?
            WHERE id = ?
            """,
            (
                status,
                crawl_count,
                id_api_count,
                oai_count,
                merged_count,
                missing_after_merge_count,
                oai_missing_count,
                oai_extra_count,
                mismatch_count,
                error,
                run_id,
            ),
        )

    def record_source(self, *, run_id: int, source: str, metadata: PaperMetadata) -> None:
        self.connection.execute(
            """
            INSERT INTO metadata_source_records (run_id, source, arxiv_id, payload_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(run_id, source, arxiv_id) DO UPDATE SET
                payload_json = excluded.payload_json
            """,
            (
                run_id,
                source,
                metadata.arxiv_id,
                json.dumps(metadata.model_dump(), ensure_ascii=False, sort_keys=True),
            ),
        )

    def record_report(
        self,
        *,
        run_id: int,
        report_type: str,
        arxiv_id: str,
        details: dict[str, Any],
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO metadata_merge_reports (run_id, report_type, arxiv_id, details_json)
            VALUES (?, ?, ?, ?)
            """,
            (run_id, report_type, arxiv_id, json.dumps(details, ensure_ascii=False, sort_keys=True)),
        )


class TemplateRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def upsert_single_template(self, template: SummaryTemplateInput) -> int:
        fields_json = json.dumps([field.model_dump() for field in template.fields], sort_keys=True, ensure_ascii=False)
        current = self.connection.execute(
            """
            SELECT id
            FROM summary_templates
            WHERE name = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (template.name,),
        ).fetchone()
        if current is None:
            current = self.connection.execute(
                """
                SELECT id
                FROM summary_templates
                ORDER BY is_default DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        if current is None:
            cursor = self.connection.execute(
                """
                INSERT INTO summary_templates
                    (name, language, version, fields_json, system_prompt, input_scope, is_default)
                VALUES (?, ?, 1, ?, ?, ?, 1)
                """,
                (
                    template.name,
                    template.language,
                    fields_json,
                    template.system_prompt,
                    template.input_scope,
                ),
            )
            return int(cursor.lastrowid)

        template_id = int(current["id"])
        self.connection.execute("UPDATE summary_templates SET is_default = 0 WHERE id != ?", (template_id,))
        self.connection.execute(
            """
            UPDATE summary_templates
            SET name = ?,
                language = ?,
                version = 1,
                fields_json = ?,
                system_prompt = ?,
                input_scope = ?,
                is_default = 1
            WHERE id = ?
            """,
            (
                template.name,
                template.language,
                fields_json,
                template.system_prompt,
                template.input_scope,
                template_id,
            ),
        )
        return template_id

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

    def get_template(
        self,
        *,
        template_id: int | None = None,
        name: str | None = None,
    ) -> sqlite3.Row | None:
        if template_id is not None:
            return self.connection.execute(
                "SELECT * FROM summary_templates WHERE id = ?",
                (template_id,),
            ).fetchone()
        if name is not None:
            return self.connection.execute(
                """
                SELECT *
                FROM summary_templates
                WHERE name = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (name,),
            ).fetchone()
        return self.connection.execute(
            """
            SELECT *
            FROM summary_templates
            ORDER BY is_default DESC, name ASC, version DESC
            LIMIT 1
            """
        ).fetchone()


class SummaryRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def list_summary_candidate_ids_for_date(
        self,
        *,
        date: str,
        template_id: int,
        template_version: int,
        model: str,
        input_scope: str,
        limit: int | None,
        force: bool = False,
    ) -> list[str]:
        limit_sql = "" if limit is None else "LIMIT ?"
        params: tuple[Any, ...] = (
            date,
            1 if force else 0,
            template_id,
            template_version,
            model,
            input_scope,
        )
        if limit is not None:
            params = (*params, limit)
        rows = self.connection.execute(
            f"""
            SELECT DISTINCT p.arxiv_id
            FROM papers p
            JOIN daily_events e ON e.arxiv_id = p.arxiv_id
            WHERE e.date = ?
              AND p.metadata_status = 'complete'
              AND COALESCE(p.abstract, '') != ''
              AND (
                ? = 1 OR NOT EXISTS (
                    SELECT 1
                    FROM summaries s
                    WHERE s.arxiv_id = p.arxiv_id
                      AND s.template_id = ?
                      AND s.template_version = ?
                      AND s.model = ?
                      AND s.input_scope = ?
                      AND s.status = 'complete'
                )
              )
            ORDER BY p.arxiv_id
            {limit_sql}
            """,
            params,
        ).fetchall()
        return [row["arxiv_id"] for row in rows]

    def count_existing_complete_summaries_for_date(
        self,
        *,
        date: str,
        template_id: int,
        template_version: int,
        model: str,
        input_scope: str,
    ) -> int:
        row = self.connection.execute(
            """
            SELECT COUNT(DISTINCT p.arxiv_id) AS count
            FROM papers p
            JOIN daily_events e ON e.arxiv_id = p.arxiv_id
            JOIN summaries s ON s.arxiv_id = p.arxiv_id
            WHERE e.date = ?
              AND p.metadata_status = 'complete'
              AND s.template_id = ?
              AND s.template_version = ?
              AND s.model = ?
              AND s.input_scope = ?
              AND s.status = 'complete'
            """,
            (date, template_id, template_version, model, input_scope),
        ).fetchone()
        return int(row["count"])

    def get_paper_for_summary(self, arxiv_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT
                arxiv_id,
                title,
                abstract,
                authors_json,
                primary_category,
                categories_json,
                abs_url,
                pdf_url,
                metadata_status,
                published_at,
                updated_at
            FROM papers
            WHERE arxiv_id = ?
            """,
            (arxiv_id,),
        ).fetchone()

    def upsert_summary(
        self,
        *,
        arxiv_id: str,
        template_id: int,
        template_version: int,
        model: str,
        language: str,
        input_scope: str,
        content: dict[str, Any],
        status: str,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO summaries
                (arxiv_id, template_id, template_version, model, language, input_scope, content_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(arxiv_id, template_id, template_version, model, input_scope) DO UPDATE SET
                language = excluded.language,
                content_json = excluded.content_json,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                arxiv_id,
                template_id,
                template_version,
                model,
                language,
                input_scope,
                json.dumps(content, ensure_ascii=False, sort_keys=True),
                status,
            ),
        )
        return int(cursor.lastrowid)

    def list_summaries_for_paper(self, arxiv_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT
                s.id,
                s.arxiv_id,
                s.template_id,
                t.name AS template_name,
                s.template_version,
                s.model,
                s.language,
                s.input_scope,
                s.content_json,
                s.status,
                s.created_at,
                s.updated_at
            FROM summaries s
            JOIN summary_templates t ON t.id = s.template_id
            WHERE s.arxiv_id = ?
            ORDER BY s.updated_at DESC, s.id DESC
            """,
            (arxiv_id,),
        ).fetchall()
        summaries: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["content"] = json.loads(item.pop("content_json"))
            summaries.append(item)
        return summaries


class ScoreRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def list_score_candidate_ids_for_date(
        self,
        *,
        date: str,
        model: str,
        rubric_version: str,
        limit: int | None,
        force: bool = False,
    ) -> list[str]:
        limit_sql = "" if limit is None else "LIMIT ?"
        params: tuple[Any, ...] = (date, 1 if force else 0, model, rubric_version)
        if limit is not None:
            params = (*params, limit)
        rows = self.connection.execute(
            f"""
            SELECT DISTINCT p.arxiv_id
            FROM papers p
            JOIN daily_events e ON e.arxiv_id = p.arxiv_id
            WHERE e.date = ?
              AND p.metadata_status = 'complete'
              AND COALESCE(p.abstract, '') != ''
              AND (
                ? = 1 OR NOT EXISTS (
                    SELECT 1
                    FROM paper_scores ps
                    WHERE ps.arxiv_id = p.arxiv_id
                      AND ps.model = ?
                      AND ps.rubric_version = ?
                      AND ps.status = 'complete'
                )
              )
            ORDER BY p.arxiv_id
            {limit_sql}
            """,
            params,
        ).fetchall()
        return [row["arxiv_id"] for row in rows]

    def get_paper_for_score(self, arxiv_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT arxiv_id, title, abstract, primary_category, categories_json
            FROM papers
            WHERE arxiv_id = ?
            """,
            (arxiv_id,),
        ).fetchone()

    def get_latest_summary_content(self, arxiv_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT content_json
            FROM summaries
            WHERE arxiv_id = ?
              AND status = 'complete'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (arxiv_id,),
        ).fetchone()
        return json.loads(row["content_json"]) if row is not None else {}

    def upsert_score(
        self,
        *,
        arxiv_id: str,
        model: str,
        rubric_version: str,
        content: dict[str, Any],
        status: str,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO paper_scores
                (arxiv_id, rubric_version, model, score_total, score_relevance, score_novelty,
                 score_technical_depth, score_evidence, score_actionability, recommended_action,
                 rationale, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(arxiv_id, rubric_version, model) DO UPDATE SET
                score_total = excluded.score_total,
                score_relevance = excluded.score_relevance,
                score_novelty = excluded.score_novelty,
                score_technical_depth = excluded.score_technical_depth,
                score_evidence = excluded.score_evidence,
                score_actionability = excluded.score_actionability,
                recommended_action = excluded.recommended_action,
                rationale = excluded.rationale,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                arxiv_id,
                rubric_version,
                model,
                int(content["score_total"]),
                int(content["score_relevance"]),
                int(content["score_novelty"]),
                int(content["score_technical_depth"]),
                int(content["score_evidence"]),
                int(content["score_actionability"]),
                str(content["recommended_action"]),
                str(content["rationale"]),
                status,
            ),
        )
        return int(cursor.lastrowid)

    def get_latest_score(self, arxiv_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM paper_scores
            WHERE arxiv_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (arxiv_id,),
        ).fetchone()
        return dict(row) if row is not None else None


class DiscussionRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def add_message(self, arxiv_id: str, message: PaperDiscussionInput) -> int:
        PaperRepository(self.connection).ensure_pending_paper(arxiv_id)
        cursor = self.connection.execute(
            """
            INSERT INTO paper_discussions (arxiv_id, role, content, tags_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                arxiv_id,
                message.role,
                message.content,
                json.dumps(message.tags, ensure_ascii=False, sort_keys=True),
            ),
        )
        return int(cursor.lastrowid)

    def list_messages(self, arxiv_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, arxiv_id, role, content, tags_json, created_at
            FROM paper_discussions
            WHERE arxiv_id = ?
            ORDER BY id ASC
            """,
            (arxiv_id,),
        ).fetchall()
        messages: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["tags"] = json.loads(item.pop("tags_json"))
            messages.append(item)
        return messages


class SearchRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def search_papers(
        self,
        *,
        query: str | None = None,
        date: str | None = None,
        category: str | list[str] | None = None,
        event_type: str | None = None,
        metadata_status: str | None = None,
        summary_status: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: str = "recent",
    ) -> list[dict[str, Any]]:
        where, params = self._search_where(
            query=query,
            date=date,
            category=category,
            event_type=event_type,
            metadata_status=metadata_status,
            summary_status=summary_status,
        )
        order_by = "latest_score DESC, latest_date DESC, p.arxiv_id ASC" if sort == "score" else "latest_date DESC, p.arxiv_id ASC"
        limit_sql = ""
        query_params: tuple[Any, ...] = tuple(params)
        if limit is not None:
            limit_sql = "LIMIT ?"
            query_params = (*query_params, limit)
            if offset > 0:
                limit_sql += " OFFSET ?"
                query_params = (*query_params, offset)
        elif offset > 0:
            limit_sql = "LIMIT -1 OFFSET ?"
            query_params = (*query_params, offset)
        rows = self.connection.execute(
            f"""
            SELECT DISTINCT
                p.arxiv_id,
                p.title,
                p.abstract,
                p.authors_json,
                p.primary_category,
                p.categories_json,
                p.abs_url,
                p.pdf_url,
                p.published_at,
                p.updated_at,
                p.metadata_status,
                p.metadata_error,
                p.metadata_attempts,
                p.metadata_next_run_at,
                (
                    SELECT MAX(de.date)
                    FROM daily_events de
                    WHERE de.arxiv_id = p.arxiv_id
                ) AS latest_date,
                (
                    SELECT ps.score_total
                    FROM paper_scores ps
                    WHERE ps.arxiv_id = p.arxiv_id
                      AND ps.status = 'complete'
                    ORDER BY ps.updated_at DESC, ps.id DESC
                    LIMIT 1
                ) AS latest_score
            FROM papers p
            LEFT JOIN daily_events e ON e.arxiv_id = p.arxiv_id
            WHERE {" AND ".join(where)}
            ORDER BY {order_by}
            {limit_sql}
            """,
            query_params,
        ).fetchall()
        return [self._paper_search_result(row) for row in rows]

    def count_search_papers(
        self,
        *,
        query: str | None = None,
        date: str | None = None,
        category: str | list[str] | None = None,
        event_type: str | None = None,
        metadata_status: str | None = None,
        summary_status: str | None = None,
    ) -> int:
        where, params = self._search_where(
            query=query,
            date=date,
            category=category,
            event_type=event_type,
            metadata_status=metadata_status,
            summary_status=summary_status,
        )
        row = self.connection.execute(
            f"""
            SELECT COUNT(DISTINCT p.arxiv_id) AS count
            FROM papers p
            LEFT JOIN daily_events e ON e.arxiv_id = p.arxiv_id
            WHERE {" AND ".join(where)}
            """,
            tuple(params),
        ).fetchone()
        return int(row["count"] or 0)

    def _search_where(
        self,
        *,
        query: str | None,
        date: str | None,
        category: str | list[str] | None,
        event_type: str | None,
        metadata_status: str | None,
        summary_status: str | None,
    ) -> tuple[list[str], list[Any]]:
        where = ["1 = 1"]
        params: list[Any] = []
        if query:
            like_query = f"%{query.lower()}%"
            where.append(
                """
                (
                    LOWER(p.arxiv_id) LIKE ?
                    OR LOWER(COALESCE(p.title, '')) LIKE ?
                    OR LOWER(COALESCE(p.abstract, '')) LIKE ?
                    OR LOWER(COALESCE(p.authors_json, '')) LIKE ?
                    OR EXISTS (
                        SELECT 1 FROM summaries qs
                        WHERE qs.arxiv_id = p.arxiv_id
                          AND LOWER(qs.content_json) LIKE ?
                    )
                )
                """
            )
            params.extend([like_query] * 5)
        if date:
            where.append("e.date = ?")
            params.append(date)
        if category:
            category_values = [category] if isinstance(category, str) else category
            category_clauses: list[str] = []
            category_params: list[Any] = []
            for raw_category in category_values:
                category_value = raw_category.strip().lower()
                if not category_value:
                    continue
                if "." in category_value:
                    json_match = f'%"{category_value}"%'
                    category_clauses.append(
                        """
                        (
                            LOWER(COALESCE(e.listing_category, '')) = ?
                            OR LOWER(COALESCE(p.primary_category, '')) = ?
                            OR LOWER(COALESCE(p.categories_json, '')) LIKE ?
                        )
                        """
                    )
                    category_params.extend([category_value, category_value, json_match])
                else:
                    category_prefix = f"{category_value}.%"
                    json_prefix = f'%"{category_value}.%'
                    category_clauses.append(
                        """
                        (
                            LOWER(COALESCE(e.listing_category, '')) = ?
                            OR LOWER(COALESCE(e.listing_category, '')) LIKE ?
                            OR LOWER(COALESCE(p.primary_category, '')) = ?
                            OR LOWER(COALESCE(p.primary_category, '')) LIKE ?
                            OR LOWER(COALESCE(p.categories_json, '')) LIKE ?
                        )
                        """
                    )
                    category_params.extend(
                        [category_value, category_prefix, category_value, category_prefix, json_prefix]
                    )
            if category_clauses:
                where.append(f"({' OR '.join(category_clauses)})")
                params.extend(category_params)
        if event_type:
            where.append("e.event_type = ?")
            params.append(event_type)
        if metadata_status:
            where.append("p.metadata_status = ?")
            params.append(metadata_status)
        if summary_status:
            where.append(
                """
                EXISTS (
                    SELECT 1 FROM summaries fs
                    WHERE fs.arxiv_id = p.arxiv_id
                      AND fs.status = ?
                )
                """
            )
            params.append(summary_status)
        return where, params

    def get_paper_detail(self, arxiv_id: str) -> dict[str, Any] | None:
        paper_row = self.connection.execute(
            """
            SELECT
                arxiv_id,
                title,
                abstract,
                authors_json,
                primary_category,
                categories_json,
                abs_url,
                pdf_url,
                published_at,
                updated_at,
                metadata_status,
                metadata_error,
                metadata_attempts,
                metadata_next_run_at,
                created_at,
                updated_row_at
            FROM papers
            WHERE arxiv_id = ?
            """,
            (arxiv_id,),
        ).fetchone()
        if paper_row is None:
            return None
        events = [
            dict(row)
            for row in self.connection.execute(
                """
                SELECT date, event_type, listing_category, primary_category, seen_source_url, created_at
                FROM daily_events
                WHERE arxiv_id = ?
                ORDER BY date DESC, event_type ASC, listing_category ASC
                """,
                (arxiv_id,),
            ).fetchall()
        ]
        return {
            "paper": self._paper_dict(paper_row),
            "events": events,
            "summaries": SummaryRepository(self.connection).list_summaries_for_paper(arxiv_id),
            "score": ScoreRepository(self.connection).get_latest_score(arxiv_id),
            "discussions": DiscussionRepository(self.connection).list_messages(arxiv_id),
        }

    def _paper_search_result(self, row: sqlite3.Row) -> dict[str, Any]:
        item = self._paper_dict(row)
        item["latest_date"] = row["latest_date"]
        item["score"] = ScoreRepository(self.connection).get_latest_score(row["arxiv_id"])
        item["summary_keywords"] = self._latest_summary_keywords(row["arxiv_id"])
        item["event_types"] = self._list_daily_event_values(row["arxiv_id"], "event_type")
        item["listing_categories"] = self._list_daily_event_values(row["arxiv_id"], "listing_category")
        item["summary_statuses"] = self._list_summary_statuses(row["arxiv_id"])
        return item

    def _paper_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        if "authors_json" in item:
            item["authors"] = json.loads(item.pop("authors_json") or "[]")
        if "categories_json" in item:
            item["categories"] = json.loads(item.pop("categories_json") or "[]")
        return item

    def _list_daily_event_values(self, arxiv_id: str, column: str) -> list[str]:
        rows = self.connection.execute(
            f"""
            SELECT DISTINCT {column} AS value
            FROM daily_events
            WHERE arxiv_id = ?
            ORDER BY value ASC
            """,
            (arxiv_id,),
        ).fetchall()
        return [row["value"] for row in rows if row["value"] is not None]

    def _list_summary_statuses(self, arxiv_id: str) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT DISTINCT status
            FROM summaries
            WHERE arxiv_id = ?
            ORDER BY status ASC
            """,
            (arxiv_id,),
        ).fetchall()
        return [row["status"] for row in rows]

    def _latest_summary_keywords(self, arxiv_id: str) -> list[str]:
        row = self.connection.execute(
            """
            SELECT content_json
            FROM summaries
            WHERE arxiv_id = ?
              AND status = 'complete'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (arxiv_id,),
        ).fetchone()
        if row is None:
            return []
        content = json.loads(row["content_json"])
        raw_keywords = content.get("keywords") or content.get("关键词") or content.get("key_terms") or []
        if isinstance(raw_keywords, list):
            return [str(keyword).strip() for keyword in raw_keywords if str(keyword).strip()]
        if isinstance(raw_keywords, str):
            normalized = raw_keywords.replace("，", ",").replace("、", ",").replace("；", ",").replace(";", ",")
            return [keyword.strip() for keyword in normalized.split(",") if keyword.strip()]
        return []
