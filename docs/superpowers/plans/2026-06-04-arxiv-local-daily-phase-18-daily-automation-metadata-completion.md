# arXiv Local Daily Phase 18 Daily Automation and Metadata Completion Plan

## Goal

Make daily collection automatic: the app should start/refresh daily crawl work and continue fetching metadata in the background until every daily paper is complete or waiting for a polite retry window.

## Root Cause

The previous crawl path queued one unified metadata enrichment pass. When that pass tried to fetch too many arXiv IDs at once or hit a source-side limit, the whole daily set could be marked `failed`. There was no completion loop to recover from partial metadata progress.

## Decisions

- Replace one-shot post-crawl metadata enrichment with a metadata completion loop.
- Fetch incomplete metadata in batches of 100 daily IDs by default.
- Use `metadata_status != complete` as the work queue and skip retry-window items until `metadata_next_run_at` is due.
- Mark retryable source failures such as HTTP 429/timeout as `retryable`, not permanent `failed`.
- Continue using both ID API and OAI sources when available; one source failing does not discard metadata from the other source.
- Add `POST /api/daily/automation/start` to queue crawl-if-needed and metadata completion.
- Merge the former Crawl and Daily UI panels into one `Daily Automation` panel.
- Start daily automation automatically on page load and when the date changes.

## Tasks

- [x] Add failing tests for retryable unified metadata errors.
- [x] Add failing tests for batched completion until all papers are complete.
- [x] Add API tests for crawl post-processing and daily automation start.
- [x] Add web UI tests for merged Automation panel and automatic entry point.
- [x] Implement retryable source handling in unified metadata enrichment.
- [x] Implement `complete_metadata_for_date`.
- [x] Queue metadata completion after crawl.
- [x] Add daily automation API endpoint.
- [x] Merge Crawl and Daily panels in the UI.
- [x] Browser-smoke the local app.

## Verification

- Focused metadata/API/web UI tests: 7 passed, 1 warning.
- Metadata retry regression tests: 8 passed.
- Full test suite: 112 passed, 1 warning.
- Browser smoke at 342px viewport:
  - `Daily Automation` panel present
  - old `Crawl` and `Daily` panels absent
  - no horizontal overflow
  - automation start request fired without server errors
- Live local smoke after reload showed metadata progress from the old failed set:
  - `complete`: 56
  - `retryable`: 144
  - `failed`: 1771
