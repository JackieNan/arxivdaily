# arXiv Local Daily Phase 9 Complete Enrich Score UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the app prove daily crawl completeness, run one unified metadata enrichment flow, score summarized papers for reading priority, and reorganize the web UI into a practical three-column workbench.

**Architecture:** The crawl listing remains the source of truth for "today's paper set"; completeness is audited from category coverage, source fetch status, page-declared counts, and repeat-run diffs. Metadata enrichment becomes one user-facing operation that compares crawl IDs against OAI and ID API sources, merges complete fields into `papers`, and records missing/mismatch details. Summary template controls move into Settings, and LLM scoring is stored separately from summaries so search can sort by reading priority.

**Tech Stack:** Python 3.12, SQLite, FastAPI, vanilla HTML/CSS/JS, pytest, existing arXiv HTTP/OAI/API clients, existing OpenAI-compatible LLM client.

---

## Decisions Log

- 2026-06-03: `Crawl` is the completeness source. OAI/API metadata cannot prove that the daily listing was fully crawled.
- 2026-06-03: OAI and ID API are not separate user workflows. They are metadata sources inside one `Enrich Metadata` operation.
- 2026-06-03: The UI should hide protocol names unless needed for diagnostics. Users should see matched/missing/mismatch/merged counts.
- 2026-06-03: Summary template controls belong in a Settings panel, not inside Enrich.
- 2026-06-03: Paper scoring is a reading-priority score, not an objective paper-quality score. Default score is 0-100 with rubric dimensions: relevance, novelty, technical_depth, evidence, actionability.
- 2026-06-03: Search default ordering should prioritize scored papers when scores exist, then fall back to date/id ordering.

## File Structure

- Modify `arxiv-local-daily/src/arxiv_local_daily/models.py`
  - Add crawl source count fields to `CrawlSourceInput`.
  - Add scoring input/result models.
- Modify `arxiv-local-daily/src/arxiv_local_daily/crawler/parser.py`
  - Add `parse_daily_listing_count`.
- Modify `arxiv-local-daily/src/arxiv_local_daily/crawler/live.py`
  - Add paginated listing URL builder and source count capture.
- Modify `arxiv-local-daily/src/arxiv_local_daily/db.py`
  - Add `expected_count`, `missing_count`, and paging fields to crawl sources.
  - Add `metadata_enrichment_runs`, `metadata_source_records`, `metadata_merge_reports`, and `paper_scores`.
- Modify `arxiv-local-daily/src/arxiv_local_daily/repositories.py`
  - Store source expected counts.
  - Add unified enrichment and scoring repositories.
  - Return scores from search and detail APIs.
- Modify `arxiv-local-daily/src/arxiv_local_daily/services.py`
  - Add unified `enrich_metadata_for_date_unified`.
  - Add `score_papers_for_date`.
  - Keep legacy metadata/OAI helpers as internal building blocks.
- Modify `arxiv-local-daily/src/arxiv_local_daily/summary.py`
  - Add scoring prompt builder and parser.
- Modify `arxiv-local-daily/src/arxiv_local_daily/api.py`
  - Route `/api/metadata/enrich` to the unified flow.
  - Add `/api/scores/run`.
  - Add search sort parameter.
- Modify web files under `arxiv-local-daily/src/arxiv_local_daily/web/`
  - Three-column layout: left controls, center search, right fixed paper detail.
  - Move template controls to Settings.
  - Redesign search cards and paper detail.
- Add/modify tests under `arxiv-local-daily/tests/`.
- Update `docs/phases.md` and `arxiv-local-daily/README.md`.

## Tasks

### Task 1: Crawl Completeness Proof

- [x] Add parser tests for page-declared counts.
- [x] Add DB/repository tests for `expected_count`, `missing_count`, and source rows.
- [x] Implement schema migration and model fields.
- [x] Update ingestion and audit so a complete HTTP source with `parsed_count < expected_count` is `incomplete`.
- [x] Run focused crawl/audit tests.

### Task 2: Unified Metadata Enrichment

- [x] Add tests for a unified enrich run that merges ID API and OAI metadata for crawled IDs.
- [x] Add tests for missing and mismatch reports.
- [x] Implement enrichment tables and repository methods.
- [x] Implement service that fetches from both sources, compares against crawl IDs, chooses the more complete metadata, and writes `papers`.
- [x] Replace the main metadata API route/UI action with the unified flow while preserving legacy diagnostics.
- [x] Run focused enrichment/API tests.

### Task 3: Paper Scoring

- [x] Add tests for scoring prompt construction and JSON parsing.
- [x] Add DB/repository tests for `paper_scores`.
- [x] Add service tests for scoring papers and storing score/rationale/action.
- [x] Add API route for scoring run.
- [x] Update search repository so `sort=score` orders by latest score descending.
- [x] Run focused scoring/search tests.

### Task 4: Web UI Reorganization

- [x] Add static UI tests for Settings panel, unified Enrich, score controls, three-column layout markers, search score rendering, and fixed detail panel.
- [x] Move template/model/summary controls to Settings.
- [x] Replace OAI/legacy split buttons with one `Enrich Metadata` action and diagnostic JSON.
- [x] Add score button and score sort control.
- [x] Redesign search cards with 15-16px two-line title, compact tags, one-line abstract/error hint, and score badge.
- [x] Redesign paper detail with top metadata strip and scrollable sections.
- [x] Run focused web UI tests.

### Task 5: Verification, Logs, Commit

- [x] Run full `uv run pytest -v`.
- [x] Restart local server on `127.0.0.1:8765`.
- [x] Use in-app browser to verify the three-column layout. Direct click smoke was blocked by the in-app browser coordinate translation layer; static UI tests cover click handler wiring.
- [x] Update README and `docs/phases.md` with all Phase 9 decisions and important implementation details.
- [x] Commit Phase 9 locally.

## Verification Log

- `uv run pytest -v`: 100 passed, 1 warning.
- Local server restarted on `http://127.0.0.1:8765/`.
- Browser layout smoke confirmed `left-rail`, `settings-panel`, `metadata-enrich`, `score-run`, `search-sort`, `right-rail`, and `paper-detail` are present. Direct browser click was blocked by plugin coordinate translation.
