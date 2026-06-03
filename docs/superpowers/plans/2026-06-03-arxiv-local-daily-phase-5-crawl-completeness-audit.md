# arXiv Local Daily Phase 5 Crawl Completeness Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for each behavior change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reliable audit layer that reports whether a daily crawl has covered every expected category and can retry failed or missing categories.

**Architecture:** Use existing `crawl_runs` and `crawl_run_sources` rows as the source of truth. Completeness is computed across all runs for a date: a category is complete if any run fetched and parsed it successfully; failed categories remain retry candidates until a later run completes them. Optional expected category lists allow the audit to detect categories that were never attempted.

**Tech Stack:** Python 3.12+, stdlib `sqlite3`, Pydantic, pytest, FastAPI.

---

## File Structure

- Modify `arxiv-local-daily/src/arxiv_local_daily/models.py`: add crawl audit result models if useful for typed boundaries.
- Modify `arxiv-local-daily/src/arxiv_local_daily/repositories.py`: add source listing methods for a date and category status rollups.
- Create `arxiv-local-daily/src/arxiv_local_daily/crawler/audit.py`: compute completeness reports and retry target categories.
- Modify `arxiv-local-daily/src/arxiv_local_daily/services.py`: expose audit and retry services.
- Modify `arxiv-local-daily/src/arxiv_local_daily/api.py`: add `GET /api/crawl/completeness/{date}` and `POST /api/crawl/retry-failed`.
- Modify `arxiv-local-daily/src/arxiv_local_daily/cli.py`: add `crawl-audit` and `crawl-retry-failed` commands.
- Modify `arxiv-local-daily/README.md`: document audit and retry commands.
- Modify `docs/phases.md`: record Phase 5 status and verification.
- Create `arxiv-local-daily/tests/test_crawl_audit.py`: report and retry-target tests.
- Modify `arxiv-local-daily/tests/test_api.py`: audit and retry API tests.
- Modify `arxiv-local-daily/tests/test_cli.py`: audit/retry CLI parsing tests.

---

## Tasks

### Task 1: Crawl Completeness Report

- [x] Write tests showing no-run dates return status `no_run`.
- [x] Write tests showing all complete category sources return status `complete`.
- [x] Write tests showing failed categories return status `partial` and list retry candidates.
- [x] Write tests showing optional expected categories detect missing categories.
- [x] Implement date source rollup and `build_crawl_completeness_report`.

### Task 2: Retry Failed or Missing Categories

- [x] Write tests showing a retry service calls the crawl runner with categories whose effective status is not complete.
- [x] Write tests showing a later successful retry makes the combined audit complete.
- [x] Implement `retry_incomplete_crawl_categories_for_date`.

### Task 3: CLI/API Controls

- [x] Write CLI parsing tests for `crawl-audit --date ... --expected-category ...`.
- [x] Write CLI parsing tests for `crawl-retry-failed --date ...`.
- [x] Write API tests for `GET /api/crawl/completeness/{date}`.
- [x] Write API tests for `POST /api/crawl/retry-failed`.
- [x] Implement CLI/API controls.

### Task 4: Verification and Recording

- [x] Run focused crawl audit tests.
- [x] Run full `uv run pytest -v`.
- [x] Update README with audit/retry usage.
- [x] Record Phase 5 in `docs/phases.md`.
- [x] Commit Phase 5 locally.
