from collections.abc import Iterator
from pathlib import Path

import pytest

from arxiv_local_daily.db import connect, initialize_schema


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.sqlite3"


@pytest.fixture
def db(db_path: Path) -> Iterator:
    connection = connect(db_path)
    initialize_schema(connection)
    try:
        yield connection
    finally:
        connection.close()
