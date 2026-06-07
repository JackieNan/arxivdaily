from pathlib import Path

from fastapi.testclient import TestClient

from arxiv_local_daily.api import create_app
from arxiv_local_daily.db import connect, initialize_schema
from arxiv_local_daily.models import (
    CrawlSourceInput,
    PaperMetadata,
    ParsedDailyEvent,
    SummaryTemplateField,
    SummaryTemplateInput,
)
from arxiv_local_daily.repositories import (
    CrawlRepository,
    PaperRepository,
    PreflightRepository,
    SummaryRepository,
    TemplateRepository,
)
from arxiv_local_daily.repositories import MetadataSyncRepository
from arxiv_local_daily.services import ingest_daily_crawl_sources, ingest_daily_listing_html


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


def _seed_ai_ready_paper(db_path: Path) -> int:
    connection = connect(db_path)
    initialize_schema(connection)
    PaperRepository(connection).upsert_daily_event(
        date="2026-06-03",
        event=ParsedDailyEvent(
            arxiv_id="2606.00001",
            event_type="new",
            listing_category="cs.AI",
            primary_category="cs.AI",
            source_url="https://arxiv.org/list/cs.AI/new",
        ),
    )
    PaperRepository(connection).upsert_metadata(
        PaperMetadata(
            arxiv_id="2606.00001",
            title="Structured Summaries for Daily Research",
            abstract="This paper proposes configurable summaries for daily research triage.",
            authors=["Ada Lovelace", "Alan Turing"],
            primary_category="cs.AI",
            categories=["cs.AI", "cs.LG"],
            abs_url="https://arxiv.org/abs/2606.00001",
            pdf_url="https://arxiv.org/pdf/2606.00001",
        )
    )
    template_id = TemplateRepository(connection).create_template(
        SummaryTemplateInput(
            name="daily_research",
            language="Chinese",
            system_prompt="Summarize papers for a Chinese research reading queue.",
            input_scope="abstract",
            is_default=True,
            fields=[
                SummaryTemplateField(
                    key="keywords",
                    label="关键词",
                    order=1,
                    prompt="提炼中文关键词。",
                    field_type="keywords",
                ),
                SummaryTemplateField(
                    key="tldr",
                    label="一句话结论",
                    order=2,
                    prompt="用一句中文概括论文贡献。",
                    field_type="short_sentence",
                ),
            ],
        )
    )
    connection.commit()
    connection.close()
    return template_id


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


def test_get_crawl_runs_includes_source_details(tmp_path):
    client = _client_with_seed_data(tmp_path)

    response = client.get("/api/crawl/runs/2026-06-03")

    assert response.status_code == 200
    data = response.json()
    assert data["runs"][0]["source_count"] == 1
    assert data["runs"][0]["sources"][0]["category"] == "cs.AI"
    assert data["runs"][0]["sources"][0]["parsed_count"] == 3


def test_get_preflight_returns_latest_evidence(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    connection = connect(db_path)
    initialize_schema(connection)
    repo = PreflightRepository(connection)
    run_id = repo.create_run(date="2026-06-03", mode="daily", status="running", category_count=1)
    repo.record_source(
        run_id=run_id,
        category="cs.AI",
        url="https://arxiv.org/list/cs.AI/new",
        status="complete",
        http_status=200,
        listing_date="2026-06-03",
        parsed_count=3,
        expected_count=3,
        distinct_count=3,
        missing_count=0,
        arxiv_ids=["2606.00001", "2606.00002", "2606.00003"],
    )
    repo.finish_run(
        run_id,
        status="complete",
        source_count=1,
        listing_entry_count=3,
        distinct_paper_count=3,
        missing_count=0,
        error_counts={},
    )
    connection.commit()
    connection.close()
    client = TestClient(create_app(database_path=db_path))

    response = client.get("/api/preflight/2026-06-03")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    assert data["distinct_paper_count"] == 3
    assert data["sources"][0]["category"] == "cs.AI"
    assert data["sources"][0]["expected_count"] == 3
    assert data["sources"][0]["arxiv_ids"] == ["2606.00001", "2606.00002", "2606.00003"]


def test_get_crawl_completeness_returns_combined_report(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    connection = connect(db_path)
    initialize_schema(connection)
    html = Path("tests/fixtures/list_cs_ai_new.html").read_text()
    ingest_daily_crawl_sources(
        connection,
        date="2026-06-03",
        mode="all-categories",
        sources=[
            CrawlSourceInput(
                category="cs.AI",
                url="https://arxiv.org/list/cs.AI/new",
                status="complete",
                http_status=200,
                html=html,
            ),
            CrawlSourceInput(
                category="cs.LG",
                url="https://arxiv.org/list/cs.LG/new",
                status="failed",
                http_status=503,
                error="HTTP 503",
            ),
        ],
    )
    connection.close()
    client = TestClient(create_app(database_path=db_path))

    response = client.get("/api/crawl/completeness/2026-06-03")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert data["retry_categories"] == ["cs.LG"]


def test_search_papers_api_returns_pagination_metadata(tmp_path):
    client = _client_with_seed_data(tmp_path)

    response = client.get("/api/search/papers?date=2026-06-03&page=2&page_size=2")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["total"] == 3
    assert data["page"] == 2
    assert data["page_size"] == 2
    assert data["total_pages"] == 2
    assert data["has_prev"] is True
    assert data["has_next"] is False
    assert [paper["arxiv_id"] for paper in data["papers"]] == ["2606.00003"]


def test_post_crawl_retry_failed_uses_injected_runner(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_retry_runner(connection, *, date: str, expected_categories: list[str] | None):
        calls.append({"date": date, "expected_categories": expected_categories})
        return {"run_id": 9, "retried": 1, "categories": ["cs.LG"]}

    client = TestClient(create_app(database_path=db_path, crawl_retry_runner=fake_retry_runner))

    response = client.post(
        "/api/crawl/retry-failed",
        json={"date": "2026-06-03", "expected_categories": ["cs.AI", "cs.LG"]},
    )

    assert response.status_code == 200
    assert response.json() == {"run_id": 9, "retried": 1, "categories": ["cs.LG"]}
    assert calls == [{"date": "2026-06-03", "expected_categories": ["cs.AI", "cs.LG"]}]


def test_post_crawl_run_uses_injected_runner(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[tuple[str, list[str]]] = []

    def fake_runner(connection, *, date: str, categories: list[str]) -> int:
        calls.append((date, categories))
        return 42

    client = TestClient(create_app(database_path=db_path, crawl_runner=fake_runner, auto_enrich_after_crawl=False))

    response = client.post(
        "/api/crawl/run",
        json={"date": "2026-06-03", "categories": ["cs.AI", "cs.LG"]},
    )

    assert response.status_code == 200
    assert response.json() == {"run_id": 42}
    assert calls == [("2026-06-03", ["cs.AI", "cs.LG"])]


def test_post_crawl_run_schedules_auto_metadata_enrich(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    crawl_calls: list[dict] = []
    completion_calls: list[dict] = []

    def fake_crawl_runner(connection, *, date: str, categories: list[str] | None) -> int:
        crawl_calls.append({"date": date, "categories": categories})
        return 42

    def fake_completion_runner(
        connection,
        *,
        date: str,
        batch_size: int,
        oai_max_pages: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        completion_calls.append(
            {
                "date": date,
                "batch_size": batch_size,
                "oai_max_pages": oai_max_pages,
                "max_rounds": max_rounds,
                "categories": categories,
            }
        )
        return {"status": "complete", "metadata": {"total": 0, "complete": 0}}

    client = TestClient(
        create_app(
            database_path=db_path,
            crawl_runner=fake_crawl_runner,
            metadata_completion_runner=fake_completion_runner,
        )
    )

    response = client.post("/api/crawl/run", json={"date": "2026-06-03"})

    assert response.status_code == 200
    assert response.json() == {"run_id": 42, "metadata_completion": "queued"}
    assert crawl_calls == [{"date": "2026-06-03", "categories": None}]
    assert completion_calls == [
        {"date": "2026-06-03", "batch_size": 100, "oai_max_pages": 1, "max_rounds": None, "categories": None}
    ]


def test_post_daily_automation_start_runs_crawl_then_metadata_and_ai_completion(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_crawl_runner(connection, *, date: str, categories: list[str] | None) -> int:
        calls.append({"step": "crawl", "date": date, "categories": categories})
        crawl_repo = CrawlRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode="all-categories", status="running")
        crawl_repo.record_source(
            run_id=run_id,
            category="cs.AI",
            event_section="all",
            url="https://arxiv.org/list/cs.AI/new",
            status="complete",
            http_status=200,
            parsed_count=0,
            expected_count=0,
            missing_count=0,
        )
        crawl_repo.finish_run(run_id, status="complete", summary_counts={})
        return run_id

    def fake_preflight_runner(connection, *, date: str, categories: list[str] | None):
        calls.append({"step": "preflight", "date": date, "categories": categories})
        return {"status": "complete", "distinct_paper_count": 3}

    def fake_completion_runner(
        connection,
        *,
        date: str,
        batch_size: int,
        oai_max_pages: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        calls.append(
            {
                "step": "metadata",
                "date": date,
                "batch_size": batch_size,
                "oai_max_pages": oai_max_pages,
                "categories": categories,
            }
        )
        return {"status": "complete", "metadata": {"total": 0, "complete": 0}}

    def fake_ai_runner(
        connection,
        *,
        date: str,
        template_id: int | None,
        template_name: str | None,
        model: str,
        batch_size: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        calls.append(
            {
                "step": "ai",
                "date": date,
                "template_id": template_id,
                "template_name": template_name,
                "model": model,
                "batch_size": batch_size,
                "max_rounds": max_rounds,
                "categories": categories,
            }
        )
        return {"status": "complete", "summary": {"complete": 0}, "score": {"complete": 0}}

    client = TestClient(
        create_app(
            database_path=db_path,
            crawl_runner=fake_crawl_runner,
            preflight_runner=fake_preflight_runner,
            metadata_completion_runner=fake_completion_runner,
            ai_triage_completion_runner=fake_ai_runner,
        )
    )

    response = client.post(
        "/api/daily/automation/start",
        json={
            "date": "2026-06-04",
            "crawl_mode": "daily",
            "categories": ["cs.AI"],
            "template_name": "daily_research",
            "model": "gpt-test",
            "ai_batch_size": 7,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == "2026-06-04"
    assert payload["status"] == "queued"
    assert isinstance(payload["automation_run_id"], int)
    assert calls == [
        {"step": "preflight", "date": "2026-06-04", "categories": ["cs.AI"]},
        {"step": "crawl", "date": "2026-06-04", "categories": ["cs.AI"]},
        {"step": "metadata", "date": "2026-06-04", "batch_size": 100, "oai_max_pages": 1, "categories": ["cs.AI"]},
        {
            "step": "ai",
            "date": "2026-06-04",
            "template_id": None,
            "template_name": "daily_research",
            "model": "gpt-test",
            "batch_size": 7,
            "max_rounds": None,
            "categories": ["cs.AI"],
        },
    ]
    status_response = client.get("/api/daily/status/2026-06-04?template_name=daily_research&model=gpt-test")
    assert status_response.json()["automation"]["status"] == "complete"
    assert status_response.json()["automation"]["current_step"] == "complete"


def test_post_daily_automation_start_can_run_historical_mode(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_crawl_runner(connection, *, date: str, categories: list[str] | None) -> int:
        calls.append({"step": "crawl", "date": date, "categories": categories})
        crawl_repo = CrawlRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode="all-categories", status="running")
        crawl_repo.record_source(
            run_id=run_id,
            category="cs.AI",
            event_section="all",
            url="https://arxiv.org/list/cs.AI/new",
            status="complete",
            http_status=200,
            parsed_count=0,
            expected_count=0,
            missing_count=0,
        )
        crawl_repo.finish_run(run_id, status="complete", summary_counts={})
        return run_id

    def fake_historical_runner(
        connection,
        *,
        date: str,
        categories: list[str] | None,
        max_pages: int,
    ) -> int:
        calls.append({"step": "historical", "date": date, "categories": categories, "max_pages": max_pages})
        crawl_repo = CrawlRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode="historical-listing", status="running")
        crawl_repo.record_source(
            run_id=run_id,
            category="cs.AI",
            event_section="archive",
            url="https://arxiv.org/list/cs/2606?skip=0&show=2000",
            status="complete",
            http_status=200,
            parsed_count=0,
            expected_count=0,
            missing_count=0,
        )
        crawl_repo.finish_run(run_id, status="complete", summary_counts={})
        return run_id

    def fake_completion_runner(
        connection,
        *,
        date: str,
        batch_size: int,
        oai_max_pages: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        calls.append({"step": "metadata", "date": date, "batch_size": batch_size, "oai_max_pages": oai_max_pages})
        return {"status": "complete", "metadata": {"total": 0, "complete": 0}}

    def fake_ai_runner(
        connection,
        *,
        date: str,
        template_id: int | None,
        template_name: str | None,
        model: str,
        batch_size: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        calls.append({"step": "ai", "date": date, "model": model})
        return {"status": "complete", "summary": {"complete": 0}, "score": {"complete": 0}}

    client = TestClient(
        create_app(
            database_path=db_path,
            crawl_runner=fake_crawl_runner,
            historical_crawl_runner=fake_historical_runner,
            metadata_completion_runner=fake_completion_runner,
            ai_triage_completion_runner=fake_ai_runner,
        )
    )

    response = client.post(
        "/api/daily/automation/start",
        json={
            "date": "2026-06-03",
            "categories": ["cs.AI"],
            "crawl_mode": "historical",
            "historical_max_pages": 9,
            "model": "gpt-test",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == "2026-06-03"
    assert payload["status"] == "queued"
    assert isinstance(payload["automation_run_id"], int)
    assert calls == [
        {"step": "historical", "date": "2026-06-03", "categories": ["cs.AI"], "max_pages": 9},
        {"step": "metadata", "date": "2026-06-03", "batch_size": 100, "oai_max_pages": 1},
        {"step": "ai", "date": "2026-06-03", "model": "gpt-test"},
    ]


def test_post_daily_automation_backfills_preflight_when_crawl_is_already_complete(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    connection = connect(db_path)
    initialize_schema(connection)
    ingest_daily_crawl_sources(
        connection,
        date="2026-06-04",
        mode="all-categories",
        sources=[
            CrawlSourceInput(
                category="cs.AI",
                url="https://arxiv.org/list/cs.AI/new",
                status="complete",
                http_status=200,
                html=Path("tests/fixtures/list_cs_ai_new.html").read_text(),
            )
        ],
    )
    connection.close()
    calls: list[dict] = []

    def fake_preflight_runner(connection, *, date: str, categories: list[str] | None):
        calls.append({"step": "preflight", "date": date, "categories": categories})
        return {"status": "complete", "distinct_paper_count": 3}

    def fake_crawl_runner(connection, *, date: str, categories: list[str] | None) -> int:
        calls.append({"step": "crawl"})
        return 1

    def fake_metadata_runner(
        connection,
        *,
        date: str,
        batch_size: int,
        oai_max_pages: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        calls.append({"step": "metadata", "date": date})
        return {"status": "complete", "metadata": {"total": 3, "complete": 3}}

    def fake_ai_runner(
        connection,
        *,
        date: str,
        template_id: int | None,
        template_name: str | None,
        model: str,
        batch_size: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        calls.append({"step": "ai", "date": date})
        return {"status": "complete"}

    client = TestClient(
        create_app(
            database_path=db_path,
            crawl_runner=fake_crawl_runner,
            preflight_runner=fake_preflight_runner,
            metadata_completion_runner=fake_metadata_runner,
            ai_triage_completion_runner=fake_ai_runner,
        )
    )

    response = client.post(
        "/api/daily/automation/start",
        json={"date": "2026-06-04", "crawl_mode": "daily", "categories": ["cs.AI"]},
    )

    assert response.status_code == 200
    assert calls == [
        {"step": "preflight", "date": "2026-06-04", "categories": ["cs.AI"]},
        {"step": "metadata", "date": "2026-06-04"},
        {"step": "ai", "date": "2026-06-04"},
    ]


def test_post_daily_automation_records_no_papers_as_finished_automation(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_historical_runner(connection, *, date: str, categories: list[str] | None, max_pages: int) -> int:
        calls.append({"step": "historical", "date": date})
        crawl_repo = CrawlRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode="historical-listing", status="running")
        crawl_repo.record_source(
            run_id=run_id,
            category="cs.AI",
            event_section="archive",
            url="https://arxiv.org/list/cs.AI/2606?skip=0&show=2000",
            status="complete",
            http_status=200,
            parsed_count=0,
            expected_count=0,
            missing_count=0,
        )
        crawl_repo.finish_run(run_id, status="complete", summary_counts={})
        return run_id

    def fake_metadata_runner(
        connection,
        *,
        date: str,
        batch_size: int,
        oai_max_pages: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        calls.append({"step": "metadata", "date": date})
        return {"status": "no_papers", "metadata": {"total": 0, "complete": 0}}

    def fake_ai_runner(
        connection,
        *,
        date: str,
        template_id: int | None,
        template_name: str | None,
        model: str,
        batch_size: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        calls.append({"step": "ai", "date": date})
        return {"status": "complete"}

    client = TestClient(
        create_app(
            database_path=db_path,
            historical_crawl_runner=fake_historical_runner,
            metadata_completion_runner=fake_metadata_runner,
            ai_triage_completion_runner=fake_ai_runner,
        )
    )

    response = client.post("/api/daily/automation/start", json={"date": "2026-06-04", "crawl_mode": "historical"})

    assert response.status_code == 200
    assert calls == [
        {"step": "historical", "date": "2026-06-04"},
        {"step": "metadata", "date": "2026-06-04"},
    ]
    status_response = client.get("/api/daily/status/2026-06-04")
    automation = status_response.json()["automation"]
    assert automation["status"] == "complete"
    assert automation["current_step"] == "no_papers"


def test_post_daily_automation_stops_before_metadata_when_historical_crawl_is_partial(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_historical_runner(connection, *, date: str, categories: list[str] | None, max_pages: int) -> int:
        calls.append({"step": "historical", "date": date})
        crawl_repo = CrawlRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode="historical-listing", status="running")
        crawl_repo.record_source(
            run_id=run_id,
            category="cs.AI",
            event_section="archive",
            url="https://arxiv.org/list/cs/2606?skip=0&show=2000",
            status="failed",
            http_status=404,
            parsed_count=0,
            expected_count=None,
            missing_count=0,
            error="historical archive page not found",
        )
        crawl_repo.finish_run(run_id, status="partial", summary_counts={})
        return run_id

    def fake_metadata_runner(
        connection,
        *,
        date: str,
        batch_size: int,
        oai_max_pages: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        calls.append({"step": "metadata", "date": date})
        return {"status": "no_papers", "metadata": {"total": 0, "complete": 0}}

    client = TestClient(
        create_app(
            database_path=db_path,
            historical_crawl_runner=fake_historical_runner,
            metadata_completion_runner=fake_metadata_runner,
        )
    )

    response = client.post("/api/daily/automation/start", json={"date": "2026-06-04", "crawl_mode": "historical"})

    assert response.status_code == 200
    assert calls == [{"step": "historical", "date": "2026-06-04"}]
    status_response = client.get("/api/daily/status/2026-06-04")
    automation = status_response.json()["automation"]
    assert automation["status"] == "failed"
    assert automation["current_step"] == "crawl_incomplete"
    assert "0/1 categories complete" in automation["error"]


def test_post_daily_automation_auto_uses_arxiv_current_date_for_mode_selection(tmp_path, monkeypatch):
    db_path = tmp_path / "api.sqlite3"
    monkeypatch.setenv("ARXIV_DAILY_LLM_CONFIG", str(tmp_path / "missing-llm-config.json"))
    calls: list[dict] = []

    def fake_arxiv_date_resolver(*, categories: list[str] | None):
        calls.append({"step": "date", "categories": categories})
        return "2026-06-05"

    def fake_daily_runner(connection, *, date: str, categories: list[str] | None) -> int:
        calls.append({"step": "daily", "date": date, "categories": categories})
        crawl_repo = CrawlRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode="all-categories", status="running")
        crawl_repo.record_source(
            run_id=run_id,
            category="cs.AI",
            event_section="all",
            url="https://arxiv.org/list/cs.AI/new",
            status="complete",
            http_status=200,
            parsed_count=0,
            expected_count=0,
            missing_count=0,
        )
        crawl_repo.finish_run(run_id, status="complete", summary_counts={})
        return run_id

    def fake_historical_runner(connection, *, date: str, categories: list[str] | None, max_pages: int) -> int:
        calls.append({"step": "historical", "date": date, "categories": categories, "max_pages": max_pages})
        crawl_repo = CrawlRepository(connection)
        run_id = crawl_repo.create_run(date=date, mode="historical-listing", status="running")
        crawl_repo.record_source(
            run_id=run_id,
            category="cs.AI",
            event_section="archive",
            url="https://arxiv.org/list/cs/2606?skip=0&show=2000",
            status="complete",
            http_status=200,
            parsed_count=0,
            expected_count=0,
            missing_count=0,
        )
        crawl_repo.finish_run(run_id, status="complete", summary_counts={})
        return run_id

    def fake_metadata_runner(
        connection,
        *,
        date: str,
        batch_size: int,
        oai_max_pages: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        calls.append({"step": "metadata", "date": date, "categories": categories})
        return {"status": "complete", "metadata": {"total": 0, "complete": 0}}

    def fake_ai_runner(
        connection,
        *,
        date: str,
        template_id: int | None,
        template_name: str | None,
        model: str,
        batch_size: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        calls.append({"step": "ai", "date": date, "model": model, "categories": categories})
        return {"status": "complete", "summary": {"complete": 0}, "score": {"complete": 0}}

    client = TestClient(
        create_app(
            database_path=db_path,
            crawl_runner=fake_daily_runner,
            historical_crawl_runner=fake_historical_runner,
            metadata_completion_runner=fake_metadata_runner,
            ai_triage_completion_runner=fake_ai_runner,
            arxiv_date_resolver=fake_arxiv_date_resolver,
        )
    )

    response = client.post(
        "/api/daily/automation/start",
        json={"date": "2026-06-04", "crawl_mode": "auto", "categories": ["cs.AI"], "historical_max_pages": 7},
    )

    assert response.status_code == 200
    assert calls == [
        {"step": "date", "categories": ["cs.AI"]},
        {"step": "historical", "date": "2026-06-04", "categories": ["cs.AI"], "max_pages": 7},
        {"step": "metadata", "date": "2026-06-04", "categories": ["cs.AI"]},
        {"step": "ai", "date": "2026-06-04", "model": "local", "categories": ["cs.AI"]},
    ]


def test_post_daily_automation_auto_waits_when_selected_date_is_after_arxiv_current_date(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_arxiv_date_resolver(*, categories: list[str] | None):
        calls.append({"step": "date", "categories": categories})
        return "2026-06-05"

    def fake_daily_runner(connection, *, date: str, categories: list[str] | None) -> int:
        calls.append({"step": "daily"})
        return 1

    def fake_metadata_runner(
        connection,
        *,
        date: str,
        batch_size: int,
        oai_max_pages: int,
        max_rounds: int | None,
        categories: list[str] | None = None,
    ):
        calls.append({"step": "metadata"})
        return {"status": "complete"}

    client = TestClient(
        create_app(
            database_path=db_path,
            crawl_runner=fake_daily_runner,
            metadata_completion_runner=fake_metadata_runner,
            arxiv_date_resolver=fake_arxiv_date_resolver,
        )
    )

    response = client.post("/api/daily/automation/start", json={"date": "2026-06-06", "crawl_mode": "auto"})

    assert response.status_code == 200
    connection = connect(db_path)
    try:
        initialize_schema(connection)
        run = connection.execute("SELECT mode, status FROM crawl_runs WHERE date = ?", ("2026-06-06",)).fetchone()
        source = connection.execute(
            "SELECT category, status, error FROM crawl_run_sources WHERE run_id = (SELECT id FROM crawl_runs WHERE date = ?)",
            ("2026-06-06",),
        ).fetchone()
    finally:
        connection.close()
    assert calls == [{"step": "date", "categories": None}]
    assert dict(run) == {"mode": "arxiv-date-check", "status": "waiting"}
    assert source["category"] == "arxiv-current-date"
    assert source["status"] == "waiting"
    assert "2026-06-05" in source["error"]
    status_response = client.get("/api/daily/status/2026-06-06")
    automation = status_response.json()["automation"]
    assert automation["status"] == "waiting"
    assert automation["current_step"] == "waiting_for_arxiv_update"
    assert "2026-06-05" in automation["error"]


def test_post_daily_automation_auto_records_waiting_when_arxiv_date_probe_fails(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_arxiv_date_resolver(*, categories: list[str] | None):
        calls.append({"step": "date", "categories": categories})
        raise RuntimeError("probe timeout")

    def fake_daily_runner(connection, *, date: str, categories: list[str] | None) -> int:
        calls.append({"step": "daily"})
        return 1

    client = TestClient(
        create_app(
            database_path=db_path,
            crawl_runner=fake_daily_runner,
            arxiv_date_resolver=fake_arxiv_date_resolver,
        )
    )

    response = client.post("/api/daily/automation/start", json={"date": "2026-06-06", "crawl_mode": "auto"})

    assert response.status_code == 200
    connection = connect(db_path)
    try:
        initialize_schema(connection)
        run = connection.execute("SELECT mode, status FROM crawl_runs WHERE date = ?", ("2026-06-06",)).fetchone()
        source = connection.execute(
            "SELECT category, status, error FROM crawl_run_sources WHERE run_id = (SELECT id FROM crawl_runs WHERE date = ?)",
            ("2026-06-06",),
        ).fetchone()
    finally:
        connection.close()
    assert calls == [{"step": "date", "categories": None}]
    assert dict(run) == {"mode": "arxiv-date-check", "status": "waiting"}
    assert source["category"] == "arxiv-current-date"
    assert source["status"] == "waiting"
    assert "probe timeout" in source["error"]
    status_response = client.get("/api/daily/status/2026-06-06")
    automation = status_response.json()["automation"]
    assert automation["status"] == "waiting"
    assert automation["current_step"] == "waiting_for_arxiv_update"
    assert "probe timeout" in automation["error"]


def test_post_repair_daily_listings_uses_injected_runner(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_repair_runner(connection, *, dates: list[str]):
        calls.append({"dates": dates})
        return {
            "dates": dates,
            "daily_events_deleted": 9,
            "crawl_runs_deleted": 3,
            "historical_events_preserved": 4,
        }

    client = TestClient(create_app(database_path=db_path, daily_listing_repair_runner=fake_repair_runner))

    response = client.post(
        "/api/repair/daily-listings",
        json={"dates": ["2026-06-03", "2026-06-04"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "dates": ["2026-06-03", "2026-06-04"],
        "daily_events_deleted": 9,
        "crawl_runs_deleted": 3,
        "historical_events_preserved": 4,
    }
    assert calls == [{"dates": ["2026-06-03", "2026-06-04"]}]


def test_get_daily_status_reports_summary_coverage(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    connection = connect(db_path)
    initialize_schema(connection)
    template_id = TemplateRepository(connection).create_template(
        SummaryTemplateInput(
            name="daily_research",
            language="Chinese",
            system_prompt="Return Chinese summaries.",
            input_scope="abstract",
            is_default=True,
            fields=[
                SummaryTemplateField(
                    key="keywords",
                    label="关键词",
                    order=1,
                    prompt="Return Chinese keywords.",
                    field_type="bullets",
                )
            ],
        )
    )
    PaperRepository(connection).upsert_daily_event(
        date="2026-06-03",
        event=ParsedDailyEvent(
            arxiv_id="2606.00001",
            event_type="new",
            listing_category="cs.AI",
            primary_category="cs.AI",
            source_url="https://arxiv.org/list/cs.AI/new",
        ),
    )
    PaperRepository(connection).upsert_metadata(
        PaperMetadata(
            arxiv_id="2606.00001",
            title="Daily Summary Coverage",
            abstract="Daily status should include summary coverage.",
            authors=["Ada Lovelace"],
            primary_category="cs.AI",
            categories=["cs.AI"],
        )
    )
    SummaryRepository(connection).upsert_summary(
        arxiv_id="2606.00001",
        template_id=template_id,
        template_version=1,
        model="fake-model",
        language="Chinese",
        input_scope="abstract",
        content={"keywords": ["每日状态"]},
        status="complete",
    )
    connection.commit()
    connection.close()
    client = TestClient(create_app(database_path=db_path))

    response = client.get("/api/daily/status/2026-06-03?template_id=1&model=fake-model")

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["complete"] == 1
    assert data["summary"]["missing"] == 0
    assert data["summary"]["required_fields"] == ["keywords"]


def test_post_daily_pipeline_run_uses_injected_runner(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_daily_pipeline_runner(
        connection,
        *,
        date: str,
        categories: list[str] | None,
        expected_categories: list[str] | None,
        template_id: int | None,
        template_name: str | None,
        model: str,
        force_summary: bool,
        force_score: bool,
        oai_max_pages: int,
    ):
        calls.append(
            {
                "date": date,
                "categories": categories,
                "expected_categories": expected_categories,
                "template_id": template_id,
                "template_name": template_name,
                "model": model,
                "force_summary": force_summary,
                "force_score": force_score,
                "oai_max_pages": oai_max_pages,
            }
        )
        return {"date": date, "status": "complete", "steps": {}, "daily_status": {"status": "complete"}}

    client = TestClient(create_app(database_path=db_path, daily_pipeline_runner=fake_daily_pipeline_runner))

    response = client.post(
        "/api/daily/pipeline/run",
        json={
            "date": "2026-06-03",
            "categories": ["cs.AI"],
            "expected_categories": ["cs.AI"],
            "template_id": 1,
            "model": "fake-model",
            "force_summary": True,
            "force_score": True,
            "oai_max_pages": 2,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "complete"
    assert calls == [
        {
            "date": "2026-06-03",
            "categories": ["cs.AI"],
            "expected_categories": ["cs.AI"],
            "template_id": 1,
            "template_name": None,
            "model": "fake-model",
            "force_summary": True,
            "force_score": True,
            "oai_max_pages": 2,
        }
    ]


def test_post_ai_triage_run_uses_injected_runner(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_ai_runner(
        connection,
        *,
        date: str,
        template_id: int | None,
        template_name: str | None,
        model: str,
        limit: int | None,
        force: bool,
        categories: list[str] | None = None,
    ):
        calls.append(
            {
                "date": date,
                "template_id": template_id,
                "template_name": template_name,
                "model": model,
                "limit": limit,
                "force": force,
                "categories": categories,
            }
        )
        return {"requested": 2, "completed": 2, "failed": 0, "skipped": 0}

    client = TestClient(create_app(database_path=db_path, ai_triage_runner=fake_ai_runner))

    response = client.post(
        "/api/ai-triage/run",
        json={
            "date": "2026-06-03",
            "template_name": "daily_research",
            "model": "gpt-test",
            "force": True,
            "categories": ["cs.AI", "cs.LG"],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"requested": 2, "completed": 2, "failed": 0, "skipped": 0}
    assert calls == [
        {
            "date": "2026-06-03",
            "template_id": None,
            "template_name": "daily_research",
            "model": "gpt-test",
            "limit": None,
            "force": True,
            "categories": ["cs.AI", "cs.LG"],
        }
    ]


def test_post_ai_triage_run_uses_config_model_when_request_omits_model(tmp_path, monkeypatch):
    db_path = tmp_path / "api.sqlite3"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "llm.local.json").write_text(
        '{"base_url":"https://llm.example.test/v1","api_key":"sk-local-secret","model":"deepseek-v4-pro"}'
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ARXIV_DAILY_LLM_MODEL", raising=False)
    calls: list[dict] = []

    def fake_ai_runner(
        connection,
        *,
        date: str,
        template_id: int | None,
        template_name: str | None,
        model: str,
        limit: int | None,
        force: bool,
        categories: list[str] | None = None,
    ):
        calls.append({"date": date, "model": model})
        return {"requested": 0, "completed": 0, "failed": 0, "skipped": 0}

    client = TestClient(create_app(database_path=db_path, ai_triage_runner=fake_ai_runner))

    response = client.post("/api/ai-triage/run", json={"date": "2026-06-03"})

    assert response.status_code == 200
    assert calls == [{"date": "2026-06-03", "model": "deepseek-v4-pro"}]


def test_get_ai_config_reports_masked_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ARXIV_DAILY_LLM_CONFIG", str(tmp_path / "missing-llm-config.json"))
    monkeypatch.setenv("ARXIV_DAILY_LLM_API_KEY", "sk-test-secret")
    monkeypatch.setenv("ARXIV_DAILY_LLM_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("ARXIV_DAILY_LLM_TEMPERATURE", "0.2")
    client = TestClient(create_app(database_path=tmp_path / "api.sqlite3"))

    response = client.get("/api/ai/config")

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["api_key_present"] is True
    assert data["base_url"] == "https://llm.example.test/v1"
    assert data["temperature"] == "0.2"
    assert data["config_file_present"] is False
    assert data["env"] == {
        "api_key": "ARXIV_DAILY_LLM_API_KEY",
        "base_url": "ARXIV_DAILY_LLM_BASE_URL",
        "model": "ARXIV_DAILY_LLM_MODEL",
        "temperature": "ARXIV_DAILY_LLM_TEMPERATURE",
        "config": "ARXIV_DAILY_LLM_CONFIG",
    }
    assert "sk-test-secret" not in str(data)


def test_get_ai_config_reports_masked_local_config_file(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "llm.local.json").write_text(
        """
        {
          "base_url": "https://llm.example.test/v1",
          "api_key": "sk-local-secret",
          "model": "deepseek-v4-pro",
          "temperature": 0.2
        }
        """
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ARXIV_DAILY_LLM_API_KEY", raising=False)
    monkeypatch.delenv("ARXIV_DAILY_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ARXIV_DAILY_LLM_MODEL", raising=False)
    monkeypatch.delenv("ARXIV_DAILY_LLM_TEMPERATURE", raising=False)
    client = TestClient(create_app(database_path=tmp_path / "api.sqlite3"))

    response = client.get("/api/ai/config")

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["api_key_present"] is True
    assert data["base_url"] == "https://llm.example.test/v1"
    assert data["temperature"] == "0.2"
    assert data["config_file_present"] is True
    assert data["config_path"].endswith("config/llm.local.json")
    assert "sk-local-secret" not in str(data)


def test_post_ai_prompt_preview_returns_messages(tmp_path, monkeypatch):
    db_path = tmp_path / "api.sqlite3"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "summary_template.local.json").write_text(
        """
        {
          "language": "Chinese",
          "system_prompt": "Use the local single template.",
          "input_scope": "abstract",
          "fields": [
            {
              "key": "keywords",
              "label": "关键词",
              "order": 1,
              "prompt": "提炼本地配置关键词。",
              "field_type": "keywords",
              "enabled": true
            }
          ]
        }
        """
    )
    monkeypatch.chdir(tmp_path)
    _seed_ai_ready_paper(db_path)
    client = TestClient(create_app(database_path=db_path))

    response = client.post(
        "/api/ai/prompt-preview",
        json={"arxiv_id": "2606.00001", "model": "gpt-test"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "gpt-test"
    assert data["paper"] == {
        "arxiv_id": "2606.00001",
        "title": "Structured Summaries for Daily Research",
    }
    assert data["template"]["source"] == "config"
    assert data["summary_keys"] == ["keywords"]
    assert "score_total" in data["score_keys"]
    assert [message["role"] for message in data["messages"]] == ["system", "user"]
    assert "Structured Summaries for Daily Research" in data["messages"][1]["content"]
    assert "提炼本地配置关键词" in data["messages"][1]["content"]


def test_post_paper_ai_triage_run_uses_injected_runner(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_paper_ai_runner(
        connection,
        *,
        arxiv_id: str,
        template_id: int | None,
        template_name: str | None,
        model: str,
        force: bool,
    ):
        calls.append(
            {
                "arxiv_id": arxiv_id,
                "template_id": template_id,
                "template_name": template_name,
                "model": model,
                "force": force,
            }
        )
        return {
            "status": "complete",
            "arxiv_id": arxiv_id,
            "requested": 1,
            "completed": 1,
            "failed": 0,
            "skipped": 0,
        }

    client = TestClient(create_app(database_path=db_path, paper_ai_triage_runner=fake_paper_ai_runner))

    response = client.post(
        "/api/papers/2606.00001/ai-triage/run",
        json={"template_name": "daily_research", "model": "gpt-test", "force": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "complete"
    assert calls == [
        {
            "arxiv_id": "2606.00001",
            "template_id": None,
            "template_name": "daily_research",
            "model": "gpt-test",
            "force": True,
        }
    ]


def test_post_metadata_run_uses_injected_runner(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[tuple[str, int]] = []

    def fake_metadata_runner(connection, *, date: str, limit: int):
        calls.append((date, limit))
        return {"requested": 2, "updated": 2, "missing": 0, "failed": 0}

    client = TestClient(create_app(database_path=db_path, metadata_runner=fake_metadata_runner))

    response = client.post("/api/metadata/run", json={"date": "2026-06-03", "limit": 2})

    assert response.status_code == 200
    assert response.json() == {"requested": 2, "updated": 2, "missing": 0, "failed": 0}
    assert calls == [("2026-06-03", 2)]


def test_post_metadata_enrich_uses_injected_unified_runner(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_unified_runner(connection, *, date: str, limit: int, oai_max_pages: int):
        calls.append({"date": date, "limit": limit, "oai_max_pages": oai_max_pages})
        return {"run_id": 3, "status": "complete", "merged": 2}

    client = TestClient(create_app(database_path=db_path, unified_metadata_runner=fake_unified_runner))

    response = client.post("/api/metadata/enrich", json={"date": "2026-06-03", "limit": 2, "oai_max_pages": 1})

    assert response.status_code == 200
    assert response.json() == {"run_id": 3, "status": "complete", "merged": 2}
    assert calls == [{"date": "2026-06-03", "limit": 2, "oai_max_pages": 1}]


def test_post_scores_run_uses_injected_runner(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_score_runner(connection, *, date: str, model: str, limit: int, force: bool):
        calls.append({"date": date, "model": model, "limit": limit, "force": force})
        return {"requested": 1, "completed": 1, "failed": 0, "skipped": 0}

    client = TestClient(create_app(database_path=db_path, score_runner=fake_score_runner))

    response = client.post("/api/scores/run", json={"date": "2026-06-03", "model": "score-model", "limit": 1, "force": True})

    assert response.status_code == 200
    assert response.json()["completed"] == 1
    assert calls == [{"date": "2026-06-03", "model": "score-model", "limit": 1, "force": True}]


def test_post_oai_metadata_sync_start_creates_background_run(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_oai_sync_runner(
        connection,
        *,
        sync_run_id: int,
        from_date: str | None,
        until_date: str | None,
        set_spec: str | None,
        max_pages: int,
    ):
        calls.append(
            {
                "sync_run_id": sync_run_id,
                "from_date": from_date,
                "until_date": until_date,
                "set_spec": set_spec,
                "max_pages": max_pages,
            }
        )
        repo = MetadataSyncRepository(connection)
        repo.mark_running(sync_run_id)
        repo.finish_run(
            sync_run_id,
            status="complete",
            records_seen=0,
            records_upserted=0,
            pages_fetched=0,
        )
        connection.commit()
        return {"sync_run_id": sync_run_id, "status": "complete"}

    client = TestClient(create_app(database_path=db_path, oai_sync_runner=fake_oai_sync_runner))

    response = client.post(
        "/api/metadata/oai-sync/start",
        json={
            "from_date": "2026-06-03",
            "until_date": "2026-06-03",
            "set_spec": "cs:cs:AI",
            "max_pages": 2,
        },
    )
    run_id = response.json()["run_id"]
    status_response = client.get(f"/api/metadata/oai-sync/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert calls == [
        {
            "sync_run_id": run_id,
            "from_date": "2026-06-03",
            "until_date": "2026-06-03",
            "set_spec": "cs:cs:AI",
            "max_pages": 2,
        }
    ]
    assert status_response.status_code == 200
    assert status_response.json()["run"]["status"] == "complete"


def test_list_summary_templates_endpoint_is_removed(tmp_path):
    client = _client_with_seed_data(tmp_path)

    response = client.get("/api/summary-templates")

    assert response.status_code == 404


def test_post_summary_template_endpoint_is_removed(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    client = TestClient(create_app(database_path=db_path))

    response = client.post(
        "/api/summary-templates",
        json={
            "name": "daily_research",
            "language": "Chinese",
            "system_prompt": "Summarize with the configured structure.",
            "input_scope": "abstract",
            "is_default": True,
            "fields": [
                {
                    "key": "tldr",
                    "label": "一句话结论",
                    "order": 1,
                    "prompt": "Give one sentence.",
                    "field_type": "short_sentence",
                    "enabled": True,
                }
            ],
        },
    )

    assert response.status_code == 404


def test_post_summaries_run_uses_injected_runner(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_summary_runner(connection, *, date: str, template_id: int | None, template_name: str | None, model: str, limit: int | None, force: bool):
        calls.append(
            {
                "date": date,
                "template_id": template_id,
                "template_name": template_name,
                "model": model,
                "limit": limit,
                "force": force,
            }
        )
        return {"requested": 2, "completed": 2, "failed": 0, "skipped": 0, "template_id": template_id, "template_version": 1}

    client = TestClient(create_app(database_path=db_path, summary_runner=fake_summary_runner))

    response = client.post(
        "/api/summaries/run",
        json={"date": "2026-06-03", "template_id": 7, "model": "fake-model", "limit": 2, "force": True},
    )

    assert response.status_code == 200
    assert response.json()["completed"] == 2
    assert calls == [
        {
            "date": "2026-06-03",
            "template_id": 7,
            "template_name": None,
            "model": "fake-model",
            "limit": 2,
            "force": True,
        }
    ]


def test_post_summaries_run_returns_detail_when_template_missing(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    client = TestClient(create_app(database_path=db_path), raise_server_exceptions=False)

    response = client.post("/api/summaries/run", json={"date": "2026-06-03", "template_name": "missing"})

    assert response.status_code == 400
    assert response.json() == {"detail": "summary template not found"}


def test_get_paper_summaries_returns_persisted_content(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    connection = connect(db_path)
    initialize_schema(connection)
    paper_repo = PaperRepository(connection)
    paper_repo.upsert_daily_event(
        date="2026-06-03",
        event=ParsedDailyEvent(
            arxiv_id="2606.00001",
            event_type="new",
            listing_category="cs.AI",
            primary_category="cs.AI",
            source_url="https://arxiv.org/list/cs.AI/new",
        ),
    )
    paper_repo.upsert_metadata(
        PaperMetadata(
            arxiv_id="2606.00001",
            title="Structured Summaries",
            abstract="Abstract.",
            authors=["Ada Lovelace"],
            primary_category="cs.AI",
            categories=["cs.AI"],
        )
    )
    template_id = TemplateRepository(connection).create_template(
        SummaryTemplateInput(
            name="daily_research",
            language="Chinese",
            system_prompt="Summarize.",
            input_scope="abstract",
            fields=[
                SummaryTemplateField(
                    key="tldr",
                    label="一句话结论",
                    order=1,
                    prompt="Give one sentence.",
                    field_type="short_sentence",
                )
            ],
        )
    )
    SummaryRepository(connection).upsert_summary(
        arxiv_id="2606.00001",
        template_id=template_id,
        template_version=1,
        model="fake-model",
        language="Chinese",
        input_scope="abstract",
        content={"tldr": "Stored summary."},
        status="complete",
    )
    connection.commit()
    connection.close()
    client = TestClient(create_app(database_path=db_path))

    response = client.get("/api/papers/2606.00001/summaries")

    assert response.status_code == 200
    data = response.json()
    assert data["summaries"][0]["content"] == {"tldr": "Stored summary."}
    assert data["summaries"][0]["status"] == "complete"


def _seed_search_api_data(db_path: Path) -> None:
    connection = connect(db_path)
    initialize_schema(connection)
    paper_repo = PaperRepository(connection)
    paper_repo.upsert_daily_event(
        date="2026-06-03",
        event=ParsedDailyEvent(
            arxiv_id="2606.00001",
            event_type="new",
            listing_category="cs.AI",
            primary_category="cs.AI",
            source_url="https://arxiv.org/list/cs.AI/new",
        ),
    )
    paper_repo.upsert_metadata(
        PaperMetadata(
            arxiv_id="2606.00001",
            title="Structured Summaries for Daily Research",
            abstract="Configurable summaries help daily research triage.",
            authors=["Ada Lovelace"],
            primary_category="cs.AI",
            categories=["cs.AI"],
        )
    )
    template_id = TemplateRepository(connection).create_template(
        SummaryTemplateInput(
            name="daily_research",
            language="Chinese",
            system_prompt="Summarize.",
            input_scope="abstract",
            fields=[
                SummaryTemplateField(
                    key="tldr",
                    label="一句话结论",
                    order=1,
                    prompt="Give one sentence.",
                    field_type="short_sentence",
                )
            ],
        )
    )
    SummaryRepository(connection).upsert_summary(
        arxiv_id="2606.00001",
        template_id=template_id,
        template_version=1,
        model="fake-model",
        language="Chinese",
        input_scope="abstract",
        content={"tldr": "Daily triage summary."},
        status="complete",
    )
    connection.commit()
    connection.close()


def test_search_papers_api_returns_filtered_results(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    _seed_search_api_data(db_path)
    client = TestClient(create_app(database_path=db_path))

    response = client.get(
        "/api/search/papers",
        params={"q": "daily triage", "date": "2026-06-03", "category": "cs.AI"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["papers"][0]["arxiv_id"] == "2606.00001"


def test_get_paper_detail_api_returns_nested_records(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    _seed_search_api_data(db_path)
    client = TestClient(create_app(database_path=db_path))

    response = client.get("/api/papers/2606.00001")

    assert response.status_code == 200
    data = response.json()
    assert data["paper"]["arxiv_id"] == "2606.00001"
    assert data["events"][0]["event_type"] == "new"
    assert data["summaries"][0]["content"] == {"tldr": "Daily triage summary."}


def test_paper_discussions_api_adds_and_lists_messages(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    _seed_search_api_data(db_path)
    client = TestClient(create_app(database_path=db_path))

    create_response = client.post(
        "/api/papers/2606.00001/discussions",
        json={"role": "user", "content": "Why is this paper useful?", "tags": ["question"]},
    )
    list_response = client.get("/api/papers/2606.00001/discussions")

    assert create_response.status_code == 200
    assert create_response.json()["message_id"] == 1
    assert list_response.status_code == 200
    assert list_response.json()["discussions"][0]["content"] == "Why is this paper useful?"
    assert list_response.json()["discussions"][0]["tags"] == ["question"]
