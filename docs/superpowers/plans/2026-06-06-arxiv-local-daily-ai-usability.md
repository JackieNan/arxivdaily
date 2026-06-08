# arXiv Local Daily AI Usability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI summary and score workflow inspectable before batch runs by exposing API configuration, prompt preview, and selected-paper AI triage.

**Architecture:** Reuse the existing OpenAI-compatible LLM client and combined AI triage prompt. Add small API endpoints for configuration and prompt preview, plus a service/API path for one selected paper. The web UI keeps batch triage in Settings and adds selected-paper AI controls in the detail panel.

**Tech Stack:** FastAPI, SQLite repositories, existing LLM summary helpers, vanilla HTML/CSS/JS, pytest.

---

### Task 1: Backend AI Introspection Tests

**Files:**
- Modify: `arxiv-local-daily/tests/test_api.py`
- Modify: `arxiv-local-daily/tests/test_ai_triage.py`

- [x] **Step 1: Write failing service test**

Add a test that seeds one metadata-complete paper and one template, calls `generate_ai_triage_for_paper`, and asserts exactly one LLM call, one complete summary, and one complete score.

- [x] **Step 2: Write failing API tests**

Add tests for:
- `GET /api/ai/config` masks secrets and reports env variable names.
- `POST /api/ai/prompt-preview` returns the exact chat messages for a selected paper and template.
- `POST /api/papers/{arxiv_id}/ai-triage/run` delegates to an injectable single-paper runner.

- [x] **Step 3: Run focused tests and verify red**

Run:

```bash
uv run pytest tests/test_ai_triage.py::test_generate_ai_triage_for_paper_persists_summary_and_score tests/test_api.py::test_get_ai_config_reports_masked_environment tests/test_api.py::test_post_ai_prompt_preview_returns_messages tests/test_api.py::test_post_paper_ai_triage_run_uses_injected_runner -q
```

Expected: failures for missing function/endpoints.

### Task 2: Backend Implementation

**Files:**
- Modify: `arxiv-local-daily/src/arxiv_local_daily/services.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/api.py`

- [x] **Step 1: Implement `generate_ai_triage_for_paper`**

Use the same template lookup, prompt builder, parser, summary upsert, and score upsert as `generate_ai_triage_for_date`. Return `not_configured`, `not_found`, `not_eligible`, `skipped`, `complete`, or `failed` with counts and IDs.

- [x] **Step 2: Add config and prompt preview endpoints**

Return masked LLM config without exposing the API key. Prompt preview returns model, paper summary, template info, enabled summary keys, score keys, and messages.

- [x] **Step 3: Add selected-paper AI endpoint**

Wire `/api/papers/{arxiv_id}/ai-triage/run` through an injectable `paper_ai_triage_runner`.

- [x] **Step 4: Run focused tests and verify green**

Run the same focused test command. Expected: all listed tests pass.

### Task 3: Web UI Tests And Implementation

**Files:**
- Modify: `arxiv-local-daily/tests/test_web_ui.py`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/index.html`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/app.js`
- Modify: `arxiv-local-daily/src/arxiv_local_daily/web/styles.css`

- [x] **Step 1: Write failing static web tests**

Assert the page contains `ai-config-status`, `paper-ai-run`, `paper-prompt-preview`, and `prompt-preview-dialog`. Assert JS calls `/api/ai/config`, `/api/ai/prompt-preview`, and `/api/papers/`.

- [x] **Step 2: Implement UI controls**

Settings shows API configured/not configured and base URL. Paper detail shows `Run AI` and `Preview Prompt` when a paper is selected. Prompt preview opens a modal with system/user messages.

- [x] **Step 3: Render summaries readably**

Replace raw JSON summary display with field rows that render arrays as compact lists and scalar fields as paragraphs.

- [x] **Step 4: Run web UI tests**

Run:

```bash
uv run pytest tests/test_web_ui.py -q
```

Expected: pass.

### Task 4: Documentation, Verification, Commit

**Files:**
- Modify: `docs/phases.md`
- Modify: `docs/superpowers/plans/2026-06-06-arxiv-local-daily-ai-usability.md`

- [x] **Step 1: Record phase outcome**

Append a new phase entry describing AI config visibility, prompt preview, selected-paper triage, and readable summary rendering.

- [x] **Step 2: Run verification**

Run focused tests, then full suite:

```bash
uv run pytest -q
```

- [x] **Step 3: Browser smoke test**

Open `http://127.0.0.1:8765/?phase=37`, verify AI config appears, select a paper, open prompt preview, and ensure there is no horizontal overflow.

- [x] **Step 4: Commit**

```bash
git add docs arxiv-local-daily
git commit -m "feat: add AI prompt preview and single paper triage"
```
