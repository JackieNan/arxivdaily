# arXiv Local Daily Phase 15 Daily Pipeline and Summary Completion

**Goal:** Make daily completeness include the AI summary layer, so a day is not considered operationally complete until crawl, metadata, Chinese summary/keywords, and score coverage are all visible.

## Decisions Log

- 2026-06-03: AI summaries are part of the daily reliability loop, not just a manual Settings action.
- 2026-06-03: The daily pipeline should orchestrate crawl, crawl audit/retry, unified metadata enrichment, summary generation, and scoring.
- 2026-06-03: Daily status should be read-only and explain coverage separately for crawl, metadata, summary, and score.
- 2026-06-03: Summary completion is measured over daily papers with complete metadata and non-empty abstracts.
- 2026-06-03: Missing summary templates should be reported as a daily blocker instead of being hidden behind a generic failed state.
- 2026-06-03: The complex PDF-reading agent remains a later phase; Phase 15 focuses on abstract/metadata-based daily summaries and triage scores.

## Tasks

- [x] Add service tests for daily summary and score coverage.
- [x] Add service tests for running the daily pipeline through summary and score.
- [x] Add API tests for daily status and daily pipeline run.
- [x] Add web UI tests for Daily panel controls and API wiring.
- [x] Implement `get_daily_pipeline_status`.
- [x] Implement `run_daily_pipeline`.
- [x] Add `/api/daily/status/{date}`.
- [x] Add `/api/daily/pipeline/run`.
- [x] Add a compact Daily panel to the workbench.
- [x] Run focused Phase 15 tests.
- [x] Run full pytest suite.
- [x] Restart local server and browser-smoke Daily panel.
- [x] Commit Phase 15 locally.

## Verification Log

- Focused Phase 15 red tests initially failed because `get_daily_pipeline_status` and `run_daily_pipeline` did not exist, and the web UI had no Daily panel/API wiring.
- Focused Phase 15 tests after implementation: 6 passed, 1 warning.
- Full suite: `uv run pytest -v` -> 109 passed, 1 warning.
- Browser smoke on `http://127.0.0.1:8765/` at 599px viewport: Daily panel rendered with `Daily Status` and `Run Daily Pipeline`, document/Daily/Crawl/Settings/Search/detail had no horizontal overflow, and medium-width top controls used a two-row layout instead of three full-width stacked panels.
- Local API smoke: `GET /api/daily/status/2026-06-03?model=local` returned `200` and exposed crawl, metadata, summary, score, and blocker fields. Curl needed `require_escalated` because the sandboxed shell could not reach the local port.
