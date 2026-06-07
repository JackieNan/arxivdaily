# arXiv Local Daily: Merged Daily Status Plan

## Goal

Simplify the web workbench top area so daily automation status is readable at a glance, and make the AI progress count reflect already completed paper-level summary + score outputs.

## Decisions

- Remove the top-right Settings panel entirely from the page.
- Keep one batch AI action: `Run Summary + Score`.
- Make the batch AI action run the selected date's full Computer Science scope using all `cs.*` categories.
- Keep LLM API and summary template configuration as local config-file workflows, not in-page settings.
- Merge status/progress UI into one `Daily Status` component with four rows: Papers, Metadata, AI, Backend.
- Count AI progress by paper: a paper is complete when it has any complete summary and a complete score for the active rubric, independent of model or template identity.
- Keep the selected-date/category scope visible in status numbers, so CS daily status does not display all-category paper counts.

## Implementation Steps

1. Remove Settings HTML and move `Run Summary + Score` into Daily Automation.
2. Replace the old summary grid and pipeline cards with a compact Daily Status component.
3. Remove frontend AI config fetching and model/template UI references.
4. Add backend `ai` coverage to daily status.
5. Update status rendering so top summary and AI row use `status.ai`.
6. Update tests to reject removed UI and verify the new status component.
7. Verify the app in the browser and run the full test suite.

## Verification

- Focused Web UI and daily pipeline tests passed.
- Full test suite passed: `160 passed, 1 warning`.
- Browser verified `phase43` assets, no Settings panel, no old status summary/pipeline blocks, no horizontal overflow.
- Browser verified 2026-06-05 CS status shows `Papers 1196/1196`, `Metadata 1196/1196`, and `AI 0/1196`.
