# Date Crawl Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ambiguous refresh-first Daily Automation control with an explicit selected-date crawl launcher that starts background automation for the requested date.

**Architecture:** Keep the existing `/api/daily/automation/start` backend contract. Change the web UI so the primary automation action opens a date launcher dialog, then posts `crawl_mode=auto` and polls status/search. Keep status refresh as a smaller secondary action that only reloads local state.

**Tech Stack:** FastAPI, SQLite, vanilla HTML/CSS/JS, pytest, in-app browser verification.

---

### Task 1: UI Markup

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/index.html`
- Test: `arxiv-local-daily/tests/test_web_ui.py`

- [x] Add a primary `crawl-date-open` button labeled `抓取指定日期`.
- [x] Add a compact `status-refresh` button labeled `刷新状态`.
- [x] Add a modal dialog with `crawl-date-dialog`, `crawl-date-target`, `crawl-date-confirm`, and `crawl-date-cancel`.
- [x] Remove `Refresh Status` as the primary automation button.

### Task 2: UI Behavior

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/app.js`
- Test: `arxiv-local-daily/tests/test_web_ui.py`

- [x] Add `openDateCrawlDialog`, `closeDateCrawlDialog`, and `confirmDateCrawl`.
- [x] Make date step/change only update selected date, status, and search results.
- [x] Start full automation only from the launcher confirm action or category Enter shortcut.
- [x] Keep page load and periodic timer as silent automation/status maintenance for the selected date.

### Task 3: Styling

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/styles.css`
- Test: browser verification

- [x] Style the launcher controls so the main action is obvious and refresh is compact.
- [x] Style the date crawl modal without introducing horizontal overflow.

### Task 4: Documentation and Verification

**Files:**
- Modify: `docs/phases.md`

- [x] Record the phase decision and verification.
- [x] Run focused web UI tests.
- [x] Run full tests.
- [x] Browser verify the launcher and no horizontal overflow.
