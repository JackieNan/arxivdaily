# Historical Pastweek Crawl Fix Plan

**Goal:** Fix the 2026-06-04 selected-date crawl that incorrectly ended as `no_papers`.

**Root Cause:** The app tried historical subject dates through month archive URLs such as `/list/cs.AI/2606` or `/list/cs/2606`, which are not valid for the observed arXiv subject listing path. arXiv's recent historical subject listings are available through `/list/{category}/pastweek`. The pastweek page also groups papers by date-only headings, so the parser skipped entries because it expected a `New submissions` heading before each `<dl>`. Finally, old complete-zero crawl runs blocked future recrawls, and partial crawl failures were incorrectly followed by metadata completion, producing misleading `no_papers`.

---

### Task 1: Use arXiv Pastweek for Recent Historical Dates

- [x] Add `build_pastweek_listing_url`.
- [x] Make historical listing crawl try `/list/{category}/pastweek?skip=...&show=2000` before month fallback.
- [x] Keep month fallback for future extension and diagnostics.
- [x] Cache fetched pages during a run.

### Task 2: Parse Pastweek Date-Only Sections

- [x] Add `default_event_type` to `parse_historical_listing_for_date`.
- [x] Treat date-only pastweek sections as `new` when the caller requests it.
- [x] Filter parsed entries by target subject category.

### Task 3: Stop Mislabeling Crawl Failures as No Papers

- [x] Treat historical 404 pages as failed, not complete-zero.
- [x] Reject old poisoned complete rows with archive-page 404 evidence in crawl audit.
- [x] Stop daily automation after incomplete crawl instead of running metadata and returning `no_papers`.
- [x] Add `crawl_incomplete` status display in the UI.

### Task 4: Make the Button Actually Re-Crawl

- [x] Add `force_crawl` to daily automation requests.
- [x] Send `force_crawl=true` from the `抓取指定日期` UI action.
- [x] Bump static asset version so the browser loads the fixed JS.

### Verification

- [x] Focused parser/live-crawl/audit/API/web UI tests passed: 78 passed, 1 warning.
- [x] Full test suite passed: 150 passed, 1 warning.
- [x] Browser verified 2026-06-04 now completes with Papers `1192/1192` and Metadata `1192/1192`.
