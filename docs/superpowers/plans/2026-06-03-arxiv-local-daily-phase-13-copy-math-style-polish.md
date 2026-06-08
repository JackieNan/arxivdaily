# arXiv Local Daily Phase 13 Copy and Math Style Polish

**Goal:** Fix the search scope label typo and make fallback LaTeX rendering visually quieter.

## Decisions Log

- 2026-06-03: The repository-wide search scope label should be `总览`.
- 2026-06-03: The local LaTeX fallback should look like subdued inline math, not decorative calligraphy.
- 2026-06-03: MathJax remains the preferred renderer when available; this phase only tones down the fallback CSS.

## Tasks

- [x] Update web tests to require `总览`.
- [x] Replace the incorrect UI/docs copy with `总览`.
- [x] Remove decorative script fonts from `.math-script`.
- [x] Replace the floating hat pseudo-element with a simple overline.
- [x] Run focused web UI tests.
- [x] Run full pytest suite.
- [x] Restart the local server and browser-smoke the corrected label.
- [x] Commit Phase 13 locally.

## Verification Log

- Focused web UI red tests initially failed because UI/JS still used the incorrect overview label and fallback CSS still contained decorative script styles.
- Focused web UI tests after implementation: 2 passed, 1 warning.
- Full suite: `uv run pytest -v` -> 105 passed, 1 warning.
