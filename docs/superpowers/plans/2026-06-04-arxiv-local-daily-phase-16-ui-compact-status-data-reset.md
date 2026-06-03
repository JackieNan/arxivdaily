# arXiv Local Daily Phase 16 Compact Status and Data Reset Plan

## Goal

Fix the remaining Settings overflow, keep the top-left status area focused on key operation text, and reset the current local paper/metadata data so the next crawl starts from a clean database state.

## Decisions

- Settings uses a two-column responsive grid so template/model inputs and action buttons fit narrow in-app browser widths.
- `Create Default Template` spans the full Settings row because it has the longest label.
- The top operation log is summary-only. Detailed JSON remains in the panel-specific detail areas.
- The data reset clears papers, daily events, crawl runs, metadata enrichment/sync records, summaries, scores, discussions, and AI jobs.
- Summary templates are preserved so the app still has reusable AI summary settings after the reset.

## Tasks

- [x] Add focused web UI regression coverage for compact Settings and summary-only operation logging.
- [x] Compact the Settings grid and cap the top operation log to one line.
- [x] Reset current local paper and metadata data.
- [x] Restart the local server and browser-smoke the updated UI.
- [x] Verify database and API empty-state counts.
- [x] Record Phase 16 in the phase log.

## Verification

- Focused web UI red test initially failed because the operation log still rendered detailed JSON text.
- Focused web UI tests after implementation: 2 passed, 1 warning.
- Full test suite after implementation: 109 passed, 1 warning.
- Browser smoke at 599px viewport confirmed no document horizontal overflow, Settings grid width fits its container, and operation log height is 35px with one-line overflow clipping.
- Local database reset counts:
  - `papers`: 0
  - `daily_events`: 0
  - `metadata_enrichment_runs`: 0
  - `metadata_source_records`: 0
  - `metadata_sync_runs`: 0
  - `summaries`: 0
  - `paper_scores`: 0
  - `crawl_runs`: 0
  - `summary_templates`: 2 preserved
- Local API smoke:
  - `GET /api/daily/status/2026-06-03?model=local` returned `status=not_started`, `crawl.status=no_run`, and metadata total 0.
  - `GET /api/search/papers?date=2026-06-03&sort=score` returned `count=0`.
