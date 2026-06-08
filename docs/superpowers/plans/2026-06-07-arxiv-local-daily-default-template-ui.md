# Default Template UI and Single-Paper AI Status

## Goal

Remove `template_name` as a visible web-workbench setting and make AI status coverage rely on the backend default template. A selected-paper AI run should immediately count in the daily summary/score status shown in the top automation panel.

## Design

- Keep summary template editing in Settings, but only for the module labels/prompts.
- Store the template name internally as the backend default `daily_research`; do not expose an input for it.
- Do not send `template_name` from web daily automation, daily status, batch AI, selected-paper AI, or prompt-preview requests.
- Keep backend API compatibility for `template_name` so CLI/tests/external clients can still select templates explicitly.
- Remove visible template-name tags from paper summary detail and prompt preview headers.
- For daily status display, count completed summaries from any historical version of the same template name. This keeps the progress panel stable after template edits.
- Keep AI generation strict to the current template version so batch runs can still regenerate missing current-version summaries when needed.
- Keep daily status scoped by the selected date and category scope. A completed non-CS paper should not increment the CS-only `1/N` progress count.

## Verification

- Add web UI tests proving the `Template name` field is gone and the static JS no longer sends `template_name`.
- Add an AI regression test proving `generate_ai_triage_for_paper` is reflected in `get_daily_pipeline_status` without passing a template name.
- Extend the regression test so status still counts the single-paper summary after a newer default template version is created.
- Run focused tests first, then the full test suite.
- Smoke-test the browser at `?phase=40` for missing template-name UI and no horizontal overflow.
