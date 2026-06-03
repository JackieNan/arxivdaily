# arXiv Local Daily Phase 12 Search Scope Toggle Plan

**Goal:** Make it explicit whether the paper list is showing the selected day or the whole local repository, and allow switching between those two scopes.

## Decisions Log

- 2026-06-03: The existing web paper list is already date-scoped by default because search sends the selected date.
- 2026-06-03: The UI should make the scope explicit with a `当日 / 总揽` switch.
- 2026-06-03: `当日` keeps sending the selected date to `/api/search/papers`; `总揽` omits `date` and searches the whole local database.

## Tasks

- [x] Add web tests for the scope control and date/overview search behavior.
- [x] Add a `search-scope` select with `当日` as the default and `总揽` as the overview option.
- [x] Update search params so only daily scope sends `date`.
- [x] Update search detail/status copy to show the active scope.
- [x] Run focused web UI tests.
- [x] Run full pytest suite.
- [x] Restart the local server and browser-smoke the control.
- [x] Commit Phase 12 locally.

## Verification Log

- Focused web UI red tests initially failed because the scope control and JS date-gating were missing.
- Focused web UI tests after implementation: 2 passed, 1 warning.
- Full suite: `uv run pytest -v` -> 105 passed, 1 warning.
