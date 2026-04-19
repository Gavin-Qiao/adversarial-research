# Codex Skills

Canonical Codex skills for the `principia` plugin in `plugins/codex`.

Terminology: `principia` is the plugin identity, `plugins/codex` is the bundle path, and `principia/` is the generated workflow workspace.

Use the packaged runner: `uv run python -m principia.cli.codex_runner --root principia <command>`

User-intent map:

- `init`: create `principia/` and lock the north star.
- `status`: inspect live state, warnings, and operator guidance.
- `next-step`: choose the next action or recovery move.
- `results`: summarize stakeholder-facing synthesis and trust signals.
- `validate`: run workspace integrity checks.
- `patch-status`: inspect north-star drift.
- `packet`, `prompt`, `dispatch-log`: stateful handoff tools.
- `falsify`, `settle`, `reopen`, `replace-verdict`, `post-verdict`: state-changing bookkeeping flows.
