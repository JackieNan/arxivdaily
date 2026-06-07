from pathlib import Path
from typing import Any, Callable

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from arxiv_local_daily.config import default_settings
from arxiv_local_daily.crawler.live import (
    fetch_current_arxiv_listing_date,
    run_historical_listing_crawl,
    run_live_daily_crawl,
)
from arxiv_local_daily.crawler.preflight import run_daily_listing_preflight
from arxiv_local_daily.db import connect, initialize_schema, transaction
from arxiv_local_daily.models import PaperDiscussionInput, SummaryTemplateInput
from arxiv_local_daily.repositories import (
    CrawlRepository,
    DailyAutomationRepository,
    DiscussionRepository,
    MetadataSyncRepository,
    PreflightRepository,
    SearchRepository,
    SummaryRepository,
    TemplateRepository,
)
from arxiv_local_daily.services import (
    complete_ai_triage_for_date,
    complete_metadata_for_date,
    enrich_metadata_for_date,
    enrich_metadata_for_date_unified,
    generate_ai_triage_for_date,
    generate_ai_triage_for_paper,
    generate_summaries_for_date,
    get_crawl_completeness_for_date,
    get_daily_pipeline_status,
    repair_contaminated_daily_listing_dates,
    retry_incomplete_crawl_categories_for_date,
    run_daily_pipeline,
    run_oai_metadata_sync,
    score_papers_for_date,
)
from arxiv_local_daily.summary import (
    SCORE_KEYS,
    build_ai_triage_messages,
    enabled_template_fields,
    load_llm_api_config,
    llm_api_configured,
    resolve_llm_model,
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
    model: str | None = None
    limit: int | None = None
    force: bool = False


class ScoreRunRequest(BaseModel):
    date: str
    model: str | None = None
    limit: int | None = None
    force: bool = False


class AiTriageRunRequest(BaseModel):
    date: str
    template_id: int | None = None
    template_name: str | None = None
    model: str | None = None
    limit: int | None = None
    force: bool = False
    categories: list[str] | None = None


class AiPromptPreviewRequest(BaseModel):
    arxiv_id: str
    template_id: int | None = None
    template_name: str | None = None
    model: str | None = None


class PaperAiTriageRunRequest(BaseModel):
    template_id: int | None = None
    template_name: str | None = None
    model: str | None = None
    force: bool = False


class DailyPipelineRunRequest(BaseModel):
    date: str
    categories: list[str] | None = None
    expected_categories: list[str] | None = None
    template_id: int | None = None
    template_name: str | None = None
    model: str | None = None
    force_summary: bool = False
    force_score: bool = False
    oai_max_pages: int = Field(default=1, ge=0, le=100)


class DailyAutomationStartRequest(BaseModel):
    date: str
    categories: list[str] | None = None
    crawl_mode: str = "auto"
    force_crawl: bool = False
    batch_size: int = Field(default=100, ge=1, le=500)
    oai_max_pages: int = Field(default=1, ge=0, le=100)
    historical_max_pages: int = Field(default=100, ge=1, le=500)
    template_id: int | None = None
    template_name: str | None = None
    model: str | None = None
    ai_batch_size: int = Field(default=20, ge=1, le=100)


class DailyListingRepairRequest(BaseModel):
    dates: list[str] = Field(min_length=1)


CrawlerRunner = Callable[..., int]
HistoricalCrawlRunner = Callable[..., int]
ArxivDateResolver = Callable[..., str | None]
PreflightRunner = Callable[..., dict[str, Any]]
CrawlRetryRunner = Callable[..., dict[str, Any]]
MetadataRunner = Callable[..., dict[str, Any]]
UnifiedMetadataRunner = Callable[..., dict[str, Any]]
OaiSyncRunner = Callable[..., dict[str, Any]]
SummaryRunner = Callable[..., dict[str, Any]]
ScoreRunner = Callable[..., dict[str, Any]]
AiTriageRunner = Callable[..., dict[str, Any]]
PaperAiTriageRunner = Callable[..., dict[str, Any]]
DailyPipelineRunner = Callable[..., dict[str, Any]]
MetadataCompletionRunner = Callable[..., dict[str, Any]]
AiTriageCompletionRunner = Callable[..., dict[str, Any]]
DailyListingRepairRunner = Callable[..., dict[str, Any]]


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
    categories: list[str] | None = None,
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
            categories=categories,
        )
    finally:
        connection.close()


def _run_daily_automation_background(
    *,
    db_path: Path,
    request: DailyAutomationStartRequest,
    automation_run_id: int | None,
    crawl_runner: CrawlerRunner,
    historical_crawl_runner: HistoricalCrawlRunner,
    arxiv_date_resolver: ArxivDateResolver,
    preflight_runner: PreflightRunner,
    metadata_completion_runner: MetadataCompletionRunner,
    ai_triage_completion_runner: AiTriageCompletionRunner,
) -> None:
    connection = connect(db_path)
    initialize_schema(connection)
    try:
        _update_daily_automation_run(
            connection,
            automation_run_id,
            status="running",
            current_step="arxiv_date_check",
        )
        effective_crawl_mode = request.crawl_mode
        if request.crawl_mode == "auto":
            try:
                arxiv_current_date = arxiv_date_resolver(categories=request.categories)
            except Exception as exc:
                _record_waiting_for_arxiv_update(
                    connection,
                    date=request.date,
                    arxiv_current_date=None,
                    error=f"arXiv current date probe failed: {exc}",
                )
                _update_daily_automation_run(
                    connection,
                    automation_run_id,
                    status="waiting",
                    current_step="waiting_for_arxiv_update",
                    error=f"arXiv current date probe failed: {exc}",
                    finished=True,
                )
                return
            if arxiv_current_date is None or request.date > arxiv_current_date:
                _record_waiting_for_arxiv_update(
                    connection,
                    date=request.date,
                    arxiv_current_date=arxiv_current_date,
                )
                _update_daily_automation_run(
                    connection,
                    automation_run_id,
                    status="waiting",
                    current_step="waiting_for_arxiv_update",
                    error=(
                        f"selected date {request.date} is after arXiv current listing date "
                        f"{arxiv_current_date or 'unknown'}"
                    ),
                    finished=True,
                )
                return
            effective_crawl_mode = "daily" if request.date == arxiv_current_date else "historical"

        if effective_crawl_mode == "daily":
            latest_preflight = PreflightRepository(connection).latest_for_date(request.date)
            if latest_preflight is None or latest_preflight["status"] != "complete":
                _update_daily_automation_run(
                    connection,
                    automation_run_id,
                    status="running",
                    current_step="preflight",
                )
                preflight_runner(connection, date=request.date, categories=request.categories)

        crawl_report = get_crawl_completeness_for_date(
            connection,
            date=request.date,
            expected_categories=request.categories,
        )
        if request.force_crawl or crawl_report["status"] != "complete":
            _update_daily_automation_run(
                connection,
                automation_run_id,
                status="running",
                current_step="crawl",
            )
            if effective_crawl_mode == "historical":
                historical_crawl_runner(
                    connection,
                    date=request.date,
                    categories=request.categories,
                    max_pages=request.historical_max_pages,
                )
            else:
                crawl_runner(connection, date=request.date, categories=request.categories)
            connection.commit()
            crawl_report = get_crawl_completeness_for_date(
                connection,
                date=request.date,
                expected_categories=request.categories,
            )
            if crawl_report["status"] != "complete":
                _update_daily_automation_run(
                    connection,
                    automation_run_id,
                    status="failed",
                    current_step="crawl_incomplete",
                    error=(
                        f"crawl {crawl_report['status']}: "
                        f"{crawl_report['complete_category_count']}/{crawl_report['expected_category_count']} "
                        "categories complete"
                    ),
                    finished=True,
                )
                return
        else:
            _update_daily_automation_run(
                connection,
                automation_run_id,
                status="running",
                current_step="crawl_already_complete",
            )
        _update_daily_automation_run(
            connection,
            automation_run_id,
            status="running",
            current_step="metadata",
        )
        metadata_result = metadata_completion_runner(
            connection,
            date=request.date,
            batch_size=request.batch_size,
            oai_max_pages=request.oai_max_pages,
            max_rounds=None,
            categories=request.categories,
        )
        metadata_complete = metadata_result.get("status") == "complete"
        if metadata_complete:
            _update_daily_automation_run(
                connection,
                automation_run_id,
                status="running",
                current_step="ai",
            )
            ai_triage_completion_runner(
                connection,
                date=request.date,
                template_id=request.template_id,
                template_name=request.template_name,
                model=request.model,
                batch_size=request.ai_batch_size,
                max_rounds=None,
                categories=request.categories,
            )
            _update_daily_automation_run(
                connection,
                automation_run_id,
                status="complete",
                current_step="complete",
                finished=True,
            )
        elif metadata_result.get("status") == "no_papers":
            _update_daily_automation_run(
                connection,
                automation_run_id,
                status="complete",
                current_step="no_papers",
                error="metadata skipped because selected date has no papers",
                finished=True,
            )
        else:
            _update_daily_automation_run(
                connection,
                automation_run_id,
                status="waiting",
                current_step="metadata_waiting",
                error=str(metadata_result.get("status") or "metadata incomplete"),
                finished=True,
            )
    except Exception as exc:
        _update_daily_automation_run(
            connection,
            automation_run_id,
            status="failed",
            current_step="failed",
            error=str(exc),
            finished=True,
        )
        raise
    finally:
        connection.close()


def _update_daily_automation_run(
    connection,
    run_id: int | None,
    *,
    status: str,
    current_step: str,
    error: str | None = None,
    finished: bool = False,
) -> None:
    if run_id is None:
        return
    DailyAutomationRepository(connection).update_run(
        run_id,
        status=status,
        current_step=current_step,
        error=error,
        finished=finished,
    )
    connection.commit()


def _record_waiting_for_arxiv_update(
    connection,
    *,
    date: str,
    arxiv_current_date: str | None,
    error: str | None = None,
) -> None:
    current = arxiv_current_date or "unknown"
    source_error = error or (
        f"selected date {date} is after arXiv current listing date {current}; waiting for arXiv update"
    )
    with transaction(connection):
        crawl_repo = CrawlRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode="arxiv-date-check", status="waiting")
        crawl_repo.record_source(
            run_id=run_id,
            category="arxiv-current-date",
            event_section="new",
            url="https://arxiv.org/list/cs.AI/new",
            status="waiting",
            http_status=200 if arxiv_current_date is not None else None,
            parsed_count=0,
            expected_count=0,
            missing_count=0,
            error=source_error,
        )
        crawl_repo.finish_run(run_id, status="waiting", summary_counts={})


def create_app(
    database_path: Path | str | None = None,
    crawl_runner: CrawlerRunner = run_live_daily_crawl,
    historical_crawl_runner: HistoricalCrawlRunner = run_historical_listing_crawl,
    arxiv_date_resolver: ArxivDateResolver = fetch_current_arxiv_listing_date,
    preflight_runner: PreflightRunner = run_daily_listing_preflight,
    crawl_retry_runner: CrawlRetryRunner = retry_incomplete_crawl_categories_for_date,
    metadata_runner: MetadataRunner = enrich_metadata_for_date,
    unified_metadata_runner: UnifiedMetadataRunner = enrich_metadata_for_date_unified,
    oai_sync_runner: OaiSyncRunner = run_oai_metadata_sync,
    summary_runner: SummaryRunner = generate_summaries_for_date,
    score_runner: ScoreRunner = score_papers_for_date,
    ai_triage_runner: AiTriageRunner = generate_ai_triage_for_date,
    paper_ai_triage_runner: PaperAiTriageRunner = generate_ai_triage_for_paper,
    daily_pipeline_runner: DailyPipelineRunner = run_daily_pipeline,
    metadata_completion_runner: MetadataCompletionRunner = complete_metadata_for_date,
    ai_triage_completion_runner: AiTriageCompletionRunner = complete_ai_triage_for_date,
    daily_listing_repair_runner: DailyListingRepairRunner = repair_contaminated_daily_listing_dates,
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
        page: int = 1,
        page_size: int = 50,
        sort: str = "recent",
    ):
        connection = get_connection()
        try:
            repo = SearchRepository(connection)
            normalized_page = max(page, 1)
            normalized_page_size = max(min(page_size, 200), 1)
            effective_limit = limit if limit is not None else normalized_page_size
            offset = 0 if limit is not None else (normalized_page - 1) * normalized_page_size
            papers = repo.search_papers(
                query=q,
                date=date,
                category=category,
                event_type=event_type,
                metadata_status=metadata_status,
                summary_status=summary_status,
                limit=effective_limit,
                offset=offset,
                sort=sort,
            )
            total = repo.count_search_papers(
                query=q,
                date=date,
                category=category,
                event_type=event_type,
                metadata_status=metadata_status,
                summary_status=summary_status,
            )
            total_pages = max((total + normalized_page_size - 1) // normalized_page_size, 1)
            return {
                "count": len(papers),
                "total": total,
                "page": normalized_page,
                "page_size": normalized_page_size,
                "total_pages": total_pages,
                "has_prev": normalized_page > 1,
                "has_next": normalized_page < total_pages,
                "papers": papers,
            }
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

    @app.get("/api/preflight/{date}")
    def get_preflight(date: str):
        connection = get_connection()
        try:
            report = PreflightRepository(connection).latest_for_date(date)
            if report is None:
                return {
                    "date": date,
                    "status": "not_started",
                    "category_count": 0,
                    "source_count": 0,
                    "listing_entry_count": 0,
                    "distinct_paper_count": 0,
                    "missing_count": 0,
                    "error_counts": {},
                    "sources": [],
                }
            return report
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
                    categories=request.categories,
                )
                response["metadata_completion"] = "queued"
            return response
        finally:
            connection.close()

    @app.post("/api/daily/automation/start")
    def start_daily_automation(request: DailyAutomationStartRequest, background_tasks: BackgroundTasks):
        request.model = resolve_llm_model(request.model)
        connection = get_connection()
        try:
            automation_run_id = DailyAutomationRepository(connection).create_run(
                date=request.date,
                crawl_mode=request.crawl_mode,
                template_name=request.template_name,
                model=request.model,
            )
            connection.commit()
        finally:
            connection.close()
        background_tasks.add_task(
            _run_daily_automation_background,
            db_path=db_path,
            request=request,
            automation_run_id=automation_run_id,
            crawl_runner=crawl_runner,
            historical_crawl_runner=historical_crawl_runner,
            arxiv_date_resolver=arxiv_date_resolver,
            preflight_runner=preflight_runner,
            metadata_completion_runner=metadata_completion_runner,
            ai_triage_completion_runner=ai_triage_completion_runner,
        )
        return {"date": request.date, "status": "queued", "automation_run_id": automation_run_id}

    @app.post("/api/repair/daily-listings")
    def repair_daily_listings(request: DailyListingRepairRequest):
        connection = get_connection()
        try:
            return daily_listing_repair_runner(connection, dates=request.dates)
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

    @app.get("/api/daily/status/{date}")
    def get_daily_status(
        date: str,
        template_id: int | None = None,
        template_name: str | None = None,
        model: str | None = None,
        categories: list[str] | None = Query(default=None),
    ):
        resolved_model = resolve_llm_model(model)
        connection = get_connection()
        try:
            return get_daily_pipeline_status(
                connection,
                date=date,
                template_id=template_id,
                template_name=template_name,
                model=resolved_model,
                expected_categories=categories,
                categories=categories,
            )
        finally:
            connection.close()

    @app.post("/api/daily/pipeline/run")
    def run_daily_pipeline_endpoint(request: DailyPipelineRunRequest):
        model = resolve_llm_model(request.model)
        connection = get_connection()
        try:
            return daily_pipeline_runner(
                connection,
                date=request.date,
                categories=request.categories,
                expected_categories=request.expected_categories,
                template_id=request.template_id,
                template_name=request.template_name,
                model=model,
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
        model = resolve_llm_model(request.model)
        connection = get_connection()
        try:
            return summary_runner(
                connection,
                date=request.date,
                template_id=request.template_id,
                template_name=request.template_name,
                model=model,
                limit=request.limit,
                force=request.force,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            connection.close()

    @app.post("/api/scores/run")
    def run_scores(request: ScoreRunRequest):
        model = resolve_llm_model(request.model)
        connection = get_connection()
        try:
            return score_runner(
                connection,
                date=request.date,
                model=model,
                limit=request.limit,
                force=request.force,
            )
        finally:
            connection.close()

    @app.post("/api/ai-triage/run")
    def run_ai_triage(request: AiTriageRunRequest):
        model = resolve_llm_model(request.model)
        connection = get_connection()
        try:
            return ai_triage_runner(
                connection,
                date=request.date,
                template_id=request.template_id,
                template_name=request.template_name,
                model=model,
                limit=request.limit,
                force=request.force,
                categories=request.categories,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            connection.close()

    @app.get("/api/ai/config")
    def get_ai_config():
        config = load_llm_api_config()
        return {
            "configured": llm_api_configured(),
            "api_key_present": bool(config.api_key),
            "base_url": config.base_url,
            "temperature": f"{config.temperature:g}",
            "config_path": str(config.config_path),
            "config_file_present": config.config_file_present,
            "env": {
                "api_key": "ARXIV_DAILY_LLM_API_KEY",
                "base_url": "ARXIV_DAILY_LLM_BASE_URL",
                "model": "ARXIV_DAILY_LLM_MODEL",
                "temperature": "ARXIV_DAILY_LLM_TEMPERATURE",
                "config": "ARXIV_DAILY_LLM_CONFIG",
            },
        }

    @app.post("/api/ai/prompt-preview")
    def preview_ai_prompt(request: AiPromptPreviewRequest):
        model = resolve_llm_model(request.model)
        connection = get_connection()
        try:
            template = TemplateRepository(connection).get_template(
                template_id=request.template_id,
                name=request.template_name,
            )
            if template is None:
                raise HTTPException(status_code=400, detail="summary template not found")
            paper = SummaryRepository(connection).get_paper_for_summary(request.arxiv_id)
            if paper is None:
                raise HTTPException(status_code=404, detail="paper not found")
            fields = enabled_template_fields(template)
            messages = build_ai_triage_messages(paper=paper, template=template)
            return {
                "model": model,
                "paper": {
                    "arxiv_id": paper["arxiv_id"],
                    "title": paper["title"],
                },
                "template": {
                    "id": int(template["id"]),
                    "name": template["name"],
                    "version": int(template["version"]),
                    "language": template["language"],
                    "input_scope": template["input_scope"],
                },
                "summary_keys": [field["key"] for field in fields],
                "score_keys": SCORE_KEYS,
                "messages": messages,
            }
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

    @app.post("/api/papers/{arxiv_id}/ai-triage/run")
    def run_paper_ai_triage(arxiv_id: str, request: PaperAiTriageRunRequest):
        model = resolve_llm_model(request.model)
        connection = get_connection()
        try:
            return paper_ai_triage_runner(
                connection,
                arxiv_id=arxiv_id,
                template_id=request.template_id,
                template_name=request.template_name,
                model=model,
                force=request.force,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
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
