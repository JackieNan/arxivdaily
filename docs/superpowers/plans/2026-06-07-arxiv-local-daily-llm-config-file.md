# Phase 33 Plan: LLM Config File and Model UI Removal

## Goal

Move LLM provider settings out of the main workbench UI and support local file-based API configuration.

## Scope

- Remove the Settings `Model` input from the web UI.
- Stop web requests from sending model names during daily automation, batch AI triage, status refresh, and prompt preview.
- Resolve the active model on the backend from local LLM configuration.
- Add local JSON config support at `config/llm.local.json`.
- Keep environment variables as optional overrides over the config file.
- Add a committed `config/llm.example.json` without secrets.
- Ignore `config/llm.local.json` in git so API keys stay local.
- Keep `/api/ai/config` masked: report base URL, key presence, temperature, and config-file presence/path without returning the API key or model.

## Important Decisions

- The model is still required for provider calls, but it belongs in backend configuration rather than the page workflow.
- Env vars remain supported for scripts and temporary overrides.
- Config precedence is env > `config/llm.local.json` > defaults.
- The page should show whether AI is configured, not expose or repeatedly ask for model identity.

## Verification

- Add API tests for config-file loading and env override reporting.
- Add API test proving omitted request model resolves to the configured model.
- Add web UI tests proving the model input and model request wiring are absent.
- Run the full test suite.
