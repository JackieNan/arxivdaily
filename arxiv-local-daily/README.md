# arxiv-local-daily

Local-first arXiv daily crawler, SQLite database, AI summary, search, and discussion app.

## Phase 1

Phase 1 provides a runnable local vertical slice:

- offline-tested arXiv daily listing parsing
- SQLite schema and repositories
- daily event ingestion
- versioned summary template persistence
- minimal FastAPI endpoints

The default SQLite database path is `data/arxiv-local-daily.sqlite3`.

## Deferred

These are planned for later versions:

- live all-category daily fetching from arXiv
- arXiv API metadata enrichment
- AI summary workers
- full-text extraction
- complex long-chain paper-reading agents
- production web UI

## Run Tests

```bash
uv run pytest
```

## Run API

```bash
uv run uvicorn arxiv_local_daily.api:create_app --factory --reload
```

The phase-one endpoints are:

- `GET /api/days/{date}/papers`
- `GET /api/crawl/runs/{date}`
- `GET /api/summary-templates`
