# arXiv Local Daily Phase 14 UI Density and Detail Focus

**Goal:** Tighten the local workbench layout so settings/crawl controls stay compact, the paper list stays narrow and readable, and the paper detail panel receives more first-screen space.

## Decisions Log

- 2026-06-03: Selecting a paper should not spam the top operation log with `Loaded <id>`; only meaningful operation failures should be recorded.
- 2026-06-03: The paper detail panel is the primary reading surface, so the desktop grid should allocate more width to the right detail rail than to the search list.
- 2026-06-03: Search filters should use stable two-column controls on desktop, with the query and search action spanning the full filter width. This keeps option text readable without horizontal scrolling.
- 2026-06-03: Settings and Crawl remain visible at the top, but their controls, buttons, badges, and diagnostic text should use denser sizing.
- 2026-06-03: Local fallback LaTeX rendering should use a plain serif style instead of an ornate or italic math script look.

## Tasks

- [x] Add web UI regression tests for removed `Loaded` status logging.
- [x] Add web UI regression tests for the detail-focused desktop grid and wider search filter controls.
- [x] Add web UI regression tests for the plainer fallback math font.
- [x] Remove the paper-selection `Loaded <id>` operation log write.
- [x] Tighten the Crawl and Settings control strip.
- [x] Narrow the search/list column and widen the paper detail column.
- [x] Make search controls fit without horizontal scrolling.
- [x] Replace fallback math styling with a quieter serif font.
- [x] Run focused web UI tests.
- [x] Run full pytest suite.
- [x] Restart the local server and browser-smoke the layout.
- [x] Commit Phase 14 locally.

## Verification Log

- Focused web UI red test initially failed because `app.js` still wrote `Loaded ${arxivId}` to the operation log.
- Focused web UI tests after implementation: 2 passed, 1 warning.
- Full suite: `uv run pytest -v` -> 105 passed, 1 warning.
- Browser smoke on `http://127.0.0.1:8765/` at 599px viewport: document, Settings, Crawl, Search, and detail rail reported no horizontal overflow; operation log was capped at 84px and scrollable; operation log did not contain a `Loaded <id>` paper-selection message.
- Browser screenshot capture timed out twice, so screenshot output was not used as verification evidence.
