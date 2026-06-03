from pathlib import Path

from fastapi.testclient import TestClient

from arxiv_local_daily.api import create_app
from arxiv_local_daily.db import connect, initialize_schema
from arxiv_local_daily.services import ingest_daily_listing_html


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
