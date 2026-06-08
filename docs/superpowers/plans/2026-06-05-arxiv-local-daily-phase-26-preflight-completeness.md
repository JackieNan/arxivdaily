# Preflight Completeness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a preflight phase that estimates and verifies the day's paper count before the main crawl, then expose evidence users can inspect.

**Architecture:** Preflight is separate from `crawl_runs` so it cannot pollute crawl completeness. It fetches listing pages, verifies listing dates and declared counts, treats explicit arXiv `No updates today.` pages as verified zero-count categories, persists per-category evidence, and stores aggregate distinct-paper counts. Daily automation runs preflight before crawl and status/UI display the preflight evidence.

**Tech Stack:** FastAPI, SQLite, pytest, local vanilla HTML/CSS/JS.

---

### Task 1: Preflight Persistence

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/db.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/repositories.py`
- Test: `arxiv-local-daily/tests/test_db.py`

- [x] Add `crawl_preflight_runs` and `crawl_preflight_sources`.
- [x] Store aggregate counts and per-category evidence independently of `crawl_runs`.

### Task 2: Preflight Runner

**Files:**
- Create: `arxiv-local-daily/src/arxiv_local_daily/crawler/preflight.py`
- Test: `arxiv-local-daily/tests/test_preflight.py`

- [x] Fetch category listings.
- [x] Verify page date matches requested date.
- [x] Parse declared listing count and actual IDs.
- [x] Treat explicit empty arXiv category pages as complete zero-count sources.
- [x] Aggregate distinct arXiv IDs.

### Task 3: API and Automation

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/api.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/services.py`
- Test: `arxiv-local-daily/tests/test_api.py`

- [x] Run preflight before daily crawl in automation.
- [x] Record visible waiting status if arXiv current-date probing fails.
- [x] Add `GET /api/preflight/{date}`.
- [x] Include latest preflight in `GET /api/daily/status/{date}`.

### Task 4: UI and Verification Guidance

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/index.html`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/app.js`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/styles.css`
- Modify: `docs/phases.md`
- Test: `arxiv-local-daily/tests/test_web_ui.py`

- [x] Display preflight total/evidence in the automation note.
- [x] Make Papers progress use preflight total when available.
- [x] Document how the user verifies full crawl count.

### Verification

- [x] Focused preflight/API/web tests pass.
- [x] `uv run pytest -v` passes.
- [x] Browser shows preflight-backed paper count and no horizontal overflow.
