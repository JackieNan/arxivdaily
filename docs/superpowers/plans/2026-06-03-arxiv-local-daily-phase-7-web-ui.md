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

- [ ] Write tests for `GET /` returning the workbench HTML.
- [ ] Write tests for `/static/app.js` and `/static/styles.css`.
- [ ] Implement static asset serving in `create_app`.

### Task 2: Workbench Shell

- [ ] Create an app shell with date, crawl, audit, metadata, summary, search, result list, and detail regions.
- [ ] Add responsive CSS with compact controls and stable layout dimensions.
- [ ] Verify text does not overflow compact controls.

### Task 3: Frontend Interactions

- [ ] Implement crawl run and retry controls.
- [ ] Implement crawl audit display.
- [ ] Implement metadata and summary run controls.
- [ ] Implement paper search and filters.
- [ ] Implement paper detail, summaries, and discussions.

### Task 4: Verification and Recording

- [ ] Run focused web UI tests.
- [ ] Run full `uv run pytest -v`.
- [ ] Start local `uvicorn` server.
- [ ] Verify UI in browser at localhost.
- [ ] Update README with web UI usage.
- [ ] Record Phase 7 in `docs/phases.md`.
- [ ] Commit Phase 7 locally.
