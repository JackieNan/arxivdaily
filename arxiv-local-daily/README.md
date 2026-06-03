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

## Phase 5

Phase 5 adds crawl completeness auditing:

- daily crawl completeness reports across all runs for a date
- failed category and missing expected-category detection
- retry candidate generation
- manual retry for failed or missing categories through CLI and API

## Phase 6

Phase 6 adds search and discussion:

- local paper search across metadata and summary JSON
- filters for date, category, event type, metadata status, and summary status
- paper detail records with events, summaries, and discussions
- local per-paper discussion messages

## Phase 7

Phase 7 adds a local web workbench:

- FastAPI serves the UI at `/`
- static CSS and JavaScript are served under `/static`
- crawl, audit, retry, summary, score, search, paper detail, and discussion controls are available in one screen
- the UI uses the existing local API and SQLite database

## Phase 8

Phase 8 reduces dependency on the rate-limited legacy arXiv API:

- daily listing titles are stored immediately during crawl
- OAI-PMH ListRecords metadata pages can be synced into SQLite
- metadata sync runs are tracked with status, counts, resumption token, and error
- the web UI starts and polls OAI metadata sync jobs
- legacy `Run Metadata` remains available as a fallback

## Phase 9

Phase 9 unifies metadata enrichment and improves reading triage:

- crawl sources store page-declared counts and become `incomplete` when parsed count is lower
- unified `Enrich Metadata` compares crawled IDs against ID API and OAI metadata sources
- enrichment reports record missing-after-merge, OAI-missing, OAI-extra, and mismatch diagnostics
- paper scores store a 0-100 reading-priority score plus component scores, rationale, and recommended action
- search can sort by score
- the web UI uses left controls, center search results, and a fixed right paper detail panel
- summary templates and scoring controls live in Settings

## Phase 10

Phase 10 makes crawl the only user-facing ingestion action:

- `POST /api/crawl/run` queues unified metadata enrichment in the background after the crawl finishes
- unified enrichment processes all crawled paper IDs for the day by default and merges ID API plus OAI metadata sources
- the web UI removes the Enrich panel, left rail, metadata limits, OAI page controls, summary limit, and score limit
- search shows all matching papers by default instead of forcing a 50-paper UI cap
- the workbench uses a top action strip with a paper list and fixed right detail panel
- long titles, tags, abstracts, LaTeX-like text, and JSON summaries wrap without horizontal page scrolling

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

## Run Web UI

```bash
uv run --with-editable . uvicorn arxiv_local_daily.api:create_app --factory --host 127.0.0.1 --port 8765
```

Then open `http://127.0.0.1:8765/`.

Run Crawl is the main ingestion path. After the crawl finishes, the API queues unified metadata enrichment in the background, checks the crawled daily paper IDs against ID API and OAI metadata sources, merges the most complete metadata into SQLite, and records missing/mismatch diagnostics. Summary and scoring controls live in Settings and run all eligible papers by default.

The phase-one endpoints are:

- `GET /api/days/{date}/papers`
- `GET /api/crawl/runs/{date}`
- `GET /api/crawl/completeness/{date}`
- `POST /api/crawl/retry-failed`
- `POST /api/metadata/enrich`
- `POST /api/metadata/oai-sync/start`
- `GET /api/metadata/oai-sync/runs`
- `GET /api/metadata/oai-sync/runs/{run_id}`
- `GET /api/search/papers`
- `GET /api/papers/{arxiv_id}`
- `GET /api/summary-templates`
- `POST /api/summary-templates`
- `POST /api/summaries/run`
- `POST /api/scores/run`
- `GET /api/papers/{arxiv_id}/summaries`
- `GET /api/papers/{arxiv_id}/discussions`
- `POST /api/papers/{arxiv_id}/discussions`

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

## Audit and Retry Crawl Completeness

Audit a date after a crawl:

```bash
uv run --with-editable . arxiv-local-daily crawl-audit --date 2026-06-03
```

If you know the exact categories you expected, pass them explicitly. Any expected category that has no successful source row is reported in `retry_categories`:

```bash
uv run --with-editable . arxiv-local-daily crawl-audit \
  --date 2026-06-03 \
  --expected-category cs.AI \
  --expected-category cs.LG
```

Retry failed or missing categories:

```bash
uv run --with-editable . arxiv-local-daily crawl-retry-failed --date 2026-06-03
```

The retry command uses the combined audit across all runs for the date. If a later retry completes a category that failed earlier, the audit treats that category as complete.

## Run Metadata Enrichment

Metadata enrichment is normally automatic after `POST /api/crawl/run`. The OAI and legacy metadata endpoints remain available for diagnostics and controlled experiments.

OAI metadata sync:

```bash
curl -X POST http://127.0.0.1:8765/api/metadata/oai-sync/start \
  -H "Content-Type: application/json" \
  -d '{"from_date":"2026-06-03","until_date":"2026-06-03","set_spec":"cs:cs:AI","max_pages":1}'
```

Check sync status:

```bash
curl http://127.0.0.1:8765/api/metadata/oai-sync/runs/1
```

Legacy API fallback:

```bash
uv run --with-editable . arxiv-local-daily metadata --date 2026-06-03 --limit 100
```

The fallback metadata command uses the official arXiv API `id_list` query for crawled paper IDs. Daily crawl events remain in the database even when metadata is missing or failed.

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
  --model local-model
```

Use `--force` to regenerate existing complete summaries for the same template version, model, and input scope. The command processes all eligible papers by default; pass `--limit` only for a controlled diagnostic run.

## Search Papers

Search metadata and persisted summaries:

```bash
uv run --with-editable . arxiv-local-daily search \
  --query "daily triage" \
  --date 2026-06-03 \
  --category cs.AI \
  --summary-status complete
```

The search command returns all matching papers by default as JSON with paper metadata, latest daily event date, event types, listing categories, and summary statuses. Pass `--limit` only when you intentionally want a smaller diagnostic result set.

## Discuss a Paper Locally

Add a discussion message:

```bash
uv run --with-editable . arxiv-local-daily discuss add \
  --arxiv-id 2606.00001 \
  --role user \
  --content "Why is this paper useful?" \
  --tag question
```

List discussion messages:

```bash
uv run --with-editable . arxiv-local-daily discuss list --arxiv-id 2606.00001
```
