# arxiv-local-daily

Local-first arXiv daily crawler, SQLite database, AI summary, search, and discussion app.

## Phase 1

Phase 1 provides a runnable local vertical slice:

- offline-tested arXiv daily listing parsing
- SQLite schema and repositories
- daily event ingestion
- versioned summary template persistence
- minimal FastAPI endpoints

## Phase 2

Phase 2 adds live daily crawling:

- arXiv category taxonomy parsing
- retryable arXiv HTTP fetching with a fixed local user agent
- one crawl run with one source row per requested category
- default all-category discovery from `https://arxiv.org/category_taxonomy`
- limited manual category crawls for smoke testing
- `complete` and `partial` crawl status based on per-source success

## Phase 3

Phase 3 adds arXiv API metadata enrichment:

- arXiv API `id_list` URL construction
- Atom feed parsing for modern and legacy arXiv IDs
- title, authors, abstract, category, URL, timestamp, and version persistence
- metadata status transitions to `complete` or `failed`
- manual metadata enrichment through CLI and API

The default SQLite database path is `data/arxiv-local-daily.sqlite3`.

## Deferred

These are planned for later versions:

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
PYTHONPATH=src uv run uvicorn arxiv_local_daily.api:create_app --factory --reload
```

The phase-one endpoints are:

- `GET /api/days/{date}/papers`
- `GET /api/crawl/runs/{date}`
- `GET /api/summary-templates`

## Run Limited Live Crawl

```bash
uv run --with-editable . arxiv-local-daily crawl --date 2026-06-03 --category cs.AI
```

## Run All-Category Live Crawl

```bash
uv run --with-editable . arxiv-local-daily crawl --date 2026-06-03
```

The all-category command discovers categories from arXiv's taxonomy page, then fetches `/list/{category}/new` for every discovered category. A crawl run is `complete` when all requested category pages fetch successfully; it is `partial` when one or more requested sources fail.

The crawl trigger API accepts the same date/category shape:

- `POST /api/crawl/run`

## Run Metadata Enrichment

```bash
uv run --with-editable . arxiv-local-daily metadata --date 2026-06-03 --limit 100
```

Metadata enrichment uses the official arXiv API `id_list` query for crawled paper IDs. Daily crawl events remain in the database even when metadata is missing or failed.

The metadata trigger API accepts the same date/limit shape:

- `POST /api/metadata/run`
