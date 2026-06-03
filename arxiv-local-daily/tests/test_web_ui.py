from fastapi.testclient import TestClient

from arxiv_local_daily.api import create_app


def test_root_serves_web_workbench(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "web.sqlite3"))

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "arXiv Daily Workbench" in response.text
    assert 'id="crawl-panel"' in response.text
    assert 'id="search-panel"' in response.text
    assert 'id="paper-detail"' in response.text
    assert 'id="discussion-panel"' in response.text


def test_static_web_assets_are_served(tmp_path):
    client = TestClient(create_app(database_path=tmp_path / "web.sqlite3"))

    js_response = client.get("/static/app.js")
    css_response = client.get("/static/styles.css")

    assert js_response.status_code == 200
    assert "ArxivDailyWorkbench" in js_response.text
    assert css_response.status_code == 200
    assert ".app-shell" in css_response.text
