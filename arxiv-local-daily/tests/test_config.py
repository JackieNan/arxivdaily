from pathlib import Path

from arxiv_local_daily.config import default_settings


def test_default_settings_accepts_database_path_env(monkeypatch) -> None:
    monkeypatch.setenv("ARXIV_DAILY_DATABASE", "/data/arxiv-local-daily.sqlite3")

    assert default_settings().database_path == Path("/data/arxiv-local-daily.sqlite3")
