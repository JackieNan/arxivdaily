# arXiv Local Daily: Category Picker Plan

## Goal

Replace the free-text category search filter with a grouped checkbox picker so users can select whole arXiv category groups or individual subcategories.

## Decisions

- Keep default search selection on all Computer Science categories.
- Represent each arXiv group as a parent checkbox and each leaf category as a child checkbox.
- Selecting a parent group selects all of its child categories; partial child selection makes the parent indeterminate.
- Send selected leaf categories as repeated `category` query parameters.
- Keep an empty selection as "all categories".
- Extend backend search to OR multiple category filters while preserving existing single-category API compatibility.

## Verification

- Added repository/API regression tests for multiple category filters.
- Focused Web UI/search/API tests passed.
- Full test suite passed: `162 passed, 1 warning`.
- Browser verified `phase45` assets, grouped category picker, default CS selection, Clear -> all categories, CS -> CS-only, and no Rydberg physics paper in CS results.
