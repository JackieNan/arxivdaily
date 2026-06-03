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
