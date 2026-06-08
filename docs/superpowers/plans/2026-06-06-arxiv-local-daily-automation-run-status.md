# Automation Run Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or equivalent stepwise implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make selected-date crawl launches visibly traceable from the UI: after the user clicks `开始抓取`, the app must show whether the backend job started, its persistent run id, current step, terminal state, and any blocker/error.

**Architecture:** Add a persistent `daily_automation_runs` table and repository. The daily automation API creates a queued run before scheduling background work. The background worker updates that run at each major step. `GET /api/daily/status/{date}` returns the latest automation run so the web UI can render a Backend status card and poll quickly while the run is active.

**Tech Stack:** SQLite, FastAPI `BackgroundTasks`, vanilla JS status polling, pytest API/db/web UI tests, in-app browser verification.

---

### Task 1: Persist Automation Runs

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/db.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/repositories.py`
- Test: `arxiv-local-daily/tests/test_db.py`

- [x] Add `daily_automation_runs`.
- [x] Store date, crawl mode, status, current step, timestamps, template/model, and error text.
- [x] Add create, update, and latest-for-date repository methods.

### Task 2: Update Backend Status During Daily Automation

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/api.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/services.py`
- Test: `arxiv-local-daily/tests/test_api.py`

- [x] Return `automation_run_id` from `POST /api/daily/automation/start`.
- [x] Mark runs `running` at arXiv date check, preflight, crawl, metadata, and AI steps.
- [x] Mark waiting states for arXiv date blockers and metadata blockers.
- [x] Mark zero-paper selected dates as a visible terminal `complete/no_papers` state instead of leaving the UI ambiguous.
- [x] Include the latest automation run in `GET /api/daily/status/{date}`.

### Task 3: Render Backend Run State in the UI

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/index.html`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/app.js`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/styles.css`
- Test: `arxiv-local-daily/tests/test_web_ui.py`

- [x] Add a Backend card to the status component.
- [x] Immediately render queued run id after `开始抓取`.
- [x] Poll status every 2.5 seconds while the latest automation run is queued or running.
- [x] Stop fast polling once the run is complete, waiting, or failed.
- [x] Keep the status grid responsive without horizontal overflow.

### Task 4: Verification

**Files:**
- Modify: `docs/phases.md`

- [x] Focused API/db/web UI tests pass.
- [x] Full test suite passes.
- [x] Browser verification confirms run id and current step appear immediately after launch.
- [x] Browser verification confirms active polling updates the Backend card to the terminal state.

### Observed Follow-Up

- For the user's 2026-06-04 example, the new status surface shows the backend did start and ended at `complete/no_papers`.
- The local crawl evidence still looks suspicious: historical source rows previously recorded 0 papers for 2026-06-04 after archive-page lookup failures. The next backend-correctness phase should stop treating ambiguous historical archive failures as clean complete zero-paper crawls.
