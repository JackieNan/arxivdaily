# arxiv-local-daily Phase Log

Date baseline: 2026-06-03

## Phase 0: Product Design

- Branch: `main`
- Commit: `da22453 docs: add arxiv local daily design`
- Artifact: `docs/superpowers/specs/2026-06-03-arxiv-local-daily-design.md`
- Scope: local-first arXiv daily crawler, SQLite database, configurable AI summaries, search, discussion, and manually triggered deep reading agent.
- Status: complete.

## Phase 1: Local Vertical Slice

- Branch: `codex/phase-1-local-daily`
- Main merge commit: `8aec589 merge phase one local daily app`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-1.md`
- Scope completed:
  - project scaffold
  - SQLite schema
  - offline arXiv daily listing parser
  - daily event ingestion
  - versioned summary template persistence
  - minimal FastAPI endpoints
- Verification:
  - `uv run pytest -v`: 19 passed, 1 warning
  - live cs.AI parser smoke test: 440 events parsed from the current arXiv daily page.
- Status: merged to `main`.

## Phase 2: Live Daily Crawler

- Branch: `codex/phase-2-live-crawler`
- Main merge commit: `00df456 merge phase two live crawler`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-2-live-crawler.md`
- Scope completed:
  - arXiv category taxonomy parsing
  - default all-category discovery
  - retryable arXiv HTTP fetching
  - multi-source daily crawl ingestion
  - per-source crawl health records
  - `complete` and `partial` run status
  - crawl trigger API
  - manual crawl CLI
- Verification:
  - `uv run pytest -v`: 35 passed, 1 warning
  - live taxonomy discovery smoke test: 155 categories discovered.
  - live cs.AI limited crawl smoke test: 440 events persisted with source status `complete`.
- Status: merged to `main`.

## Phase 3: arXiv API Metadata Enrichment

- Branch: `codex/phase-3-metadata-enrichment`
- Main merge commit: `9671398 merge phase three metadata enrichment`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-3-metadata-enrichment.md`
- Scope completed:
  - fetch metadata from the arXiv API for known arXiv IDs
  - parse Atom feed entries into structured paper metadata
  - persist title, authors, abstract, categories, URLs, published/updated timestamps, and version data
  - mark metadata as `complete`, `pending`, or `failed`
  - expose manual metadata enrichment through CLI/API
- Verification:
  - `uv run pytest -v`: 44 passed, 1 warning
  - metadata CLI help smoke test succeeded.
  - live arXiv API metadata smoke test: `2606.00001` returned one parsed paper.
- Status: merged to `main`.

## Phase 4: Configurable AI Summary Worker

- Branch: `codex/phase-4-ai-summary-worker`
- Main merge commit: `b18056d merge phase four summary worker`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-4-ai-summary-worker.md`
- Scope completed:
  - create and version user-editable summary templates through API/CLI
  - build structured prompts from template fields and paper metadata
  - parse JSON AI responses into configurable summary sections
  - persist summaries by paper, template version, model, and input scope
  - expose manual summary generation through CLI/API
- Verification:
  - `uv run pytest -v`: 55 passed, 1 warning
  - focused Phase 4 tests: 11 passed, 1 warning
- Status: merged to `main`.

## Phase 5: Crawl Completeness Audit

- Branch: `codex/phase-5-crawl-completeness-audit`
- Main merge commit: `fbb923d merge phase five crawl audit`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-5-crawl-completeness-audit.md`
- Scope completed:
  - compute daily crawl completeness across all crawl runs for a date
  - detect failed and never-attempted expected categories
  - expose retry candidates for incomplete categories
  - rerun failed or missing categories through CLI/API
  - document audit and retry workflow
- Verification:
  - focused Phase 5 tests: 11 passed, 1 warning
  - `uv run pytest -v`: 66 passed, 1 warning
- Status: merged to `main`.

## Phase 6: Search and Discussion

- Branch: `codex/phase-6-search-discussion`
- Main merge commit: `a46c02c merge phase six search discussion`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-6-search-discussion.md`
- Scope completed:
  - search papers across title, abstract, authors, categories, arXiv ID, and summaries
  - filter results by date, category, event type, metadata status, and summary status
  - expose paper detail with daily events, summaries, and discussions
  - store local per-paper discussion messages
  - expose search and discussion through CLI/API
- Verification:
  - focused Phase 6 tests: 10 passed, 1 warning
  - `uv run pytest -v`: 75 passed, 1 warning
- Status: merged to `main`.

## Phase 7: Local Web UI

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-7-web-ui.md`
- Scope completed:
  - serve a static local workbench from FastAPI
  - provide crawl, audit, metadata, and summary controls
  - provide paper search and filters
  - show paper details, summaries, and discussions
  - support local discussion message creation from the UI
  - show structured operation details for enrich/search errors and empty states
  - expose metadata failure reasons and default summary template creation in the UI
  - handle arXiv metadata API rate limits with retryable status, backoff timestamps, and in-process request spacing
- Verification:
  - focused Phase 7 rate-limit tests: 13 passed, 1 warning
  - `uv run pytest -v`: 81 passed, 1 warning
  - Chrome headless desktop and mobile screenshots succeeded.
  - live local checks: summary missing template returns `400 {"detail":"summary template not found"}`; search returns `200`.
  - live metadata timeout check returns `retryable` with `next_run_at`.
- Status: implemented on branch, not yet merged to `main`.

## Phase 8: OAI Metadata Mirror

- Branch: `codex/phase-7-web-ui`
- Commit: local Phase 8 commit on this branch.
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-8-oai-metadata-mirror.md`
- Scope completed:
  - persist daily listing titles immediately during crawl
  - add OAI-PMH ListRecords URL builder, XML parser, and rate-limited client
  - add `metadata_sync_runs` for queued/running/complete/failed OAI sync jobs
  - upsert OAI metadata into local `papers`
  - expose OAI sync start/list/status API routes
  - add web controls and polling for OAI metadata sync status
  - retain legacy arXiv API metadata enrichment as fallback
- Verification:
  - focused Phase 8 tests: parser/ingestion, OAI parser/client, sync service, API, and web UI all passed.
  - `uv run pytest -v`: 89 passed, 1 warning
  - local API smoke: OAI sync start returned `run_id=1`; status route returned `complete` with counters and `error=null`.
  - in-app browser smoke: `Start OAI Sync` rendered and updated sync detail after a no-network `max_pages=0` run.
- Status: implemented on branch, not yet merged to `main`.

## Phase 9: Complete Enrich, Scoring, and Triage UI

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-9-complete-enrich-score-ui.md`
- Scope completed:
  - add page-declared crawl counts and `incomplete` source status when parsed count is below expected count
  - extend crawl audit with incomplete category counts and retry candidates
  - add unified metadata enrichment run records, source records, and merge reports
  - merge metadata from crawled listing, arXiv ID API, and OAI source records into local `papers`
  - record OAI missing, OAI extra, and source mismatch reports for diagnostics
  - add paper reading-priority scores with default rubric dimensions: relevance, novelty, technical depth, evidence, and actionability
  - add score sorting to search
  - move summary template/model controls into Settings
  - reorganize the web UI into left controls, center search, and right fixed paper detail
  - redesign search cards and paper detail to show compact metadata and scores
- Important decisions:
  - crawl listing is the source of truth for today's paper set
  - OAI and ID API are metadata sources inside one enrich workflow, not separate user-facing workflows
  - scoring is a reading-priority score, not an objective paper-quality score
- Verification:
  - focused crawl/audit, unified enrich, scoring, API, and web UI tests passed
  - `uv run pytest -v`: 100 passed, 1 warning
  - browser layout smoke confirmed the new left controls, center search, right detail layout and Settings/Score controls. Direct click smoke was blocked by the in-app browser coordinate translation layer.
- Status: implemented on branch, not yet merged to `main`.

## Phase 10: Auto Enrich and Clean All-Paper UI

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-10-auto-enrich-clean-ui.md`
- Scope completed:
  - make `POST /api/crawl/run` queue unified metadata enrichment in the background after crawl
  - process all crawled daily IDs by default in unified metadata enrichment
  - remove user-facing Enrich, legacy metadata, metadata limit, OAI page, summary limit, and score limit controls from the web UI
  - move Crawl and Settings into a compact top action strip
  - keep paper list and fixed right paper detail as the primary work area
  - return all matching search results by default in repository/API/UI/CLI
  - run summary and score over all eligible candidates by default while retaining optional diagnostic limits in API/CLI
  - prevent horizontal overflow in search controls, paper cards, tags, abstracts, and summary JSON
- Important decisions:
  - crawl is the only normal user-facing ingestion action
  - metadata completion is an automatic post-crawl background responsibility
  - OAI and ID API remain internal metadata sources, not separate UI workflows
  - limits remain optional diagnostics for scripts/API callers, not normal UI controls
- Verification:
  - focused Phase 10 API/search/web UI tests: 5 passed, 1 warning
  - focused all-candidate summary/score/CLI default tests: 3 passed
  - `uv run pytest -v`: 105 passed, 1 warning
  - browser desktop smoke: no Enrich/left rail/limit controls, top action strip present, no document horizontal overflow
  - browser mobile smoke at 390px width: search controls fit and no horizontal document overflow
- Status: implemented on branch, not yet merged to `main`.

## Phase 11: Math Rendering and Chinese Keywords

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-11-math-keywords-cn-summary.md`
- Scope completed:
  - add MathJax configuration for title and abstract LaTeX rendering
  - add a local lightweight LaTeX fallback renderer for common inline formulas when MathJax is unavailable
  - trigger MathJax typesetting after dynamic search result and paper detail rendering
  - add latest-summary `summary_keywords` to search results
  - display Chinese keyword chips in paper cards instead of abstract snippets
  - update the default web-created summary template with Chinese `keywords`, `tldr`, `method`, `value`, and `limits` fields
  - update summary prompt construction to require user-facing JSON values in the template language
- Important decisions:
  - paper lists are for triage and should show LLM-compressed Chinese keywords, not long abstracts
  - raw title and abstract remain in detail, but formulas should render where possible
  - if a paper has no complete summary yet, the card shows a missing-keywords hint rather than abstract text
- Verification:
  - focused keyword/search, summary prompt, and web UI tests passed
  - `uv run pytest -v`: 105 passed, 1 warning
  - browser smoke after server restart confirmed no abstract snippets in default cards and no horizontal overflow
  - local API smoke found the user-referenced formula-title paper `2104.14092`
- Status: implemented on branch, not yet merged to `main`.

## Phase 12: Daily vs Overview Search Scope

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-12-search-scope-toggle.md`
- Scope completed:
  - add a search scope selector with `当日` and `总览`
  - keep `当日` as the default behavior and continue sending the selected date to search
  - make `总览` omit the date parameter so the search list covers the whole local database
  - update result detail/status text to show the active scope
- Important decisions:
  - the previous list was already day-scoped, but the UI did not make that obvious
  - `总览` is a repository-wide view, not a separate data source
- Verification:
  - focused web UI tests passed
  - `uv run pytest -v`: 105 passed, 1 warning
- Status: implemented on branch, not yet merged to `main`.

## Phase 13: Copy and Math Style Polish

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-13-copy-math-style-polish.md`
- Scope completed:
  - correct repository-wide search scope label to `总览`
  - update Phase 12 documentation to use the corrected label
  - tone down fallback LaTeX CSS by removing decorative script fonts
  - replace the floating hat pseudo-element with a simple overline
- Verification:
  - focused web UI tests passed
  - `uv run pytest -v`: 105 passed, 1 warning
- Status: implemented on branch, not yet merged to `main`.

## Phase 14: UI Density and Detail Focus

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-14-ui-density-detail-focus.md`
- Scope completed:
  - remove routine `Loaded <id>` paper-selection messages from the top operation log
  - make the Crawl and Settings top strip denser with smaller buttons, badges, inputs, and diagnostic text
  - use a desktop grid that narrows the search/list column and widens the right paper detail rail
  - make search controls stable two-column controls with full-width query and search action
  - switch fallback LaTeX text to a plainer serif style without ornate math/script fonts
- Important decisions:
  - paper detail is the main reading surface and should get more first-screen width than the list
  - top controls should stay available without competing visually with the paper detail
  - paper selection is navigation, not an operation worth logging
- Verification:
  - focused web UI tests passed
  - `uv run pytest -v`: 105 passed, 1 warning
  - browser smoke at 599px viewport confirmed no horizontal overflow in document, Settings, Crawl, Search, or detail rail; operation log capped at 84px and no `Loaded <id>` paper-selection message
- Status: implemented on branch, not yet merged to `main`.

## Phase 15: Daily Pipeline and Summary Completion

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-03-arxiv-local-daily-phase-15-daily-pipeline-summary-completion.md`
- Scope completed:
  - add `get_daily_pipeline_status` for daily crawl, metadata, summary, and score coverage
  - add `run_daily_pipeline` to orchestrate crawl, audit/retry, unified metadata enrichment, summary generation, and scoring
  - expose `GET /api/daily/status/{date}`
  - expose `POST /api/daily/pipeline/run`
  - add a compact Daily panel with `Daily Status`, `Run Daily Pipeline`, and coverage counters
  - treat missing summary templates, missing summaries, failed summaries, missing scores, and metadata gaps as explicit daily blockers
- Important decisions:
  - AI summary completion is part of daily reliability, not only a manual side action
  - summary coverage is measured over daily papers with complete metadata and non-empty abstracts
  - the PDF-reading agent remains separate from this abstract/metadata-based daily pipeline
- Verification:
  - focused Phase 15 tests passed
  - `uv run pytest -v`: 109 passed, 1 warning
  - browser smoke at 599px viewport confirmed Daily panel controls, no horizontal overflow, and compact two-row top action layout
  - local API smoke confirmed `GET /api/daily/status/2026-06-03?model=local` returns crawl, metadata, summary, score, and blocker fields
- Status: implemented on branch, not yet merged to `main`.

## Phase 16: Compact Status and Data Reset

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-04-arxiv-local-daily-phase-16-ui-compact-status-data-reset.md`
- Scope completed:
  - make the Settings grid fit narrow in-app browser widths without horizontal overflow
  - make `Create Default Template` span the full Settings row
  - cap the top operation log to a one-line key status instead of rendering detailed JSON
  - reset the current local paper and metadata data
  - preserve summary templates after the reset
- Important decisions:
  - the top-left status area should answer "what just happened" only
  - detailed operation output belongs in the relevant panel detail area
  - clearing papers should also clear daily events, crawl runs, metadata runs/source records, summaries, scores, discussions, and jobs
- Verification:
  - focused web UI tests passed
  - `uv run pytest -v`: 109 passed, 1 warning
  - browser smoke at 599px viewport confirmed no horizontal overflow and a 35px one-line operation log
  - SQLite reset confirmed papers, daily events, metadata runs/source records, summaries, scores, and crawl runs are 0; summary templates remain 2
  - local API smoke confirmed daily status is `not_started` and search returns `count=0`
- Status: implemented on branch, not yet merged to `main`.

## Phase 17: Daily and Settings UI Semantics

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-04-arxiv-local-daily-phase-17-daily-settings-ui-semantics.md`
- Scope completed:
  - clarify that 155 is the all-category crawl coverage count, not the daily paper count
  - show daily paper count from the daily metadata/paper total
  - replace `Daily Status` and `Run Daily Pipeline` with one `Run Daily Update` action
  - remove raw Daily and Settings detail panes from the main UI
  - replace `Create Default Template` with a hidden second-level template editor
  - allow template module labels, prompts, and enabled flags to be edited and saved
  - combine manual summary and score execution into one `Run Summary + Score` action
- Important decisions:
  - Daily should be an operational summary, not a raw API inspector
  - crawl coverage and paper count must be shown as separate concepts
  - summary template editing belongs in a second-level panel because it is not a routine daily action
- Verification:
  - focused web UI tests passed
  - `uv run pytest -v`: 109 passed, 1 warning
  - browser smoke at 599px viewport confirmed no horizontal overflow, one Daily button, no raw Daily/Settings detail panes, and a working expandable template editor
- Status: implemented on branch, not yet merged to `main`.

## Phase 18: Daily Automation and Metadata Completion

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-04-arxiv-local-daily-phase-18-daily-automation-metadata-completion.md`
- Scope completed:
  - add `complete_metadata_for_date` as a batched metadata completion loop
  - fetch incomplete metadata in batches of 100 daily IDs by default
  - change unified metadata enrichment to support `only_incomplete`
  - mark HTTP 429/timeout source failures as `retryable` with `metadata_next_run_at`
  - make failed metadata rows respect retry windows so background work does not spin
  - queue metadata completion after crawl instead of a one-shot unified enrich pass
  - add `POST /api/daily/automation/start` to crawl-if-needed and then complete metadata
  - merge the former Crawl and Daily panels into one `Daily Automation` panel
  - start daily automation automatically on page load and date changes
- Important decisions:
  - metadata completion is a background reliability responsibility, not a manual button workflow
  - source limits should produce retryable state, not permanent all-paper failure
  - Crawl and Daily are one daily automation pipeline in the UI
- Verification:
  - focused metadata/API/web UI tests passed
  - `uv run pytest -v`: 112 passed, 1 warning
  - browser smoke at 342px viewport confirmed one Daily Automation panel, no old Crawl/Daily panels, and no horizontal overflow
  - live local smoke showed the old failed metadata set begin recovering: 56 complete, 144 retryable, 1771 still failed
- Status: implemented on branch, not yet merged to `main`.

## Phase 19: LLM API Triage Automation

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-04-arxiv-local-daily-phase-19-llm-api-triage-automation.md`
- Scope completed:
  - add a combined AI triage prompt that returns one JSON object with `summary` and `score`
  - parse combined LLM responses and persist the configurable Chinese summary/keywords plus reading-priority score
  - add `generate_ai_triage_for_date` for one-pass manual AI triage over eligible papers
  - add `complete_ai_triage_for_date` for batched completion until daily AI coverage is complete
  - avoid writing failed summary/score rows when no LLM API is configured
  - connect daily automation as crawl-if-needed -> metadata completion -> AI triage completion
  - add `POST /api/ai-triage/run`
  - make Settings `Run Summary + Score` use the combined AI triage endpoint
  - pass the selected template and model into daily automation
  - update README API/setup notes for OpenAI-compatible LLM configuration
- Important decisions:
  - summary and score should be generated in one LLM call per paper
  - existing summary and score tables remain the source of truth
  - AI triage is skipped as `not_configured` if the default OpenAI URL has no API key and no custom base URL is set
  - PDF/full-text long-chain reading remains a later phase, separate from daily abstract-based triage
- Verification:
  - focused AI triage/API/web UI tests: 9 passed, 1 warning
  - `uv run pytest -v`: 118 passed, 1 warning
- Status: implemented on branch, not yet merged to `main`.

## Phase 20: Date-Aware and Historical Crawl

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-05-arxiv-local-daily-phase-20-date-aware-historical-crawl.md`
- Scope completed:
  - parse the real arXiv announcement date from `/list/{category}/new` headings
  - record `date_mismatch` sources when the current `/new` page date does not match the selected date
  - avoid writing wrong-date daily events on date mismatch
  - add `run_historical_metadata_crawl` backed by OAI-PMH `ListRecords`
  - store historical date records as metadata-complete papers with `event_type = historical`
  - add `crawl_mode` and `historical_max_pages` to daily automation requests
  - route historical automation through OAI metadata instead of `/new` plus metadata completion
  - make the web UI send `crawl_mode = historical` for selected dates earlier than the browser's current date
  - add `historical` to the search event filter and correct event filter values for `cross-list` and `replacement`
- Important decisions:
  - `/new` is only a current arXiv announcement page, not a historical date endpoint
  - historical collection is metadata-based and should not be labeled as daily `new`, `cross-list`, or `replacement`
  - if today's local date is ahead of arXiv's current page, the app waits instead of storing yesterday under today
- Verification:
  - focused date-aware crawl, historical crawl, API, and web UI tests: 26 passed, 1 warning
  - `uv run pytest -v`: 122 passed, 1 warning
- Status: implemented on branch, not yet merged to `main`.

## Phase 21: Data Repair and Auto Polling

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-05-arxiv-local-daily-phase-21-data-repair-auto-poll.md`
- Scope completed:
  - add `repair_contaminated_daily_listing_dates` for local cleanup of wrong-date daily listing rows
  - delete only `new`, `cross-list`, and `replacement` daily events for selected contaminated dates
  - preserve `historical` events, metadata, summaries, scores, discussions, and paper rows
  - delete old daily crawl runs in `single-source`, `all-categories`, and `retry-incomplete` modes so audit will not treat contaminated runs as valid
  - expose `POST /api/repair/daily-listings` for explicit repair runs
  - make the open workbench silently restart daily automation every 10 minutes
- Important decisions:
  - Phase 20 prevents future wrong-date writes; Phase 21 repairs already polluted local data
  - OAI-PMH remains a metadata/historical record source, not a guarantee of exact historical daily listing sections
  - exact earlier-day listing reconstruction should parse arXiv historical listing/archive pages per category and use OAI/API only for enrichment and cross-checking
- Verification:
  - focused data repair/API/web UI tests: 3 passed, 1 warning
- Status: implemented on branch, not yet merged to `main`.

## Phase 22: Exact Historical Listing Crawl

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-05-arxiv-local-daily-phase-22-exact-historical-listing.md`
- Scope completed:
  - add historical listing parsing for a single requested date inside monthly arXiv listing/archive pages
  - add `parse_listing_dates` so pagination can stop after passing the target date
  - add historical listing URL construction with `/list/{category}/{yymm}?skip={skip}&show={show}`
  - add `run_historical_listing_crawl` with mode `historical-listing`
  - make historical listing crawl store exact `new`, `cross-list`, and `replacement` events instead of `historical`
  - remove metadata-only `historical` event rows for category/date pairs once exact listing rows have been successfully crawled
  - make `historical-oai` metadata runs invisible to daily crawl completeness
  - route daily automation `crawl_mode = historical` through exact historical listing crawl, then metadata completion, then AI triage
- Important decisions:
  - OAI-PMH is still a metadata source, not a source of exact daily listing membership
  - exact listing events should use the same event types as live `/new` crawl
  - metadata rows from old OAI collection are preserved even when metadata-only daily events are removed
- Verification:
  - focused parser/live crawl/API/audit tests: 8 passed, 1 warning
  - `uv run pytest -v`: 131 passed, 1 warning
- Status: implemented on branch, not yet merged to `main`.

## Phase 23: arXiv Time, Pagination, and Progress

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-05-arxiv-local-daily-phase-23-arxiv-time-pagination-progress.md`
- Scope completed:
  - add `fetch_current_arxiv_listing_date` to probe arXiv's current `/new` page date
  - make Daily Automation default to `crawl_mode = auto`
  - route auto mode to daily crawl, historical listing crawl, or `waiting` based on arXiv's current listing date
  - record `arxiv-date-check` runs with source status `waiting` when the selected date is ahead of arXiv
  - add `waiting` support to crawl completeness and daily blockers
  - add paginated search API metadata: `page`, `page_size`, `total`, `total_pages`, `has_prev`, and `has_next`
  - add web UI previous/next date buttons, paper result pagination, original arXiv links, and a three-segment progress line
- Important decisions:
  - arXiv page date is the source of truth for daily/previous/future routing
  - future local dates should wait instead of writing an empty or wrong daily list
  - pagination is API-backed rather than hiding loaded results in the browser
- Verification:
  - focused Phase 23 tests: 57 passed, 1 warning
  - `uv run pytest -v`: 136 passed, 1 warning
- Status: implemented on branch, not yet merged to `main`.

## Phase 24: Date Navigation and Paper Crawl Progress Fix

- Branch: `codex/phase-7-web-ui`
- Scope completed:
  - fix previous/next date navigation by shifting ISO dates with `Date.UTC`, avoiding local timezone conversion from `YYYY-MM-DDT00:00:00`
  - add crawl audit paper totals: `parsed_paper_count`, `expected_paper_count`, and `missing_paper_count`
  - replace the three-segment automation progress indicator with one paper crawl progress bar
  - render filled progress in color and leave the remaining track empty
- Important decisions:
  - the progress bar should describe only paper listing crawl progress, not metadata/summary/score state
  - category progress and metadata/AI status remain available in the summary metrics and detail text
- Verification:
  - focused crawl audit and web UI tests: 11 passed, 1 warning
- Status: implemented on branch, not yet merged to `main`.

## Phase 25: Three-Stage Pipeline Progress

- Branch: `codex/phase-7-web-ui`
- Scope completed:
  - clarify the automation button by renaming it to `Refresh Status`
  - keep `Refresh Status` scoped to status/list refresh only; it does not start a new crawl
  - replace the single paper progress row with three progress rows: Papers, Metadata, and AI
  - render Papers from distinct arXiv IDs, avoiding double-counted category listing entries
  - render Metadata from `metadata.complete / metadata.total`
  - render AI from per-paper summary/score triage coverage using `min(summary.complete, score.complete) / max(summary.eligible, score.eligible)`
- Important decisions:
  - listing crawl currently parses each category page as a batch; exact per-paper crawl streaming is a later crawler refactor
  - arXiv category counts are listing entries, so completed paper counts should normalize to distinct arXiv IDs
  - metadata and AI progress already advance through batch loops and can be monitored through status polling
  - empty tracks show no known total, colored fill shows current phase progress/state
- Verification:
  - focused web UI tests: 2 passed, 1 warning
- Status: implemented on branch, not yet merged to `main`.

## Phase 26: Preflight Completeness Evidence

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-05-arxiv-local-daily-phase-26-preflight-completeness.md`
- Scope completed:
  - add independent `crawl_preflight_runs` and `crawl_preflight_sources` tables
  - add `run_daily_listing_preflight` to fetch requested `/new` category pages before main daily crawl
  - verify listing date, declared entry count, parsed entry count, distinct arXiv IDs, missing count, and per-source errors
  - treat explicit arXiv `No updates today.` category pages as complete zero-count sources
  - run daily preflight before daily crawl in Daily Automation
  - use a short current-date probe and record `arxiv-date-check/waiting` if the probe fails or arXiv has not advanced to the selected date
  - backfill preflight evidence for already-complete daily crawls when no complete preflight exists
  - add `GET /api/preflight/{date}` for raw evidence inspection
  - include latest preflight report in `GET /api/daily/status/{date}`
  - make Papers progress prefer preflight distinct-paper totals when available
  - document API and SQLite checks for verifying complete daily collection
- Important decisions:
  - preflight evidence is stored separately from crawl runs so it cannot pollute crawl completeness
  - preflight only certifies current `/new` daily listings; exact historical completeness still comes from historical listing crawl audit
  - a non-empty category without a declared arXiv count is `count_missing`, so preflight is `partial` rather than falsely complete
- Browser/local verification on 2026-06-05:
  - UI displayed `Preflight complete: 2071 distinct papers, 155/155 categories`
  - latest `crawl_preflight_runs` row was `complete`, `listing_entry_count=3757`, `distinct_paper_count=2071`, `missing_count=0`, `error_counts={}`
- Verification:
  - focused API/live/parser/preflight tests: 63 passed, 1 warning
  - full test suite: 143 passed, 1 warning
- Status: implemented on branch, not yet merged to `main`.

## Phase 27: Selected-Date Crawl Launcher

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-06-arxiv-local-daily-date-crawl-launcher.md`
- Scope completed:
  - replace the primary `Refresh Status` automation button with `抓取指定日期`
  - add a date crawl launcher dialog with target date selection and explicit `开始抓取`
  - keep a smaller `刷新状态` control that only reloads daily status/search
  - make date picker changes and previous/next buttons refresh the selected-date view without starting a crawl
  - keep background polling for status/search refresh without silently launching new crawl jobs
- Important decisions:
  - viewing a date and starting a crawl are separate actions
  - the launcher continues to use backend `crawl_mode=auto`, so arXiv listing date still decides daily, historical, or waiting behavior
  - category Enter remains a keyboard shortcut for starting automation for the selected date
- Verification:
  - focused web UI tests: 2 passed, 1 warning
  - full test suite: 143 passed, 1 warning
  - browser verified launcher open/close, `开始抓取` POST, `Crawl 2026-06-06 queued` feedback, waiting blocker display, and no horizontal overflow
- Status: implemented on branch, not yet merged to `main`.

## Phase 28: Pipeline Status Component

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-06-arxiv-local-daily-status-component.md`
- Scope completed:
  - remove Daily Automation progress bars and progress fill logic
  - add a `pipeline-status` component with Papers, Metadata, and AI status panels
  - render each stage as state badge, count, and short detail text
  - show preflight evidence in the Papers stage detail when available
  - keep state badge styling for idle, running, waiting, partial, complete, and failed
- Important decisions:
  - the status component is better than progress bars for long-running background jobs with waiting and partial states
  - counts remain visible, but percentage fills are no longer used
- Verification:
  - focused web UI tests: 2 passed, 1 warning
  - full test suite: 143 passed, 1 warning
  - browser verified `pipeline-status` appears, old progress bars are absent, Papers shows `waiting`, Metadata/AI show `idle`, and no horizontal overflow
- Status: implemented on branch, not yet merged to `main`.

## Phase 29: Automation Run Status Visibility

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-06-arxiv-local-daily-automation-run-status.md`
- Scope completed:
  - add persistent `daily_automation_runs` records for selected-date crawl launches
  - create a queued automation run before scheduling background work
  - update the run at arXiv date check, preflight, crawl, metadata, AI, waiting, no-paper, complete, and failed states
  - include the latest automation run in `GET /api/daily/status/{date}`
  - return `automation_run_id` from `POST /api/daily/automation/start`
  - add a Backend card to the UI status component with run id, current step, updated time, and error/blocker details
  - immediately render queued/running state after `开始抓取`
  - poll daily status every 2.5 seconds while the latest backend run is queued or running, then stop when it reaches a terminal state
- Important decisions:
  - the UI should expose backend job state directly instead of inferring it from crawl/metadata counts
  - `no_papers` is a visible terminal state for an empty selected date, not a silent metadata failure
  - old historical runs that record zero papers after archive-page failures are now visible as suspicious evidence and should be fixed in a later crawler-correctness phase
- Verification:
  - focused API/db/web UI tests: 36 passed, 1 warning
  - full test suite: 144 passed, 1 warning
  - browser verified 2026-06-04 launch shows `Crawl 2026-06-04 queued; backend run #2`, Backend `running`, and `Step: checking arXiv date` immediately after clicking `开始抓取`
  - browser verified active polling updated the same card to `complete`, `Step: no papers`, with the error detail `metadata skipped because selected date has no papers`
  - browser width check showed no horizontal overflow
- Status: implemented on branch, not yet merged to `main`.

## Phase 30: Historical Pastweek Crawl Fix

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-06-arxiv-local-daily-historical-pastweek-fix.md`
- Scope completed:
  - add `/list/{category}/pastweek?skip=...&show=2000` as the first source for recent historical subject listing crawl
  - keep month archive URL fallback for later diagnostics and older-date extension
  - parse date-only pastweek sections by allowing `parse_historical_listing_for_date` to use a default `new` event type
  - filter historical and pastweek entries by target subject category
  - treat historical 404 pages as failed instead of complete-zero
  - make crawl audit reject old poisoned complete rows with archive-page 404 evidence
  - stop daily automation after incomplete crawl instead of continuing to metadata and reporting `no_papers`
  - add `crawl_incomplete` UI status
  - make the selected-date crawl launcher send `force_crawl=true` so user clicks really re-run the crawl even after an old bad complete-zero audit
  - bump static asset query version to load the fixed frontend code
- Important decisions:
  - for current-week historical dates, arXiv `pastweek` is the reliable subject listing source
  - `no_papers` should only mean the crawl completed and genuinely found no papers; crawl failures must remain crawl failures
  - the explicit `抓取指定日期` action should force a fresh crawl, not silently trust prior audit state
- Verification:
  - focused parser/live-crawl/audit/API/web UI tests: 78 passed, 1 warning
  - full test suite: 150 passed, 1 warning
  - direct arXiv URL probe confirmed `/list/cs.AI/pastweek?skip=0&show=2000` returns 200 and date-only sections
  - browser verified 2026-06-04 run #8 completed with Papers `1192/1192`, Metadata `1192/1192`, Backend `complete`
- Status: implemented on branch, not yet merged to `main`.

## Phase 31: AI Usability And Single Paper Triage

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-06-arxiv-local-daily-ai-usability.md`
- Scope completed:
  - add masked LLM API configuration status at `GET /api/ai/config`
  - add prompt preview at `POST /api/ai/prompt-preview` so the exact system/user messages can be inspected before calling an LLM
  - add `generate_ai_triage_for_paper` for one selected paper using the same summary+score prompt as daily batch triage
  - add `POST /api/papers/{arxiv_id}/ai-triage/run` for selected-paper AI runs
  - show AI API status in Settings without exposing the API key
  - add Paper detail actions for `Run AI` and `Preview Prompt`
  - render summary content as readable fields instead of raw JSON
- Important decisions:
  - prompt preview is a no-cost/no-LLM call and is the first debugging step before batch AI runs
  - selected-paper AI runs use `force=true` from the UI because they are a deliberate debugging action
  - batch daily AI remains separate and continues to use the existing automation path
- Verification:
  - focused AI/API/Web UI tests: 6 passed, 1 warning
  - focused Web UI regression tests after status fix: 2 passed, 1 warning
  - full test suite: 154 passed, 1 warning
  - browser verified `phase37` static assets, AI config status, June 4 daily list page `1/24` with `1192` papers, prompt preview modal content, selected-paper `not_configured` status persistence, and no horizontal overflow
- Status: implemented on branch, not yet merged to `main`.

## Phase 32: CS Default Scope

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-06-arxiv-local-daily-cs-default-scope.md`
- Scope completed:
  - add all 40 `cs.*` arXiv categories to the web app as the default empty-input category scope
  - make selected-date crawl automation send the CS category set unless the user manually enters categories or switches to all groups
  - make metadata completion and metadata status counts use the same category scope
  - make batch `Run Summary + Score` send the same category scope
  - add a bottom-of-page scope panel with a low-priority `抓取全部大组` / `恢复只抓取 CS` toggle
  - make daily status coverage accept category scope so CS-only summary/score totals match the selected workflow
  - filter AI triage candidates, skipped counts, summary coverage, and score coverage by category when categories are supplied
- Important decisions:
  - backend APIs still allow all-category operation by omitting `categories`
  - CS-only is the default product workflow, not a destructive database filter
  - manual category input overrides both CS-only and all-groups defaults
- Verification:
  - focused category-scope AI/API/Web UI tests: 6 passed, 1 warning
  - focused metadata category-scope tests: 3 passed, 1 warning
  - full test suite: 156 passed, 1 warning
  - browser verified `phase38` static assets, bottom scope panel visible, default CS status shows `40 cs.* categories`, all-groups toggle works, and no horizontal overflow
- Status: implemented on branch, not yet merged to `main`.

## Phase 33: LLM Config File and Model UI Removal

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-07-arxiv-local-daily-llm-config-file.md`
- Scope completed:
  - remove the Settings `Model` input from the web workbench
  - stop web daily automation, batch AI, status, and prompt-preview requests from sending model names
  - resolve omitted model values on the backend from LLM configuration
  - add local JSON config support at `config/llm.local.json`
  - keep environment variables as overrides over the local config file
  - add `config/llm.example.json` as a non-secret template
  - ignore `config/llm.local.json` in git
  - keep `/api/ai/config` masked while reporting config-file path/presence, key presence, base URL, and temperature
  - remove model tags/text from the summary detail and prompt preview surfaces
- Important decisions:
  - model identity is backend configuration, not a recurring UI workflow input
  - config precedence is env > `config/llm.local.json` > defaults
  - API keys must stay in untracked local files or environment variables
- Verification:
  - focused config-file/API/Web UI tests: 5 passed, 1 warning
  - full test suite: 158 passed, 1 warning
  - browser verified `phase39` static assets, Settings has no Model input, AI config status points to `config/llm.local.json`, and no horizontal overflow
- Status: implemented on branch, not yet merged to `main`.

## Phase 34: Default Template UI and Single-Paper AI Status

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-07-arxiv-local-daily-default-template-ui.md`
- Scope completed:
  - remove the Settings `Template name` input from the web workbench
  - keep template module editing and saving, using the backend default template name internally
  - stop web daily automation, daily status, batch AI, selected-paper AI, and prompt-preview requests from sending `template_name`
  - remove template-name display from summary detail tags and prompt-preview headers
  - make daily status display count completed summaries across historical versions of the same template name so template edits do not hide already generated AI summaries
  - keep AI generation strict to the current template version so batch jobs can still regenerate current-version summaries
  - add a regression test that selected-paper AI completion is visible in daily summary/score status without a template-name query, even after a newer default template version is saved
  - bump web static asset version to `phase40`
- Important decisions:
  - template identity is backend/default-template configuration, not a routine UI setting
  - the web app should use one consistent default template path so single-paper AI and daily status counts cannot drift because of a stale UI text field
  - daily status remains scoped to the selected date and category scope; non-CS AI outputs do not increment the CS-only `1/N` progress count
  - backend API compatibility for explicit `template_name` is preserved for non-web callers
- Verification:
  - focused Web UI + AI status tests: 3 passed, 1 warning
  - full test suite: 159 passed, 1 warning
  - browser verified `phase40` static assets, no Settings `Template name` input/text, no horizontal overflow, and Settings uses the local config file without showing a model input
  - local API verified the existing one completed non-CS AI paper now appears as `summary 1/2071` and `score 1/2071` for 2026-06-05 all-group status after a newer template version exists
  - browser verified 2026-06-05 CS-only status remains `summary 0/1196`, `score 0/1196` because the existing completed AI paper is `physics.atom-ph`, outside the current CS scope
- Status: implemented on branch, not yet merged to `main`.

## Phase 35: Single Config-File Summary Template

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-07-arxiv-local-daily-single-config-template.md`
- Scope completed:
  - remove Settings template editing UI, including module rows and Save Template controls
  - remove frontend calls to `/api/summary-templates`
  - remove summary-template CRUD API routes
  - add `config/summary_template.example.json`
  - ignore local `config/summary_template.local.json`
  - load the active summary template from `config/summary_template.local.json`, falling back to the built-in default when absent
  - force internal template identity to one singleton template with version `1`
  - keep existing template DB tables only as internal storage to avoid destructive migration
  - make summary completion checks ignore template name/version and count by paper, model, and input scope
  - show the summary template config path in the AI config status payload/UI text
- Important decisions:
  - template edits are now a local config-file workflow, not an in-app workflow
  - there is no user-facing template name or template version
  - old summaries remain usable in progress counts because template identity/version are no longer part of completion semantics
- Verification:
  - focused Web UI/API template tests: 5 passed, 1 warning
  - full test suite: 159 passed, 1 warning
  - browser verified `phase41` static assets, no template editor/toggle/save controls, no `Template name` text, no horizontal overflow, and Settings shows `config/summary_template.local.json`
  - local API verified `GET /api/summary-templates` returns 404 and `/api/ai/config` reports the summary template config path
- Status: implemented on branch, not yet merged to `main`.

## Phase 36: Merged Daily Status and Single Batch AI Button

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-07-arxiv-local-daily-merged-daily-status.md`
- Scope completed:
  - remove the top-right Settings panel from the web workbench
  - move `Run Summary + Score` into Daily Automation as the only page-level AI batch button
  - make that button run the selected date's full CS scope with all 40 `cs.*` categories
  - remove frontend AI config fetching and all model/template setting display from the main page
  - merge paper, metadata, AI, and backend run state into one compact `Daily Status` component
  - add backend `status.ai` coverage that counts paper-level summary + score completion independent of model/template identity
  - make the Papers row prefer the selected category scope count, avoiding all-category preflight counts in the CS view
  - bump static assets to `phase43`
- Important decisions:
  - API/template configuration remains a local config-file workflow rather than a routine UI setting
  - AI daily progress is now `complete papers / eligible papers`, where complete means the paper has both a complete summary and a complete score
  - top status text should stay compact and avoid mixing all-category preflight counts with CS-scope progress
- Verification:
  - focused Web UI + daily pipeline tests: 3 passed, 1 warning
  - full test suite: 160 passed, 1 warning
  - browser verified `phase43` static assets, no Settings panel, no old `automation-summary`/`pipeline-status` modules, and no horizontal overflow
  - browser verified 2026-06-05 CS status shows `Papers 1196/1196`, `Metadata 1196/1196`, and `AI 0/1196`
  - browser screenshot capture timed out twice, so verification used DOM/layout checks instead of a saved screenshot
- Status: implemented on branch, not yet merged to `main`.

## Phase 37: Search Category Matching and Filter Cleanup

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-07-arxiv-local-daily-search-filter-cleanup.md`
- Scope completed:
  - diagnose why `Tuning long-range interactions in Sr Rydberg atoms` appeared under a `cs` category search
  - fix category filtering so group input like `cs` matches `cs.*` rather than arbitrary substrings
  - keep exact category input like `cs.AI` exact
  - remove `categories_json` from broad text query matching to avoid accidental category substring hits
  - remove `Event`, `Metadata`, and `Summary` dropdown filters from the web search panel
  - bump static assets to `phase44`
- Important decisions:
  - old papers can legitimately appear in a daily list when arXiv reports replacement/cross-list activity for that date
  - score sorting should still rank already scored papers first, but category matching must first be correct
  - backend API support for event/metadata/summary filters remains for compatibility; only the web controls were removed
- Verification:
  - database confirmed `1505.07152` is a 2015 paper with a `2026-06-05 replacement` event in `physics.atom-ph` and a completed AI score
  - focused category/Web UI tests: 3 passed, 1 warning
  - full test suite: 161 passed, 1 warning
  - browser verified `phase44` static assets, removed filter controls, no horizontal overflow, and `2026-06-05 + category=cs` no longer shows the Rydberg physics paper on the first page
- Status: implemented on branch, not yet merged to `main`.

## Phase 38: Grouped Category Picker

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-07-arxiv-local-daily-category-picker.md`
- Scope completed:
  - replace the free-text search category input with a grouped checkbox picker
  - default selected search categories to all 40 `cs.*` categories
  - allow selecting a whole arXiv group or individual child categories
  - add `CS`, `All`, and `Clear` picker actions
  - send selected leaf categories as repeated `category` query parameters
  - extend backend search repository/API to OR multiple category filters
  - bump static assets to `phase45`
- Important decisions:
  - empty category selection means all categories
  - parent category checkboxes are UI conveniences; backend receives leaf category codes
  - single-category API compatibility remains intact
- Verification:
  - focused Web UI/search/API tests: 4 passed, 1 warning
  - full test suite: 162 passed, 1 warning
  - browser verified `phase45` assets, category picker expansion, CS default `50/1198`, Clear all-categories `50/2071`, and CS reset excluding the Rydberg physics paper
- Status: implemented on branch, not yet merged to `main`.

## Phase 39: Chinese Web UI

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-07-arxiv-local-daily-chinese-ui.md`
- Scope completed:
  - translate static web labels, buttons, empty states, modal copy, and navigation text to Chinese
  - translate dynamic daily automation, search, paper detail, AI, prompt preview, discussion, and category picker status text to Chinese
  - add a frontend status display map so raw backend states remain stable while UI shows Chinese state labels
  - keep arXiv category codes, API parameter values, CSS state classes, and database status values unchanged
  - bump static assets to `phase46`
- Important decisions:
  - localization is display-only; no backend protocol, schema, or stored values are translated
  - arXiv category group names are translated, but child category codes remain exact arXiv codes
  - result status tags display Chinese labels while preserving raw values for filtering and state classes
- Verification:
  - JavaScript syntax check passed: `node --check arxiv-local-daily/src/arxiv_local_daily/web/app.js`
  - focused Web UI tests: 2 passed, 1 warning
  - full test suite: 162 passed, 1 warning
  - browser verified `phase46` assets: Chinese title, Daily Automation, search, detail, prompt preview, discussion, and category picker labels rendered; old English labels were absent; no horizontal overflow at the current in-app browser width
- Status: implemented on branch, not yet merged to `main`.

## Phase 40: Cloudflare Tunnel Deployment Package

- Branch: `codex/phase-7-web-ui`
- Plan: `docs/superpowers/plans/2026-06-07-arxiv-local-daily-cloudflare-tunnel-deploy.md`
- Scope completed:
  - add a Dockerfile for running the FastAPI app with Uvicorn inside a Python 3.12 slim container
  - add Docker Compose services for `app` and `cloudflared`
  - keep the app service off the public host network by omitting `ports:` and routing Cloudflare Tunnel to `http://app:8765`
  - mount SQLite data at `/data` and local config files at `/config`
  - add `ARXIV_DAILY_DATABASE` support so deployed SQLite storage can live outside the project tree
  - add `.env.example`, `.dockerignore`, optional named-tunnel cloudflared config template, and local runtime ignore rules
  - add a SQLite-safe backup script that snapshots the DB and packages local config
  - add Chinese deployment docs covering domain setup, Cloudflare Access, startup, logs, backup, update, and troubleshooting
- Important decisions:
  - Cloudflare Tunnel is the public ingress; the app container should not expose `8765` directly to the internet
  - API keys and summary templates remain local config-file workflows, not environment-only deployment secrets
  - backups include both SQLite data and local config because the DB alone is not enough to restore AI behavior
- Verification:
  - focused deployment/config tests: 7 passed
  - full test suite: 169 passed, 1 warning
  - backup script syntax check passed: `bash -n arxiv-local-daily/scripts/backup_sqlite.sh`
  - Compose config expansion passed: `docker compose --env-file .env.example config`
- Status: implemented on branch, not yet merged to `main`.

## Phase 40 Hotfix: Docker Package Web Assets

- Branch: `codex/phase-7-web-ui`
- Scope completed:
  - fix Docker startup crash where installed package lacked `arxiv_local_daily/web`
  - add setuptools package-data config for `web/*.html`, `web/*.js`, and `web/*.css`
  - add a regression test that requires package-data coverage for the static web assets
- Root cause:
  - local tests used `pythonpath = ["src"]`, so the app read static files from the source tree
  - Docker used `pip install .`, so the app read from `site-packages`
  - `pyproject.toml` did not declare the web directory as package data, so `site-packages/arxiv_local_daily/web` was missing
- Verification:
  - focused import/web UI tests with existing venv: 4 passed, 1 warning
  - full test suite with existing venv: 170 passed, 1 warning
  - `uv lock` could not be refreshed in the sandbox because network access to PyPI is blocked and the local uv cache lacks `beautifulsoup4`
- Status: implemented on branch, not yet merged to `main`.

## Phase 40 Hotfix: Docker Build Apt Mirror

- Branch: `codex/phase-7-web-ui`
- Scope completed:
  - add Docker build args for Debian apt mirrors: `DEBIAN_MIRROR` and `DEBIAN_SECURITY_MIRROR`
  - default apt mirrors to TUNA for Debian trixie builds
  - pass apt mirror args through Docker Compose and `.env.example`
  - document that Docker Hub registry mirrors do not affect `apt-get update` inside the image build
  - document Aliyun ECS internal apt mirror overrides
- Important decisions:
  - keep mirror values configurable because the fastest source depends on server provider and region
  - leave Docker Hub mirror configuration as a host-level Docker daemon setting; apt mirror configuration belongs in the Dockerfile/build args
- Verification:
  - focused deployment tests: 7 passed
  - Compose config expansion shows apt mirror build args
  - full test suite with existing venv: 171 passed, 1 warning
- Status: implemented on branch, not yet merged to `main`.

## Phase 40 Hotfix: Docker Build Pip Mirror

- Branch: `codex/phase-7-web-ui`
- Scope completed:
  - add Docker build arg `PIP_INDEX_URL` for Python dependency installation
  - default pip mirror to TUNA PyPI during image builds
  - pass `PIP_INDEX_URL` through Docker Compose and `.env.example`
  - document TUNA, Aliyun, and Tencent Cloud PyPI mirror options
- Important decisions:
  - keep pip mirror configurable because provider-local mirrors are usually faster than one global default
  - use a build-time `--index-url` instead of writing a permanent pip config into the runtime container
- Verification:
  - focused deployment tests: 8 passed
  - Compose config expansion shows `PIP_INDEX_URL` build arg
  - full test suite with existing venv: 172 passed, 1 warning
- Status: implemented on branch, not yet merged to `main`.
