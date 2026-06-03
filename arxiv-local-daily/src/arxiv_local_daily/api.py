from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from arxiv_local_daily.config import default_settings
from arxiv_local_daily.crawler.live import run_live_daily_crawl
from arxiv_local_daily.db import connect, initialize_schema
from arxiv_local_daily.models import PaperDiscussionInput, SummaryTemplateInput
from arxiv_local_daily.repositories import (
    CrawlRepository,
    DiscussionRepository,
    SearchRepository,
    SummaryRepository,
    TemplateRepository,
)
from arxiv_local_daily.services import (
    enrich_metadata_for_date,
    generate_summaries_for_date,
    get_crawl_completeness_for_date,
    retry_incomplete_crawl_categories_for_date,
)


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


class CrawlRunRequest(BaseModel):
    date: str
    categories: list[str] | None = Field(default=None)


class CrawlRetryFailedRequest(BaseModel):
    date: str
    expected_categories: list[str] | None = None


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
CrawlRetryRunner = Callable[..., dict[str, Any]]
MetadataRunner = Callable[..., dict[str, int]]
SummaryRunner = Callable[..., dict[str, Any]]


def create_app(
    database_path: Path | str | None = None,
    crawl_runner: CrawlerRunner = run_live_daily_crawl,
    crawl_retry_runner: CrawlRetryRunner = retry_incomplete_crawl_categories_for_date,
    metadata_runner: MetadataRunner = enrich_metadata_for_date,
    summary_runner: SummaryRunner = generate_summaries_for_date,
) -> FastAPI:
    app = FastAPI(title="arxiv-local-daily")
    db_path = Path(database_path) if database_path is not None else default_settings().database_path
    web_dir = Path(__file__).resolve().parent / "web"
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

    def get_connection():
        connection = connect(db_path)
        initialize_schema(connection)
        return connection

    @app.get("/")
    def web_workbench():
        return FileResponse(web_dir / "index.html")

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

    @app.get("/api/search/papers")
    def search_papers(
        q: str | None = None,
        date: str | None = None,
        category: str | None = None,
        event_type: str | None = None,
        metadata_status: str | None = None,
        summary_status: str | None = None,
        limit: int = 50,
    ):
        connection = get_connection()
        try:
            repo = SearchRepository(connection)
            papers = repo.search_papers(
                query=q,
                date=date,
                category=category,
                event_type=event_type,
                metadata_status=metadata_status,
                summary_status=summary_status,
                limit=limit,
            )
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

    @app.get("/api/crawl/completeness/{date}")
    def get_crawl_completeness(date: str):
        connection = get_connection()
        try:
            return get_crawl_completeness_for_date(connection, date=date)
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

    @app.post("/api/crawl/retry-failed")
    def retry_failed_crawl(request: CrawlRetryFailedRequest):
        connection = get_connection()
        try:
            return crawl_retry_runner(
                connection,
                date=request.date,
                expected_categories=request.expected_categories,
            )
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

    @app.get("/api/papers/{arxiv_id}")
    def get_paper_detail(arxiv_id: str):
        connection = get_connection()
        try:
            detail = SearchRepository(connection).get_paper_detail(arxiv_id)
            if detail is None:
                return {"paper": None, "events": [], "summaries": [], "discussions": []}
            return detail
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

    @app.get("/api/papers/{arxiv_id}/discussions")
    def list_paper_discussions(arxiv_id: str):
        connection = get_connection()
        try:
            repo = DiscussionRepository(connection)
            return {"discussions": repo.list_messages(arxiv_id)}
        finally:
            connection.close()

    @app.post("/api/papers/{arxiv_id}/discussions")
    def create_paper_discussion(arxiv_id: str, message: PaperDiscussionInput):
        connection = get_connection()
        try:
            repo = DiscussionRepository(connection)
            message_id = repo.add_message(arxiv_id, message)
            connection.commit()
            return {"message_id": message_id}
        finally:
            connection.close()

    return app
