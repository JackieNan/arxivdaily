# arXiv Local Daily Phase 11 Math Rendering and Chinese Keywords Plan

**Goal:** Render LaTeX math in paper titles/abstracts and make the paper list show LLM-generated Chinese keywords instead of raw abstracts.

## Decisions Log

- 2026-06-03: Use MathJax for TeX rendering in title and abstract surfaces when available, with a local lightweight renderer as fallback.
- 2026-06-03: Paper cards should not fall back to abstract snippets; they show `summary_keywords` from the latest complete summary or a short missing-keywords hint.
- 2026-06-03: The default summary template adds a `keywords` field and uses Chinese labels/prompts.
- 2026-06-03: Summary prompt construction now explicitly requires all user-facing JSON values to be in the template language, defaulting to Chinese.

## Tasks

- [x] Add tests for latest-summary keywords in search results.
- [x] Add tests for Chinese output requirements in summary prompts.
- [x] Add tests for MathJax/static UI wiring and removal of abstract fallback in paper cards.
- [x] Add `summary_keywords` to search results by parsing the latest complete summary JSON.
- [x] Update default summary template with Chinese `keywords`, `tldr`, `method`, `value`, and `limits` fields.
- [x] Add MathJax config and dynamic typesetting after search/detail rendering.
- [x] Add local fallback renderer for common inline LaTeX when MathJax CDN loading is unavailable.
- [x] Update paper cards to display Chinese keyword chips instead of abstracts.
- [x] Run full pytest suite.
- [x] Restart local server and browser-smoke the updated UI.
- [x] Commit Phase 11 locally.

## Verification Log

- Focused red tests initially failed for missing `summary_keywords`, missing Chinese prompt instruction, missing MathJax wiring, and abstract fallback in cards.
- Focused tests after implementation: `tests/test_search_discussion.py::test_search_papers_matches_metadata_and_summary_content`, `tests/test_summary_prompt.py::test_build_summary_messages_uses_enabled_template_fields_and_paper_metadata`, and `tests/test_web_ui.py` passed.
- Full suite: `uv run pytest -v` -> 105 passed, 1 warning.
- Browser smoke after server restart: default list no longer shows abstract snippets; cards show the missing-keywords hint when summaries have not generated keywords; no horizontal overflow.
- Browser interaction note: direct search-box interaction was blocked by the browser plugin clipboard/click layer, so the formula paper lookup was verified through the local API (`2104.14092`, title contains `$p$`).
