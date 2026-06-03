from fastapi.testclient import TestClient

from arxiv_local_daily.api import create_app


def test_root_serves_web_workbench(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "web.sqlite3"))

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "arXiv Daily Workbench" in response.text
    assert 'id="crawl-panel"' in response.text
    assert 'id="left-rail"' in response.text
    assert 'id="settings-panel"' in response.text
    assert 'id="search-panel"' in response.text
    assert 'id="right-rail"' in response.text
    assert 'id="paper-detail"' in response.text
    assert 'id="discussion-panel"' in response.text
    assert 'id="enrich-detail"' in response.text
    assert 'id="search-detail"' in response.text
    assert 'id="operation-log"' in response.text
    assert 'id="summary-template-create"' in response.text
    assert 'id="summary-template-help"' in response.text
    assert 'id="metadata-enrich"' in response.text
    assert 'id="score-run"' in response.text
    assert 'id="search-sort"' in response.text
    assert "Settings" in response.text
    assert "Papers to enrich" in response.text


def test_static_web_assets_are_served(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "web.sqlite3"))

    js_response = client.get("/static/app.js")
    css_response = client.get("/static/styles.css")

    assert js_response.status_code == 200
    assert "ArxivDailyWorkbench" in js_response.text
    assert "readErrorMessage" in js_response.text
    assert "DEFAULT_SUMMARY_TEMPLATE" in js_response.text
    assert "loadSummaryTemplates" in js_response.text
    assert "createDefaultTemplate" in js_response.text
    assert "retryable" in js_response.text
    assert "next_run_at" in js_response.text
    assert "runScore" in js_response.text
    assert "/api/metadata/enrich" in js_response.text
    assert "/api/scores/run" in js_response.text
    assert "score-badge" in js_response.text
    assert css_response.status_code == 200
    assert ".app-shell" in css_response.text
    assert ".operation-detail" in css_response.text
    assert ".workspace-grid" in css_response.text
    assert ".paper-card-title" in css_response.text
    assert ".right-rail" in css_response.text
