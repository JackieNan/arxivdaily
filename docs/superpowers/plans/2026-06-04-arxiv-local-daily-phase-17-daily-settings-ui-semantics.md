# arXiv Local Daily Phase 17 Daily and Settings UI Semantics Plan

## Goal

Remove confusing Daily and Settings controls, clarify crawl category counts versus daily paper counts, and make summary templates editable without exposing raw JSON status panes.

## Root Cause

The daily crawl had successfully covered 155 arXiv categories and persisted 1971 unique daily papers, but the UI put the 155 category count in a prominent "complete" slot. That made it look like crawl only fetched 155 papers. Daily status also rendered raw API JSON in a small panel, so `partial`/metadata failures were visible but not actionable.

## Decisions

- Treat 155 as a category-completeness count, not a paper count.
- Show daily paper count from `metadata.total`.
- Collapse Daily into one user-facing action: `Run Daily Update`.
- Keep status refresh automatic after crawl, summary, and score operations.
- Remove raw Daily and Settings detail panes from the main UI.
- Replace `Create Default Template` with an expandable template editor.
- Let users edit template module labels/prompts and enabled state, then save a new template version.
- Combine manual summary and scoring into one `Run Summary + Score` action.

## Tasks

- [x] Add failing web UI tests for simplified Daily controls, missing raw detail panes, template editor affordance, combined summary/score action, and explicit paper/category status semantics.
- [x] Replace Daily Status and Daily Pipeline buttons with one Daily Update button.
- [x] Render Daily metrics as status, papers, categories, metadata, summary, and score.
- [x] Replace raw Daily JSON with a concise blocker/status note.
- [x] Replace Settings detail pane with a hidden second-level template editor.
- [x] Combine summary and score execution into one UI action.
- [x] Browser-smoke the updated local UI.

## Verification

- Focused web UI red tests initially failed because the old Daily buttons, raw detail panes, and create-template action were still present.
- Focused web UI tests after implementation: 2 passed, 1 warning.
- Full test suite after implementation: 109 passed, 1 warning.
- Browser smoke at 599px viewport:
  - no horizontal overflow
  - Daily has one button: `Run Daily Update`
  - Daily note shows `Papers 1971; categories 155/155; metadata 0/1971 complete; failed 1971`
  - Daily and Settings raw detail panes are absent
  - Template editor opens with 5 editable module rows and internal scrolling
