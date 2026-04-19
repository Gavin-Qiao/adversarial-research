---
name: principia
description: Use when orienting Principia in Codex.
---

Use `uv run python -m principia.cli.codex_runner --root principia <cmd>` for workflow state. Here `principia` is the plugin identity, `plugins/codex` is the bundle path, and `principia/` is the generated workspace.
If `principia/` is missing or the north star is unlocked, start with `principia:init`; otherwise start with `principia:status`.
Artifact ladder: `status` for live state, `next-step` for action selection, `patch-status` for drift, `results` for stakeholder synthesis, and `packet` / `prompt` / `dispatch-log` for stateful handoff tools.
Use `uv run python -m principia.cli.manage --root principia ...` only for `falsify`, `settle`, `post-verdict`, `replace-verdict`, and `reopen`.
