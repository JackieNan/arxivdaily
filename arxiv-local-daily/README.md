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

## Phase 4

Phase 4 adds configurable AI summary generation:

- user-editable summary templates with versioned fields
- structured prompt construction from paper metadata and enabled template fields
- strict JSON response parsing into custom summary sections
- summary persistence by paper, template version, model, and input scope
- manual summary generation through CLI and API

The default SQLite database path is `data/arxiv-local-daily.sqlite3`.

## Deferred

These are planned for later versions:

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
- `POST /api/summary-templates`
- `POST /api/summaries/run`
- `GET /api/papers/{arxiv_id}/summaries`

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

## Customize Summary Structure

Create a JSON template file with the sections you want:

```json
{
  "name": "daily_research",
  "language": "Chinese",
  "system_prompt": "Summarize the paper for a local research reading database.",
  "input_scope": "abstract",
  "is_default": true,
  "fields": [
    {
      "key": "tldr",
      "label": "一句话结论",
      "order": 1,
      "prompt": "Give one sentence about the main result.",
      "field_type": "short_sentence",
      "enabled": true
    },
    {
      "key": "method",
      "label": "核心方法",
      "order": 2,
      "prompt": "Explain the core method in two bullets.",
      "field_type": "bullets",
      "enabled": true
    }
  ]
}
```

Importing a template with the same `name` creates a new version:

```bash
uv run --with-editable . arxiv-local-daily template import --file template.json
```

## Run AI Summary Generation

The summary worker calls an OpenAI-compatible chat-completions endpoint. Configure it with environment variables:

```bash
export ARXIV_DAILY_LLM_BASE_URL="http://localhost:11434/v1"
export ARXIV_DAILY_LLM_API_KEY=""
```

Then generate summaries for metadata-enriched papers from one daily crawl:

```bash
uv run --with-editable . arxiv-local-daily summarize \
  --date 2026-06-03 \
  --template-name daily_research \
  --model local-model \
  --limit 20
```

Use `--force` to regenerate existing complete summaries for the same template version, model, and input scope.
