# arXiv Local Daily Phase 4 AI Summary Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for each behavior change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and persist structured AI summaries for crawled daily papers using user-editable, versioned summary templates.

**Architecture:** Keep prompt construction, model client calls, JSON parsing, persistence, and API/CLI triggers separate. Tests use injected fake LLM clients only. Runtime uses an OpenAI-compatible chat-completions endpoint configured by environment variables, so local models and hosted providers can share the same service boundary.

**Non-goals for this phase:** full web UI, full PDF text extraction, long-chain paper-reading agents, and automatic background scheduling.

---

## File Structure

- Create `arxiv-local-daily/src/arxiv_local_daily/summary.py`: prompt builder, response parser, LLM client protocol, OpenAI-compatible client.
- Modify `arxiv-local-daily/src/arxiv_local_daily/models.py`: add structured summary request/result models.
- Modify `arxiv-local-daily/src/arxiv_local_daily/repositories.py`: add template lookup, summary candidate query, and summary upsert/list methods.
- Modify `arxiv-local-daily/src/arxiv_local_daily/services.py`: add summary generation service.
- Modify `arxiv-local-daily/src/arxiv_local_daily/api.py`: add template creation, summary trigger, and paper summary listing endpoints.
- Modify `arxiv-local-daily/src/arxiv_local_daily/cli.py`: add `summarize` and template JSON import commands.
- Modify `arxiv-local-daily/README.md`: document summary template customization and summary generation.
- Modify `docs/phases.md`: record Phase 4 status and verification.
- Create `arxiv-local-daily/tests/test_summary_prompt.py`: prompt construction and JSON parsing tests.
- Create `arxiv-local-daily/tests/test_summary_generation.py`: repository/service tests with fake LLM client.
- Modify `arxiv-local-daily/tests/test_api.py`: template creation and summary trigger/listing tests.
- Modify `arxiv-local-daily/tests/test_cli.py`: CLI parsing tests.

---

## Tasks

### Task 1: Prompt Builder and Response Parser

- [ ] Write tests for prompt construction from a paper row and a custom template.
- [ ] Write tests for parsing strict JSON and fenced JSON model responses.
- [ ] Implement `build_summary_messages` and `parse_summary_response`.

### Task 2: Template and Summary Repositories

- [ ] Write tests for loading latest/default templates.
- [ ] Write tests for selecting daily papers that have complete metadata and do not already have a summary for the requested template/model unless `force=True`.
- [ ] Write tests for upserting summary content with template version and status.
- [ ] Implement repository methods.

### Task 3: Summary Generation Service

- [ ] Write tests with a fake LLM client returning structured JSON.
- [ ] Write tests for failed model calls storing failed summary rows without losing the paper.
- [ ] Implement `generate_summaries_for_date`.

### Task 4: CLI/API Controls

- [ ] Write tests for `POST /api/summary-templates`, `POST /api/summaries/run`, and `GET /api/papers/{arxiv_id}/summaries`.
- [ ] Write CLI parsing tests for `summarize` and template JSON import.
- [ ] Implement controls and documentation.

### Task 5: Verification

- [ ] Run focused tests for summary behavior.
- [ ] Run full `uv run pytest -v`.
- [ ] Record Phase 4 in `docs/phases.md`.
- [ ] Commit Phase 4 locally.
