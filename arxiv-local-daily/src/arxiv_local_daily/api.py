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
