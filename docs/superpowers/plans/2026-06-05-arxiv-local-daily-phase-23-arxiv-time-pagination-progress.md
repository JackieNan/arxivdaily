# arXiv Time, Pagination, and Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make daily automation use arXiv's current listing date as the time source, paginate paper results, improve date navigation, add source links, and show lightweight progress.

**Architecture:** Add backend arXiv date detection for automation mode selection, extend search API with page/page_size/total metadata, and expose progress from existing crawl/metadata/AI status fields. The web UI will send `crawl_mode=auto`, add previous/next date controls, render paginated result lists, add arXiv links, and draw a simple colored progress line.

**Tech Stack:** Python, FastAPI, SQLite, BeautifulSoup parser, pytest, vanilla HTML/CSS/JS.

---

### Task 1: arXiv-Date-Based Automation

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/crawler/live.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/api.py`
- Test: `arxiv-local-daily/tests/test_live_crawl.py`
- Test: `arxiv-local-daily/tests/test_api.py`

- [ ] Add tests for resolving current arXiv listing date from `/list/{category}/new`.
- [ ] Add API tests proving `crawl_mode=auto` chooses daily, historical, or waiting based on arXiv current date.
- [ ] Implement `fetch_current_arxiv_listing_date`.
- [ ] Make daily automation default to `auto`.

### Task 2: Paginated Search

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/repositories.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/api.py`
- Test: `arxiv-local-daily/tests/test_search_discussion.py`
- Test: `arxiv-local-daily/tests/test_api.py`

- [ ] Add repository/API tests for `page`, `page_size`, `total`, `total_pages`, `has_next`, and `has_prev`.
- [ ] Implement limit/offset pagination while preserving existing filters and sort.

### Task 3: Web UI Controls

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/index.html`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/app.js`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/styles.css`
- Test: `arxiv-local-daily/tests/test_web_ui.py`

- [ ] Add previous/next date buttons.
- [ ] Add pagination buttons and page label.
- [ ] Make paper cards and detail show arXiv source links.
- [ ] Add simple colored progress line from daily status.
- [ ] Make UI send `crawl_mode=auto`.

### Task 4: Documentation and Verification

**Files:**
- Modify: `docs/phases.md`
- Modify: `arxiv-local-daily/README.md`

- [ ] Document Phase 23.
- [ ] Run focused tests.
- [ ] Run `uv run pytest -v`.
- [ ] Restart the local app server.
- [ ] Commit with `feat: add arxiv-time pagination progress`.

## Verification

- Focused Phase 23 tests: 57 passed, 1 warning.
- `uv run pytest -v`: 136 passed, 1 warning.
