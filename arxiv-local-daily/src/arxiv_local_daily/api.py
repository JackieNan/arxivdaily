from pathlib import Path
from typing import Any, Callable

from fastapi import BackgroundTasks, FastAPI, HTTPException
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
    MetadataSyncRepository,
    SearchRepository,
    SummaryRepository,
    TemplateRepository,
)
from arxiv_local_daily.services import (
    complete_metadata_for_date,
    enrich_metadata_for_date,
    enrich_metadata_for_date_unified,
    generate_summaries_for_date,
    get_crawl_completeness_for_date,
    get_daily_pipeline_status,
    retry_incomplete_crawl_categories_for_date,
    run_daily_pipeline,
    run_oai_metadata_sync,
    score_papers_for_date,
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


class MetadataEnrichRequest(BaseModel):
    date: str
    limit: int = 100
    oai_max_pages: int = Field(default=1, ge=0, le=100)


class OaiMetadataSyncStartRequest(BaseModel):
    from_date: str | None = None
    until_date: str | None = None
    set_spec: str | None = None
    max_pages: int = Field(default=1, ge=0, le=100)


class SummaryRunRequest(BaseModel):
    date: str
    template_id: int | None = None
    template_name: str | None = None
    model: str = "local"
    limit: int | None = None
    force: bool = False


class ScoreRunRequest(BaseModel):
    date: str
    model: str = "local"
    limit: int | None = None
    force: bool = False


class DailyPipelineRunRequest(BaseModel):
    date: str
    categories: list[str] | None = None
    expected_categories: list[str] | None = None
    template_id: int | None = None
    template_name: str | None = None
    model: str = "local"
    force_summary: bool = False
    force_score: bool = False
    oai_max_pages: int = Field(default=1, ge=0, le=100)


class DailyAutomationStartRequest(BaseModel):
    date: str
    categories: list[str] | None = None
    batch_size: int = Field(default=100, ge=1, le=500)
    oai_max_pages: int = Field(default=1, ge=0, le=100)


CrawlerRunner = Callable[..., int]
CrawlRetryRunner = Callable[..., dict[str, Any]]
MetadataRunner = Callable[..., dict[str, Any]]
UnifiedMetadataRunner = Callable[..., dict[str, Any]]
OaiSyncRunner = Callable[..., dict[str, Any]]
SummaryRunner = Callable[..., dict[str, Any]]
ScoreRunner = Callable[..., dict[str, Any]]
DailyPipelineRunner = Callable[..., dict[str, Any]]
MetadataCompletionRunner = Callable[..., dict[str, Any]]


def _run_oai_sync_background(
    *,
    db_path: Path,
    sync_run_id: int,
    request: OaiMetadataSyncStartRequest,
    oai_sync_runner: OaiSyncRunner,
) -> None:
    connection = connect(db_path)
    initialize_schema(connection)
    try:
        oai_sync_runner(
            connection,
            sync_run_id=sync_run_id,
            from_date=request.from_date,
            until_date=request.until_date,
            set_spec=request.set_spec,
            max_pages=request.max_pages,
        )
    finally:
        connection.close()


def _run_metadata_completion_background(
    *,
    db_path: Path,
    date: str,
    metadata_completion_runner: MetadataCompletionRunner,
    batch_size: int = 100,
    oai_max_pages: int = 1,
    max_rounds: int | None = None,
) -> None:
    connection = connect(db_path)
    initialize_schema(connection)
    try:
        metadata_completion_runner(
            connection,
            date=date,
            batch_size=batch_size,
            oai_max_pages=oai_max_pages,
            max_rounds=max_rounds,
        )
    finally:
        connection.close()


def _run_daily_automation_background(
    *,
    db_path: Path,
    request: DailyAutomationStartRequest,
    crawl_runner: CrawlerRunner,
    metadata_completion_runner: MetadataCompletionRunner,
) -> None:
    connection = connect(db_path)
    initialize_schema(connection)
    try:
        crawl_report = get_crawl_completeness_for_date(connection, date=request.date)
        if crawl_report["status"] != "complete":
            crawl_runner(connection, date=request.date, categories=request.categories)
            connection.commit()
        metadata_completion_runner(
            connection,
            date=request.date,
            batch_size=request.batch_size,
            oai_max_pages=request.oai_max_pages,
            max_rounds=None,
        )
    finally:
        connection.close()


def create_app(
    database_path: Path | str | None = None,
    crawl_runner: CrawlerRunner = run_live_daily_crawl,
    crawl_retry_runner: CrawlRetryRunner = retry_incomplete_crawl_categories_for_date,
    metadata_runner: MetadataRunner = enrich_metadata_for_date,
    unified_metadata_runner: UnifiedMetadataRunner = enrich_metadata_for_date_unified,
    oai_sync_runner: OaiSyncRunner = run_oai_metadata_sync,
    summary_runner: SummaryRunner = generate_summaries_for_date,
    score_runner: ScoreRunner = score_papers_for_date,
    daily_pipeline_runner: DailyPipelineRunner = run_daily_pipeline,
    metadata_completion_runner: MetadataCompletionRunner = complete_metadata_for_date,
    auto_enrich_after_crawl: bool = True,
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
        limit: int | None = None,
        sort: str = "recent",
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
                sort=sort,
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
    def run_crawl(request: CrawlRunRequest, background_tasks: BackgroundTasks):
        connection = get_connection()
        try:
            run_id = crawl_runner(
                connection,
                date=request.date,
                categories=request.categories,
            )
            response: dict[str, Any] = {"run_id": run_id}
            if auto_enrich_after_crawl:
                background_tasks.add_task(
                    _run_metadata_completion_background,
                    db_path=db_path,
                    date=request.date,
                    metadata_completion_runner=metadata_completion_runner,
                    batch_size=100,
                    oai_max_pages=1,
                    max_rounds=None,
                )
                response["metadata_completion"] = "queued"
            return response
        finally:
            connection.close()

    @app.post("/api/daily/automation/start")
    def start_daily_automation(request: DailyAutomationStartRequest, background_tasks: BackgroundTasks):
        background_tasks.add_task(
            _run_daily_automation_background,
            db_path=db_path,
            request=request,
            crawl_runner=crawl_runner,
            metadata_completion_runner=metadata_completion_runner,
        )
        return {"date": request.date, "status": "queued"}

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

    @app.get("/api/daily/status/{date}")
    def get_daily_status(
        date: str,
        template_id: int | None = None,
        template_name: str | None = None,
        model: str = "local",
    ):
        connection = get_connection()
        try:
            return get_daily_pipeline_status(
                connection,
                date=date,
                template_id=template_id,
                template_name=template_name,
                model=model,
            )
        finally:
            connection.close()

    @app.post("/api/daily/pipeline/run")
    def run_daily_pipeline_endpoint(request: DailyPipelineRunRequest):
        connection = get_connection()
        try:
            return daily_pipeline_runner(
                connection,
                date=request.date,
                categories=request.categories,
                expected_categories=request.expected_categories,
                template_id=request.template_id,
                template_name=request.template_name,
                model=request.model,
                force_summary=request.force_summary,
                force_score=request.force_score,
                oai_max_pages=request.oai_max_pages,
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

    @app.post("/api/metadata/enrich")
    def enrich_metadata(request: MetadataEnrichRequest):
        connection = get_connection()
        try:
            return unified_metadata_runner(
                connection,
                date=request.date,
                limit=request.limit,
                oai_max_pages=request.oai_max_pages,
            )
        finally:
            connection.close()

    @app.post("/api/metadata/oai-sync/start")
    def start_oai_metadata_sync(request: OaiMetadataSyncStartRequest, background_tasks: BackgroundTasks):
        connection = get_connection()
        try:
            repo = MetadataSyncRepository(connection)
            run_id = repo.create_run(
                source="oai-pmh",
                from_date=request.from_date,
                until_date=request.until_date,
                set_spec=request.set_spec,
                max_pages=request.max_pages,
            )
            connection.commit()
            background_tasks.add_task(
                _run_oai_sync_background,
                db_path=db_path,
                sync_run_id=run_id,
                request=request,
                oai_sync_runner=oai_sync_runner,
            )
            return {"run_id": run_id, "status": "queued"}
        finally:
            connection.close()

    @app.get("/api/metadata/oai-sync/runs")
    def list_oai_metadata_sync_runs(limit: int = 20):
        connection = get_connection()
        try:
            repo = MetadataSyncRepository(connection)
            return {"runs": repo.list_runs(limit=limit)}
        finally:
            connection.close()

    @app.get("/api/metadata/oai-sync/runs/{run_id}")
    def get_oai_metadata_sync_run(run_id: int):
        connection = get_connection()
        try:
            repo = MetadataSyncRepository(connection)
            return {"run": repo.get_run(run_id)}
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
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            connection.close()

    @app.post("/api/scores/run")
    def run_scores(request: ScoreRunRequest):
        connection = get_connection()
        try:
            return score_runner(
                connection,
                date=request.date,
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
