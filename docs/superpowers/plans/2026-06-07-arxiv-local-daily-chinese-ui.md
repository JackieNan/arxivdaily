# Phase 39 Plan: Chinese Web UI

**Goal:** Make the web workbench's visible UI Chinese while preserving backend contracts, database values, and arXiv category codes.

## Scope

- Translate static HTML labels, buttons, empty states, modals, and status copy to Chinese.
- Translate dynamic JavaScript messages for daily automation, search, paper detail, AI actions, prompt preview, discussions, and category picker labels.
- Display backend status values such as `complete`, `failed`, `running`, and `retryable` as Chinese labels without changing the raw status values used by CSS, API calls, or tests.
- Keep arXiv category codes such as `cs.LG` and API parameter values such as `daily`, `overview`, `score`, and `recent` unchanged.
- Bump static web asset version to `phase46`.

## Tests

- Update Web UI tests to assert the new Chinese labels and continue checking removed legacy controls stay absent.
- Run JavaScript syntax validation, focused Web UI tests, and the full Python test suite.
- Verify the local browser page renders the Chinese UI at `/?phase=46`.
