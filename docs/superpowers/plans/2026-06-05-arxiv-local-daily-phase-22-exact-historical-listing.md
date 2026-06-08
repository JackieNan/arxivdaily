# Exact Historical Listing Crawl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch exact earlier-day arXiv daily listing events from historical listing/archive pages instead of treating OAI metadata records as the daily list.

**Architecture:** Add a historical listing parser that extracts only one requested date from an arXiv monthly listing page, then add a crawler mode that fetches `/list/{category}/{yymm}` pages with pagination. Daily automation will use this crawler for earlier selected dates, then run metadata completion and AI triage as before. OAI historical records remain as metadata-only fallback rows until exact listing rows are available.

**Tech Stack:** Python, FastAPI, SQLite, httpx mock transports, BeautifulSoup parser, vanilla JS web workbench, pytest.

---

### Task 1: Historical Listing Parser

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/crawler/parser.py`
- Test: `arxiv-local-daily/tests/test_parser.py`

- [ ] Add tests for `parse_historical_listing_for_date` using a fixture-like HTML sample with two dates.
- [ ] Verify the test fails because the parser function does not exist.
- [ ] Implement date-section tracking that supports both `New submissions for Fri, 5 Jun 2026` headings and `Fri, 5 Jun 2026` followed by event-section headings.
- [ ] Return only target-date `new`, `cross-list`, and `replacement` events.
- [ ] Add `parse_listing_dates` so the crawler can know whether a paginated page has already passed the target date.

### Task 2: Historical Listing Crawler

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/crawler/live.py`
- Test: `arxiv-local-daily/tests/test_live_crawl.py`

- [ ] Add tests for `build_historical_listing_url`.
- [ ] Add tests for `run_historical_listing_crawl` fetching category monthly pages and writing exact listing events with mode `historical-listing`.
- [ ] Add tests that the crawler deletes `historical` event rows for categories where exact listing rows were successfully crawled, without deleting paper metadata.
- [ ] Add tests for pagination stopping once the page dates are older than the target date.
- [ ] Implement URL construction as `/list/{category}/{yymm}?skip={skip}&show={page_size}`.
- [ ] Implement per-category source rows with `complete`, `failed`, and `incomplete` statuses.

### Task 3: Daily Automation Uses Exact Listing

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/api.py`
- Test: `arxiv-local-daily/tests/test_api.py`

- [ ] Update historical automation tests so `crawl_mode="historical"` calls the historical listing crawler, then metadata completion, then AI triage when metadata is complete.
- [ ] Keep old OAI historical crawl service available as an internal metadata collection helper, but remove it from normal daily automation.
- [ ] Ensure `historical_max_pages` still controls historical listing pagination.

### Task 4: Crawl Audit Listing Scope

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/crawler/audit.py`
- Test: `arxiv-local-daily/tests/test_crawl_audit.py`

- [ ] Add a test proving `historical-oai` runs do not satisfy daily crawl completeness.
- [ ] Keep `historical-listing`, `all-categories`, `single-source`, and `retry-incomplete` rows visible to crawl completeness.
- [ ] This prevents old OAI metadata runs from making earlier dates look fully crawled before exact listing rows exist.

### Task 5: Documentation and Verification

**Files:**
- Modify: `docs/phases.md`
- Modify: `arxiv-local-daily/README.md`

- [ ] Document Phase 22 and the distinction between historical listing rows and OAI metadata records.
- [ ] Run focused tests for parser/crawler/API/audit.
- [ ] Run `uv run pytest -v`.
- [ ] Restart the local app server on `http://127.0.0.1:8765/`.
- [ ] Commit with `feat: crawl exact historical listings`.

## Verification

- Focused parser/live crawl/API/audit tests: 8 passed, 1 warning.
- `uv run pytest -v`: 131 passed, 1 warning.
