# arXiv Local Daily Phase 20 Date-Aware and Historical Crawl Plan

## Goal

Stop the app from storing the current arXiv `/new` page under the wrong selected date, and support earlier selected dates through a separate historical metadata collection path.

## Problem

The live crawler always fetched `/list/{category}/new` and used the selected UI date only as the database event date. When arXiv had not yet advanced its daily page, choosing today's local date could store yesterday's arXiv announcement under today. Choosing older dates had the same issue: the app would still ingest the current `/new` page.

## Decisions

- Parse the real arXiv announcement date from `/new` page headings.
- Treat a selected-date/page-date mismatch as `date_mismatch`; do not parse or store paper events from that source.
- Keep current daily crawl semantics for real `/new` pages: `new`, `cross-list`, and `replacement`.
- Add a separate historical mode backed by OAI-PMH metadata for the selected date.
- Store historical records as metadata-complete papers with `event_type="historical"`.
- Let the web UI send `crawl_mode="historical"` when the selected date is earlier than the browser's current date.
- Keep `crawl_mode="daily"` as the API default for backward compatibility and explicit current-page runs.

## Tasks

- [x] Add failing tests for parsing the page announcement date.
- [x] Add failing tests that `/new` date mismatch does not write daily events.
- [x] Add failing tests for historical OAI metadata crawl persistence.
- [x] Add failing API test for historical daily automation mode.
- [x] Add web UI tests for historical mode payload and search filter.
- [x] Implement `parse_daily_listing_date`.
- [x] Add live crawler date mismatch guard.
- [x] Implement `run_historical_metadata_crawl`.
- [x] Wire historical mode into daily automation.
- [x] Update web UI event filter and automation request payload.
- [x] Update README and phase log.

## Verification

- Focused date-aware crawl, historical crawl, API, and web UI tests: 26 passed, 1 warning.
- `uv run pytest -v`: 122 passed, 1 warning.
