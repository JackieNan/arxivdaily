# arXiv Local Daily App Design

Date: 2026-06-03

## Goal

Build a local-first app that crawls arXiv daily papers, stores them in a local database, and supports AI summaries, search, querying, and discussion. The most important requirement is stable, auditable, near-complete crawling of the day's arXiv daily listing.

The confirmed v1 scope is:

- Crawl all arXiv categories, not only configured categories.
- Store `new`, `cross-list`, and `replacement` daily listing events.
- Make AI processing configurable. By default, crawl and metadata ingestion complete first; AI work runs asynchronously. A manual mode can wait for all selected AI jobs.
- Do not download every paper's PDF or source by default. Full text is fetched on demand for selected, favorited, or discussion-triggered papers.
- Support customizable, versioned AI summary templates.
- Include a complex paper-reading agent in v1 as a manually triggered queued workflow, not as a default all-paper daily task.

## Existing Project Context

The workspace contains two useful reference projects:

- `daily-arXiv-ai-enhanced`: Scrapy-based arXiv daily list crawling, JSONL output, static browser reading UI, structured LLM summary generation, markdown publishing.
- `zotero-arxiv-daily`: Retriever/reranker architecture, arXiv RSS and API metadata enrichment, retry/rate-limit handling, LLM TLDR, full-text extraction, embedding-based recommendation, email rendering.

The new app should be a separate project, tentatively `arxiv-local-daily/`. The two existing projects should remain intact. Reuse patterns and small portable code only when it simplifies implementation.

## Recommended Architecture

Create an independent local app with five layers.

### Crawler

The crawler enumerates the full arXiv taxonomy/category list and fetches the daily listing page for every category. It parses all daily event types:

- `new`
- `cross-list`
- `replacement`

Every source URL and parse result is recorded in a crawl manifest. The crawler treats complete enumeration and event persistence as the primary success condition.

### Database

Use SQLite for v1. It is stable, local, simple to back up, and adequate for daily arXiv scale. The schema should not hard-code one embedding provider or summary format.

### Workers

Use SQLite-backed worker queues for asynchronous work:

- metadata enrichment
- abstract summary
- embedding
- full-text fetch and extraction
- full-text summary
- deep paper-reading agent

Workers must be resumable. A failed AI or full-text job must not make the day's crawl fail.

### API

Use FastAPI to expose crawl operations, paper search, paper detail, job control, AI summaries, and chat.

### Web UI

Build a local web workbench rather than a landing page. The first screen is the daily paper table with crawl health and filters.

## Data Flow

### Stage 1: Daily Enumeration

For a selected date, the crawler:

1. Loads the arXiv category taxonomy.
2. Fetches every category's daily listing page.
3. Parses `new`, `cross-list`, and `replacement` sections.
4. Inserts daily events immediately, even before metadata enrichment.
5. Records per-source status, HTTP result, parse count, retry count, and errors.

If an arXiv ID is seen multiple times across categories or event types, the app stores one canonical paper row and multiple `daily_events` rows.

### Stage 2: Metadata Enrichment

After event IDs are persisted, the app uses the arXiv API in batches to fill metadata:

- title
- authors
- abstract
- primary category
- all categories
- abs URL
- PDF URL
- published timestamp
- updated timestamp
- version data where available

If the arXiv API returns 429 or fails, the ID and event remain in the database with metadata status `pending`. Metadata enrichment is retried later.

### Stage 3: AI and Full-Text Work

By default, the app queues low-cost abstract summaries and optional embeddings. Full text is only fetched for selected, favorited, manually triggered, or discussion-triggered papers.

Manual "wait for AI completion" mode starts workers and blocks until jobs for the selected date or filter are completed, failed beyond retry policy, or explicitly cancelled.

## Completeness and Audit Strategy

The app does not claim mathematically perfect crawling. It provides auditable completeness:

- Which categories were requested.
- Which URLs succeeded or failed.
- Which event sections were parsed.
- Counts by category and event type.
- Papers with only ID but missing metadata.
- Pending or failed AI jobs.
- Failed full-text extraction jobs.

A daily crawl run has status:

- `complete`: every category source was fetched and parsed successfully.
- `partial`: one or more category sources failed, parsed suspiciously, or were skipped.
- `failed`: the run could not persist usable daily events.

Reruns should support:

- full date rerun
- only failed sources
- only missing metadata
- only selected AI jobs

The default daily success definition is: all category daily listing pages were fetched, parsed, and daily events were persisted. Metadata and AI may remain pending.

## Database Model

### Core Tables

`papers`

- `arxiv_id` unique key
- `title`
- `abstract`
- `authors_json`
- `primary_category`
- `categories_json`
- `abs_url`
- `pdf_url`
- `published_at`
- `updated_at`
- `metadata_status`
- `created_at`
- `updated_row_at`

`paper_versions`

- `arxiv_id`
- `version`
- `updated_at`
- `comment`
- `source_hash`

`daily_events`

- `date`
- `arxiv_id`
- `event_type`
- `listing_category`
- `primary_category`
- `seen_source_url`
- unique key: `date + arxiv_id + event_type + listing_category`

`crawl_runs`

- `id`
- `date`
- `mode`
- `status`
- `started_at`
- `finished_at`
- `summary_counts_json`
- `error_counts_json`

`crawl_run_sources`

- `run_id`
- `category`
- `event_section`
- `url`
- `status`
- `http_status`
- `parsed_count`
- `error`
- `retry_count`

### AI Tables

`summary_templates`

- `id`
- `name`
- `language`
- `version`
- `fields_json`
- `system_prompt`
- `input_scope`: `abstract`, `fulltext`, or `either`
- `is_default`
- `created_at`
- `updated_at`

Each field in `fields_json` includes:

- field key
- display label
- order
- field prompt
- field type: short sentence, bullet list, paragraph, score, tags, or choice
- enabled flag

`summaries`

- `arxiv_id`
- `template_id`
- `template_version`
- `model`
- `language`
- `input_scope`
- `content_json`
- `status`
- `created_at`
- `updated_at`

`ai_jobs`

- `id`
- `job_type`
- `arxiv_id`
- `status`
- `priority`
- `attempts`
- `next_run_at`
- `payload_json`
- `error`
- `created_at`
- `updated_at`

Job types include:

- `summarize_abstract`
- `fetch_fulltext`
- `summarize_fulltext`
- `embed_paper`
- `deep_read_paper`

### Discussion and Deep Reading Tables

`chat_sessions`

- `id`
- `title`
- `scope_json`
- `created_at`
- `updated_at`

`chat_messages`

- `session_id`
- `role`
- `content`
- `citations_json`
- `created_at`

`paper_assets`

- `arxiv_id`
- `asset_type`
- `path_or_url`
- `status`
- `metadata_json`
- `created_at`

`reading_reports`

- `id`
- `arxiv_id`
- `status`
- `agent_version`
- `started_at`
- `finished_at`
- `error`

`reading_report_sections`

- `report_id`
- `section_key`
- `title`
- `content_json`
- `status`
- `created_at`

`external_links`

- `arxiv_id`
- `link_type`
- `url`
- `source`
- `confidence`
- `created_at`

## AI Summary Templates

AI summaries are configurable and versioned. Users can edit templates in the UI:

- add, remove, enable, disable, and reorder fields
- edit field-specific prompts
- choose output language
- choose whether a template can run on abstract-only input or requires full text
- test the template on one paper
- rerun summaries for a selected date, category, paper, or filter

Changing a template creates a new template version. Old summaries remain attached to their original version. The user can choose whether new papers use the new version only or whether existing summaries should be regenerated.

Default template:

1. One-sentence conclusion
2. Research question
3. Core method
4. Key experiments or data
5. Main results
6. Limitations
7. Why it is worth reading
8. Related direction tags

## Deep Paper-Reading Agent

The deep reading agent is in v1, but it is not part of the default all-paper daily task.

It can be triggered for:

- a single paper
- favorited papers
- a selected small batch
- papers in the current filtered result set, with an explicit limit

The queued workflow performs:

1. Fetch full text from arXiv source, arXiv HTML, or PDF fallback.
2. Extract main text.
3. Index figures and tables when extraction allows.
4. Analyze contribution claims.
5. Break down method and assumptions.
6. Extract experimental setup and main results.
7. Identify limitations and failure cases.
8. Search or infer code links from abstract/full text and known URL patterns.
9. Produce a structured deep reading report.
10. Make the report available to the chat interface for follow-up questions.

The UI must show per-step state, such as:

- full text parsed
- figure extraction failed
- code links found
- deep report complete

Failures are stored per step. Partial reports are usable.

## API Design

Primary FastAPI endpoints:

`POST /api/crawl/run`

- Trigger a crawl for a date.
- Supports full rerun, failed-source-only rerun, and metadata-only completion.

`GET /api/crawl/runs/{date}`

- Return crawl status, source status, counts, and errors.

`GET /api/days/{date}/papers`

- List papers by date.
- Supports filters: event type, category, metadata status, AI status, full-text status, keyword, sort, pagination.

`GET /api/papers/{arxiv_id}`

- Return metadata, daily events, versions, summaries, assets, deep reading reports, and job states.

`POST /api/papers/{arxiv_id}/jobs`

- Trigger one or more jobs: metadata, abstract summary, full-text fetch, full-text summary, embedding, deep reading.

`GET /api/summary-templates`

- List templates and versions.

`POST /api/summary-templates`

- Create a template.

`PUT /api/summary-templates/{template_id}`

- Create a new version from edited template content.

`POST /api/summary-templates/{template_id}/test`

- Test a template on a selected paper.

`POST /api/chat`

- Discuss a paper, selected papers, or current search/filter results.

## UI Design

The web UI is a dense, local research workbench.

### Daily Workbench

Top bar:

- date selector
- run crawl button
- crawl status
- failed source count
- metadata pending count
- AI pending count
- worker status

Left filters:

- category
- event type: `new`, `cross-list`, `replacement`
- metadata status
- summary status
- full-text status
- deep-reading status
- text search

Main list:

- title
- authors
- categories
- event badges
- metadata/AI/full-text status
- abstract summary preview
- favorite or priority marker

Right detail panel:

- abstract
- AI summaries by template
- links to arXiv abs/PDF/HTML
- daily event provenance
- version history
- job controls

Tabs in detail:

- Overview
- Summary
- Full Text
- Deep Reading
- Discussion
- Provenance

### Template Settings

The settings view lets the user edit summary templates:

- fields
- order
- field prompt
- field type
- output language
- input scope
- default template
- test output
- bulk rerun action

### Deep Reading View

The deep reading tab shows:

- agent progress by step
- extracted assets
- structured report sections
- code links and related external links
- follow-up chat grounded in the report

## Search and Chat

Keyword search should use SQLite FTS over title, abstract, authors, categories, and structured summary fields.

Semantic search is optional in v1. If embeddings are configured, the app can add vector retrieval over papers and summaries. If embeddings are not configured, the app must still work with keyword search.

Chat supports:

- single-paper discussion
- selected multi-paper discussion
- current-filter discussion

The chat context uses, in order:

1. paper metadata
2. abstract
3. structured summaries
4. deep reading report if available
5. full-text chunks if fetched

If full text is needed but missing, the chat endpoint should enqueue a full-text job and explain the missing state instead of failing silently.

## v1 Exclusions

These are intentionally outside v1 unless explicitly added later:

- Zotero personalized recommendation.
- Email delivery.
- GitHub Pages static publishing.
- Multi-user authentication or permissions.
- Cloud deployment.
- Default full daily PDF/source download for all arXiv papers.
- Default deep reading for all arXiv papers.

## Testing Strategy

Tests should focus on reliability and resumability.

### Crawler Tests

- Offline HTML fixtures for daily listing pages.
- Parse `new`, `cross-list`, and `replacement`.
- Parse duplicate arXiv IDs across categories without creating duplicate `papers`.
- Detect failed or suspicious source pages.

### Metadata Tests

- Mock arXiv API batch responses.
- Test 429 retry and delayed metadata status.
- Ensure event IDs are persisted before metadata enrichment.

### Database Tests

- Temporary SQLite database.
- Test uniqueness for `daily_events`.
- Test rerun behavior.
- Test partial run status and failed-source-only rerun.

### AI Template Tests

- Fake LLM responses.
- Validate structured JSON output storage.
- Validate template versioning.
- Validate regeneration jobs for selected templates.

### Worker Tests

- Retry, failure, next-run scheduling.
- Manual wait mode.
- Partial deep-reading report persistence.

### API Tests

- Date paper list filters.
- Paper detail endpoint.
- Job trigger endpoint.
- Summary template CRUD/versioning.
- Chat endpoint with and without full text.

### End-to-End Fixture

Run a small offline flow:

1. Crawl fixture daily pages.
2. Persist daily events.
3. Enrich mocked metadata.
4. Search papers.
5. Generate fake template summary.
6. Trigger a fake deep reading job.
7. Query paper detail and chat context.

## Open Implementation Notes

- The arXiv category taxonomy source should be cached locally and refreshable.
- Crawl scheduling can start as CLI/manual and later add a local scheduler.
- The app should use explicit rate limits and backoff for arXiv API calls.
- Network-dependent tests should be avoided in CI; use fixtures and mocks.
