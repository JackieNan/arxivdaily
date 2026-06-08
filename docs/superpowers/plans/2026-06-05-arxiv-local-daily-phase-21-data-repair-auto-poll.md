# arXiv Local Daily Phase 21 Data Repair and Auto Poll Plan

## Goal

Repair local daily listing data written before the date-aware crawler existed, and make the open workbench keep trying daily automation without manual clicks.

## Problem

Before Phase 20, the app could store the current arXiv `/new` page under any selected UI date. This created overlapping `new`, `cross-list`, and `replacement` daily events for 2026-06-03, 2026-06-04, and 2026-06-05 in the local SQLite database. Phase 20 prevents future wrong-date writes, but it does not clean already stored rows.

## Decisions

- Treat `new`, `cross-list`, and `replacement` as daily listing events that can be repaired when they were written under contaminated dates.
- Preserve `historical` events because they come from OAI-PMH metadata collection and are not pretending to be exact daily listing entries.
- Preserve `papers`, metadata, summaries, scores, and discussions because they are reusable local knowledge even when the date event rows were wrong.
- Delete old daily crawl runs in `single-source`, `all-categories`, and `retry-incomplete` modes for repaired dates so crawl audit does not consider contaminated runs valid.
- Keep `historical-oai` crawl runs for repaired dates.
- Add a repair API endpoint for explicit, auditable local data repair.
- Add browser-side periodic silent daily automation while the app is open. Date mismatch protection still decides whether the current arXiv `/new` page is safe to write.

## Tasks

- [x] Add failing service test for deleting contaminated daily listing events while preserving historical records.
- [x] Add failing API test for a repair endpoint with injectable runner.
- [x] Add failing web UI test for periodic silent automation.
- [x] Implement `repair_contaminated_daily_listing_dates`.
- [x] Expose `POST /api/repair/daily-listings`.
- [x] Add 10-minute silent automation polling in the web UI.
- [x] Update README and phase log.

## Historical Listing Note

OAI-PMH is a metadata source. It can provide records for a date range, but it is not an exact reconstruction of an arXiv daily listing with `new`, `cross-list`, and `replacement` sections. Exact historical daily listing coverage should be a later phase that parses arXiv's historical listing/archive pages per category and date, then uses OAI/API metadata only for enrichment and cross-checking.

## Verification

- Focused data repair/API/web UI tests: 3 passed, 1 warning.
