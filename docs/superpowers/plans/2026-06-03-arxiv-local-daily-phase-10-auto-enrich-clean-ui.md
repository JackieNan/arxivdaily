# arXiv Local Daily Phase 10 Auto Enrich Clean UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove user-facing metadata enrich controls, automatically enrich metadata after crawl, show all papers by default, and simplify the workbench into a no-overflow reading interface.

**Architecture:** `Crawl` becomes the user-facing ingestion action. After a crawl run is created, FastAPI schedules unified metadata enrichment in the background using all crawled IDs for the date. Search no longer imposes a 50-row UI default, and the web layout moves controls from a left rail into a top action strip above a two-column paper list/detail workspace.

**Tech Stack:** Python 3.12, SQLite, FastAPI BackgroundTasks, vanilla HTML/CSS/JS, pytest.

---

## Decisions Log

- 2026-06-03: Users should not have to understand or manually run Enrich. Metadata completion is an automatic post-crawl responsibility.
- 2026-06-03: OAI and ID API remain internal metadata sources used by unified enrichment.
- 2026-06-03: Summary and score runs should not expose limits in the UI.
- 2026-06-03: Search should show all matching papers by default, not an arbitrary 50.
- 2026-06-03: The left rail is removed. Controls move to a compact top action strip; paper list and detail become the primary workspace.

## Tasks

### Task 1: Auto Metadata After Crawl

- [x] Add API test proving `POST /api/crawl/run` schedules unified metadata enrichment after crawl.
- [x] Implement background helper and app wiring.
- [x] Make unified enrichment accept `limit=None` to process all crawled IDs.
- [x] Run focused API tests.

### Task 2: All-Results Search

- [x] Add repository/API tests proving search returns more than 50 rows by default.
- [x] Update search repository and API limit handling.
- [x] Remove the UI `limit=50` parameter.
- [x] Run focused search/API tests.

### Task 3: Clean UI

- [x] Add web UI tests proving no Enrich panel, no left rail, no summary/score limit fields, and top action strip exists.
- [x] Move Crawl, Summary, Score, and Settings into top controls.
- [x] Remove user-facing `Enrich Metadata`, `Run Legacy Metadata`, `Papers to enrich`, `OAI pages`, `Summary limit`, and `Score limit`.
- [x] Rework search controls to wrap inside the center panel without horizontal overflow.
- [x] Make paper cards/detail wrap long LaTeX-like text without horizontal scrolling.
- [x] Run focused web UI tests.

### Task 4: Verification and Recording

- [x] Run full `uv run pytest -v`.
- [x] Restart local server on `127.0.0.1:8765`.
- [x] Browser smoke test layout presence and no horizontal document overflow.
- [x] Update README and `docs/phases.md`.
- [x] Commit Phase 10 locally.

## Verification Log

- Focused Phase 10 red tests initially failed for missing auto metadata queueing, SQLite `limit=None`, old left-rail UI, and `limit=50` search JS.
- Focused API/search/web UI tests after implementation: 5 passed, 1 warning.
- Focused all-candidate summary/score/CLI default tests: 3 passed.
- Full suite: `uv run pytest -v` -> 105 passed, 1 warning.
- Browser desktop smoke at `http://127.0.0.1:8765/`: `top-actions` present; `left-rail`, `enrich-panel`, `metadata-enrich`, `summary-limit`, and `score-limit` absent; no document horizontal overflow.
- Browser mobile smoke at 390px width: no document horizontal overflow; search controls fit inside their container.
