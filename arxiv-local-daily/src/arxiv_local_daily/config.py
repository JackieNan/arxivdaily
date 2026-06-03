from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path("data/arxiv-local-daily.sqlite3")


def default_settings() -> Settings:
    return Settings()
