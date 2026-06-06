# Phase 32 Plan: CS Default Scope

## Goal

Make the local daily workflow default to Computer Science papers only, while preserving an explicit low-frequency path for crawling and AI triaging all arXiv groups.

## Scope

- Add a frontend `CS_CATEGORIES` list covering all `cs.*` arXiv categories.
- Treat an empty Categories input as CS-only by default.
- Add a bottom-of-page archive scope control that switches the empty-input default between CS-only and all arXiv groups.
- Keep manually entered Categories as the highest-priority override.
- Send the selected category scope through daily automation, daily status coverage, and batch AI triage.
- Send the selected category scope through metadata completion so old non-CS daily rows are not enriched by default.
- Filter AI triage candidates, skipped counts, summary coverage, and score coverage by category when a scope is provided.

## Important Decisions

- Backend APIs still support all-category behavior when `categories` is omitted.
- The CS-only default is a UI/product default, not a backend limitation.
- The scope toggle is intentionally placed in a low-priority bottom panel because most daily use should stay CS-focused.
- Existing non-CS papers in the local database are not deleted; the default only controls future crawl/status/AI operations unless the user switches to all groups.

## Verification

- Add focused tests for category-scoped AI candidate selection.
- Add API tests proving daily automation and `/api/ai-triage/run` pass categories to runners.
- Add web UI tests for the bottom scope panel and JS category-scope behavior.
- Run the full suite after implementation.
- Browser-check the bottom scope panel, all-groups toggle, restored CS default, and horizontal overflow.
