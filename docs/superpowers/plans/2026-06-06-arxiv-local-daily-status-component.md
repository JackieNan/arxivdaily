# Pipeline Status Component Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Daily Automation progress bars with a compact current-status component.

**Architecture:** Keep the existing daily status API and summary metrics. Swap the progress-bar DOM for three stage status panels, then render each stage from the same crawl, metadata, summary, score, and preflight fields already returned by `GET /api/daily/status/{date}`.

**Tech Stack:** Vanilla HTML/CSS/JS, FastAPI static assets, pytest web UI tests, in-app browser verification.

---

### Task 1: Replace Progress Markup

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/index.html`
- Test: `arxiv-local-daily/tests/test_web_ui.py`

- [x] Remove `automation-progress`, progress tracks, fills, and labels.
- [x] Add `pipeline-status` with Papers, Metadata, and AI stage status nodes.

### Task 2: Render Status Instead of Bars

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/app.js`
- Test: `arxiv-local-daily/tests/test_web_ui.py`

- [x] Replace `renderPipelineProgress` and `renderProgressBar` with `renderPipelineStatus` and `renderStageStatus`.
- [x] Render stage state, count, and short detail text for Papers, Metadata, and AI.
- [x] Keep preflight evidence visible in the Papers stage detail.

### Task 3: Style Status Component

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/styles.css`
- Test: browser verification

- [x] Remove progress track/fill styles.
- [x] Add stage status panel and state badge styles for idle, running, waiting, partial, complete, and failed.
- [x] Stack status panels on narrow screens.

### Task 4: Verification

**Files:**
- Modify: `docs/phases.md`

- [x] Focused web UI tests pass.
- [x] Full test suite passes.
- [x] Browser shows status component with no horizontal overflow.
