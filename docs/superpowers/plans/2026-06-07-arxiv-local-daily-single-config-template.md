# Single Config-File Summary Template

## Goal

Remove template editing from the web app and stop treating templates as user-selectable/versioned UI state. The app should use one summary template, edited manually through a local config file.

## Design

- Remove all Settings UI for template editing, module toggles, and saving templates.
- Remove web JS calls to `/api/summary-templates`.
- Remove summary-template CRUD API routes.
- Add `config/summary_template.example.json` and ignore `config/summary_template.local.json`.
- Load the active template from `config/summary_template.local.json`; fall back to the built-in default template when the local file is absent.
- Force the internal template identity to one fixed singleton name and version `1`.
- Keep existing DB tables as internal storage to avoid a destructive schema/data migration.
- For completion checks, ignore template name/version and count any complete summary with the current model and input scope.
- Show the template config path in AI config status so the user knows where to edit it manually.

## Verification

- Web UI tests assert template editing controls and JS are absent.
- API tests assert template CRUD routes are removed.
- Prompt-preview test asserts a local template config file is used without creating/selecting a database template from the UI.
- Full test suite must pass.
- Browser smoke should confirm `phase41`, no template editing UI, no horizontal overflow, and config path visible.
