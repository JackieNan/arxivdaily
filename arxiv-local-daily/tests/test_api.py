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
from arxiv_local_daily.repositories import PaperRepository, SummaryRepository, TemplateRepository
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

    client = TestClient(create_app(database_path=db_path, crawl_runner=fake_runner))

    response = client.post(
        "/api/crawl/run",
        json={"date": "2026-06-03", "categories": ["cs.AI", "cs.LG"]},
    )

    assert response.status_code == 200
    assert response.json() == {"run_id": 42}
    assert calls == [("2026-06-03", ["cs.AI", "cs.LG"])]


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


def test_list_summary_templates_starts_empty(tmp_path):
    client = _client_with_seed_data(tmp_path)

    response = client.get("/api/summary-templates")

    assert response.status_code == 200
    assert response.json() == {"templates": []}


def test_post_summary_template_creates_versioned_template(tmp_path):
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

    assert response.status_code == 200
    assert response.json() == {"template_id": 1, "version": 1}


def test_post_summaries_run_uses_injected_runner(tmp_path):
    db_path = tmp_path / "api.sqlite3"
    calls: list[dict] = []

    def fake_summary_runner(connection, *, date: str, template_id: int | None, template_name: str | None, model: str, limit: int, force: bool):
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
