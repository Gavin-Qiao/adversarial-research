---
name: next-step
description: Use when asking what to do next in Principia.
---

Use `uv run python -m principia.cli.codex_runner --root principia <cmd>`. Here `principia` is the plugin identity, `plugins/codex` is the bundle path, and `principia/` is the generated workflow workspace.
Start with `dashboard` and `patch-status`.
If init is incomplete, stay in `principia:init`.
Treat the dashboard recommendation as the default answer when asking what to do next.
Surface pending human review, stale handoffs, waiting external work, and north-star drift before generic progression.
Use `next --path [claim-path]`, `packet --path [claim-path]`, `prompt --path [claim-path]`, and `dispatch-log --cycle [claim-slug]` as needed.
Report the next action as `principia:init`, a runner command, or a human decision.
