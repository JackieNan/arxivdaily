# arXiv Local Daily Phase 8 OAI Metadata Mirror Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move metadata enrichment off the fragile on-demand legacy arXiv API path by adding listing-title fallback, OAI-PMH metadata synchronization, and local background sync status.

**Architecture:** Daily crawl remains the source of truth for "all papers today" and immediately stores IDs/events plus any title available in listing HTML. OAI-PMH sync runs in the background, stores sync-run progress in SQLite, parses arXiv metadata records, and upserts complete paper metadata into the same paper table. The legacy arXiv API metadata worker remains as a fallback only.

**Tech Stack:** Python 3.12, SQLite, FastAPI BackgroundTasks, httpx-backed existing `ArxivHttpClient`, XML ElementTree, vanilla web UI, pytest.

---

## File Structure

- Modify `arxiv-local-daily/src/arxiv_local_daily/models.py`: add optional listing title to `ParsedDailyEvent`.
- Modify `arxiv-local-daily/src/arxiv_local_daily/crawler/parser.py`: extract listing titles from daily pages.
- Create `arxiv-local-daily/src/arxiv_local_daily/crawler/oai.py`: OAI-PMH URL builder, parser, and client.
- Modify `arxiv-local-daily/src/arxiv_local_daily/db.py`: add `metadata_sync_runs` table.
- Modify `arxiv-local-daily/src/arxiv_local_daily/repositories.py`: persist listing titles and metadata sync run status.
- Modify `arxiv-local-daily/src/arxiv_local_daily/services.py`: add `run_oai_metadata_sync`.
- Modify `arxiv-local-daily/src/arxiv_local_daily/api.py`: add OAI sync start/status/list routes.
- Modify `arxiv-local-daily/src/arxiv_local_daily/web/index.html`: add OAI sync controls.
- Modify `arxiv-local-daily/src/arxiv_local_daily/web/app.js`: start/poll OAI sync and render status.
- Modify `arxiv-local-daily/src/arxiv_local_daily/web/styles.css`: compact sync status styling if needed.
- Add tests and fixtures under `arxiv-local-daily/tests/`.
- Update `docs/phases.md` and README.

## Tasks

### Task 1: Daily Listing Title Fallback

- [x] Add parser tests proving listing titles are extracted.
- [x] Add repository/ingestion tests proving crawled titles are stored immediately.
- [x] Implement `ParsedDailyEvent.title`.
- [x] Update parser and paper repository.
- [x] Run focused parser/ingestion tests.

### Task 2: OAI-PMH Parser and Client

- [x] Add OAI ListRecords fixture with arXiv metadata and a resumption token.
- [x] Add tests for OAI URL construction and XML parsing.
- [x] Implement `crawler/oai.py`.
- [x] Run focused OAI parser tests.

### Task 3: OAI Metadata Sync Service

- [x] Add `metadata_sync_runs` schema and repository tests.
- [x] Implement sync-run repository methods.
- [x] Add service tests proving OAI metadata upserts paper metadata and records progress.
- [x] Implement `run_oai_metadata_sync`.
- [x] Run focused service tests.

### Task 4: API and Web UI

- [x] Add API tests for starting a background OAI sync and reading sync status.
- [x] Implement FastAPI background task route and status endpoints.
- [x] Add web UI controls for `Start OAI Sync` and sync status.
- [x] Run focused API/web tests.

### Task 5: Verification and Recording

- [x] Run full `uv run pytest -v`.
- [x] Restart local `uvicorn` on `127.0.0.1:8765`.
- [x] Smoke test `POST /api/metadata/oai-sync/start` and `GET /api/metadata/oai-sync/runs/{id}`.
- [x] Update README and `docs/phases.md`.
- [x] Commit Phase 8 locally.
