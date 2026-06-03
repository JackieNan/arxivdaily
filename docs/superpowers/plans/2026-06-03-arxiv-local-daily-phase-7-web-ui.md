# arXiv Local Daily Phase 7 Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for each behavior change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a usable local web workbench for crawling, auditing, searching, inspecting papers, and recording discussions.

**Architecture:** Serve a static HTML/CSS/JavaScript app from the existing FastAPI application. Keep API routes under `/api/*`; serve the UI at `/` and assets under `/static/*`. The UI should be dense and operational: crawl controls, audit status, search/filter controls, paper results, detail drawer, summary sections, and discussion messages.

**Tech Stack:** Python 3.12+, FastAPI/Starlette static files, vanilla HTML/CSS/JavaScript, pytest, Browser verification for local UI smoke checks.

---

## File Structure

- Modify `arxiv-local-daily/src/arxiv_local_daily/api.py`: mount static assets and serve the workbench index at `/`.
- Create `arxiv-local-daily/src/arxiv_local_daily/web/index.html`: app shell and controls.
- Create `arxiv-local-daily/src/arxiv_local_daily/web/styles.css`: responsive operational UI styling.
- Create `arxiv-local-daily/src/arxiv_local_daily/web/app.js`: API calls and interaction logic.
- Modify `arxiv-local-daily/README.md`: document web UI startup.
- Modify `docs/phases.md`: record Phase 7 status and verification.
- Create `arxiv-local-daily/tests/test_web_ui.py`: static UI serving tests.

---

## Tasks

### Task 1: Serve Local Web UI

- [x] Write tests for `GET /` returning the workbench HTML.
- [x] Write tests for `/static/app.js` and `/static/styles.css`.
- [x] Implement static asset serving in `create_app`.

### Task 2: Workbench Shell

- [x] Create an app shell with date, crawl, audit, metadata, summary, search, result list, and detail regions.
- [x] Add responsive CSS with compact controls and stable layout dimensions.
- [x] Verify text does not overflow compact controls.

### Task 3: Frontend Interactions

- [x] Implement crawl run and retry controls.
- [x] Implement crawl audit display.
- [x] Implement metadata and summary run controls.
- [x] Implement paper search and filters.
- [x] Implement paper detail, summaries, and discussions.

### Task 4: Verification and Recording

- [x] Run focused web UI tests.
- [x] Run full `uv run pytest -v`.
- [x] Start local `uvicorn` server.
- [x] Verify UI in browser at localhost.
- [x] Update README with web UI usage.
- [x] Record Phase 7 in `docs/phases.md`.
- [x] Commit Phase 7 locally.

### Task 5: Operation Error Details

- [x] Reproduce missing summary template as a failing API/UI visibility test.
- [x] Return structured `400` API detail for summary template business errors.
- [x] Add visible operation detail areas for enrich and search flows.
- [x] Parse JSON error payloads in the web UI instead of showing generic failed states.
- [x] Verify search still returns `200` and metadata `failed` badges are paper state, not request failure.

### Task 6: Enrich Usability

- [x] Reproduce metadata runs returning `200` with all papers failed but no visible error reason.
- [x] Return the metadata client error in the enrichment result payload.
- [x] Clarify the metadata limit as max papers per run.
- [x] Add a UI action to create a default `daily_research` summary template.
- [x] Keep background search refresh from overwriting enrich operation details.
