# arXiv Local Daily Phase 19 LLM API Triage Automation Plan

## Goal

Connect the daily app to an OpenAI-compatible LLM API so metadata-complete daily papers can automatically receive Chinese configurable summaries, Chinese keyword chips, and reading-priority scores.

## Problem

The app already had separate summary and score workers, but the daily automation path stopped at metadata completion. Manual `Run Summary + Score` also made two LLM calls per paper: one for summary and one for scoring. That is slower, more expensive, and creates more failure surface than necessary.

## Decisions

- Add one combined AI triage prompt per paper that returns top-level `summary` and `score` JSON.
- Keep the existing `summaries` and `paper_scores` tables rather than adding a second AI result store.
- Preserve the user-editable summary template: enabled template fields define the `summary` keys.
- Require user-facing summary values, keywords, and score rationale to be in the template language, defaulting to Chinese.
- Keep score dimensions from the existing reading-priority rubric: relevance, novelty, technical depth, evidence, and actionability.
- Add an API configuration guard:
  - default OpenAI base URL requires `ARXIV_DAILY_LLM_API_KEY`
  - custom `ARXIV_DAILY_LLM_BASE_URL` can run without an API key for local/proxy servers
  - if no usable config is present, AI triage returns `not_configured` and does not write failed rows
- Connect daily automation as crawl-if-needed -> metadata completion -> AI triage completion.
- Change the Settings `Run Summary + Score` action to call the combined AI triage endpoint instead of separate summary and score endpoints.

## Tasks

- [x] Add failing tests for combined AI triage prompt and response parsing.
- [x] Add failing tests for persisting summary and score from one LLM call.
- [x] Add completion-loop tests for batched AI triage until all eligible papers are done.
- [x] Add a no-LLM-config regression test to prevent all-paper failed-row pollution.
- [x] Add API tests for daily automation invoking AI after metadata completion.
- [x] Add API tests for manual combined AI triage.
- [x] Add web UI tests for the combined AI endpoint and daily automation model/template payload.
- [x] Implement combined prompt/parser helpers.
- [x] Implement `generate_ai_triage_for_date`.
- [x] Implement `complete_ai_triage_for_date`.
- [x] Wire AI triage into daily automation.
- [x] Wire Settings `Run Summary + Score` to `/api/ai-triage/run`.
- [x] Update README and phase log.

## Verification

- Focused AI triage, API, and web UI tests passed.
- `uv run pytest -v`: 118 passed, 1 warning.
