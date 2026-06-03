from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI
from pydantic import BaseModel, Field

from arxiv_local_daily.config import default_settings
from arxiv_local_daily.crawler.live import run_live_daily_crawl
from arxiv_local_daily.db import connect, initialize_schema
from arxiv_local_daily.models import SummaryTemplateInput
from arxiv_local_daily.repositories import CrawlRepository, SummaryRepository, TemplateRepository
from arxiv_local_daily.services import enrich_metadata_for_date, generate_summaries_for_date


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


class CrawlRunRequest(BaseModel):
    date: str
    categories: list[str] = Field(min_length=1)


class MetadataRunRequest(BaseModel):
    date: str
    limit: int = 100


class SummaryRunRequest(BaseModel):
    date: str
    template_id: int | None = None
    template_name: str | None = None
    model: str = "local"
    limit: int = 20
    force: bool = False


CrawlerRunner = Callable[..., int]
MetadataRunner = Callable[..., dict[str, int]]
SummaryRunner = Callable[..., dict[str, Any]]


def create_app(
    database_path: Path | str | None = None,
    crawl_runner: CrawlerRunner = run_live_daily_crawl,
    metadata_runner: MetadataRunner = enrich_metadata_for_date,
    summary_runner: SummaryRunner = generate_summaries_for_date,
) -> FastAPI:
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
            repo = CrawlRepository(connection)
            return {"runs": repo.list_runs_for_date(date)}
        finally:
            connection.close()

    @app.post("/api/crawl/run")
    def run_crawl(request: CrawlRunRequest):
        connection = get_connection()
        try:
            run_id = crawl_runner(
                connection,
                date=request.date,
                categories=request.categories,
            )
            return {"run_id": run_id}
        finally:
            connection.close()

    @app.post("/api/metadata/run")
    def run_metadata(request: MetadataRunRequest):
        connection = get_connection()
        try:
            return metadata_runner(connection, date=request.date, limit=request.limit)
        finally:
            connection.close()

    @app.post("/api/summaries/run")
    def run_summaries(request: SummaryRunRequest):
        connection = get_connection()
        try:
            return summary_runner(
                connection,
                date=request.date,
                template_id=request.template_id,
                template_name=request.template_name,
                model=request.model,
                limit=request.limit,
                force=request.force,
            )
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

    @app.post("/api/summary-templates")
    def create_summary_template(template: SummaryTemplateInput):
        connection = get_connection()
        try:
            repo = TemplateRepository(connection)
            template_id = repo.create_template(template)
            connection.commit()
            row = repo.get_template(template_id=template_id)
            return {"template_id": template_id, "version": row["version"]}
        finally:
            connection.close()

    @app.get("/api/papers/{arxiv_id}/summaries")
    def list_paper_summaries(arxiv_id: str):
        connection = get_connection()
        try:
            repo = SummaryRepository(connection)
            return {"summaries": repo.list_summaries_for_paper(arxiv_id)}
        finally:
            connection.close()

    return app
