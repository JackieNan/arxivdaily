# arXiv Local Daily: Search Filter Cleanup Plan

## Goal

Make category filtering behave like arXiv category filtering instead of substring matching, and simplify the search panel by removing low-value filters.

## Root Cause

The search category filter used `%<category>%` against `categories_json`. Searching for `cs` therefore matched `physics.atom-ph`, because the word `physics` contains the substring `cs`. The affected paper, `1505.07152`, appeared on 2026-06-05 because it was a replacement event, and it floated high in score sorting because it had a completed AI score.

## Decisions

- Treat category input without a dot, such as `cs`, as an arXiv category group prefix: `cs.*`.
- Treat category input with a dot, such as `cs.AI`, as an exact category.
- Stop broad query search from substring-matching `categories_json`; category search belongs in the Category field.
- Remove `Event`, `Metadata`, and `Summary` dropdowns from the web search panel.
- Preserve backend API support for those filters for CLI/API compatibility.

## Verification

- Added a regression test showing `category=cs` does not match `physics.atom-ph`.
- Focused search/Web UI tests passed.
- Full test suite passed: `161 passed, 1 warning`.
- Browser verified `phase44` assets, removed filter controls, and `2026-06-05 + category=cs` no longer shows the Rydberg physics paper on the first page.
