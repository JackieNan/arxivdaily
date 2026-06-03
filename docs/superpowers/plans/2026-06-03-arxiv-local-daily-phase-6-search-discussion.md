# arXiv Local Daily Phase 6 Search and Discussion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for each behavior change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local paper search, filtered query, paper detail, and per-paper discussion records.

**Architecture:** Keep search as a repository/service layer over existing paper, daily event, and summary tables. Search should work without external services and should cover title, abstract, authors, categories, arXiv ID, and summary JSON. Discussion records are local SQLite rows attached to `arxiv_id`; they support human and AI messages without requiring a live model.

**Tech Stack:** Python 3.12+, stdlib `sqlite3`, Pydantic, pytest, FastAPI.

---

## File Structure

- Modify `arxiv-local-daily/src/arxiv_local_daily/db.py`: add `paper_discussions` table.
- Modify `arxiv-local-daily/src/arxiv_local_daily/models.py`: add `PaperDiscussionInput`.
- Modify `arxiv-local-daily/src/arxiv_local_daily/repositories.py`: add `SearchRepository`, paper detail query, and `DiscussionRepository`.
- Modify `arxiv-local-daily/src/arxiv_local_daily/services.py`: add search/detail/discussion service wrappers if useful.
- Modify `arxiv-local-daily/src/arxiv_local_daily/api.py`: add search, paper detail, and discussion endpoints.
- Modify `arxiv-local-daily/src/arxiv_local_daily/cli.py`: add `search`, `discuss add`, and `discuss list`.
- Modify `arxiv-local-daily/README.md`: document search and discussion usage.
- Modify `docs/phases.md`: record Phase 6 status and verification.
- Create `arxiv-local-daily/tests/test_search_discussion.py`: repository/service tests.
- Modify `arxiv-local-daily/tests/test_api.py`: search/detail/discussion API tests.
- Modify `arxiv-local-daily/tests/test_cli.py`: CLI parsing tests.
- Modify `arxiv-local-daily/tests/test_db.py`: schema test for discussion table.

---

## Tasks

### Task 1: Discussion Schema and Repository

- [x] Write a schema test for `paper_discussions`.
- [x] Write repository tests for adding and listing discussion messages by paper.
- [x] Implement `paper_discussions`, `PaperDiscussionInput`, and `DiscussionRepository`.

### Task 2: Paper Search and Detail

- [x] Write tests for query matching title, abstract, authors, and summary content.
- [x] Write tests for filtering by date, listing category, event type, metadata status, and summary status.
- [x] Write tests for paper detail returning metadata, daily events, summaries, and discussions.
- [x] Implement `SearchRepository.search_papers` and `SearchRepository.get_paper_detail`.

### Task 3: API Controls

- [x] Write API tests for `GET /api/search/papers`.
- [x] Write API tests for `GET /api/papers/{arxiv_id}`.
- [x] Write API tests for `POST /api/papers/{arxiv_id}/discussions` and `GET /api/papers/{arxiv_id}/discussions`.
- [x] Implement API endpoints.

### Task 4: CLI Controls

- [x] Write CLI parsing tests for `search`.
- [x] Write CLI parsing tests for `discuss add` and `discuss list`.
- [x] Implement CLI commands with JSON output.

### Task 5: Verification and Recording

- [x] Run focused search/discussion tests.
- [x] Run full `uv run pytest -v`.
- [x] Update README with search/discussion usage.
- [x] Record Phase 6 in `docs/phases.md`.
- [x] Commit Phase 6 locally.
