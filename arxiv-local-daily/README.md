# arxiv-local-daily

Local-first arXiv daily crawler, SQLite database, AI summary, search, and discussion app.

## Phase 1 Planned Capabilities

Phase 1 is planned to provide:

- offline-tested arXiv daily listing parsing
- SQLite schema and repositories
- daily event ingestion
- summary template persistence
- minimal FastAPI endpoints

## Run Tests

```bash
uv run pytest
```

## Run API

The API command will be available after the Phase 1 API task lands:

```bash
uv run uvicorn arxiv_local_daily.api:create_app --factory --reload
```
