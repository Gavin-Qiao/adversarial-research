---
name: init
description: Use when starting Principia or locking the north star.
---

Use `principia:init` when the workflow workspace at `principia/` is missing or the north star is unlocked. Here `principia` is the plugin identity, `plugins/codex` is the bundle path, and `principia/` is the generated workspace.
Inspect repo shape, tooling, and docs such as `README.md` and `AGENTS.md`.
Create missing workspace folders and files under `principia/`, including `claims/`, `context/assumptions/`, `.db/`, `.config.md`, and `.context.md`, then write a repo-grounded summary to `principia/.context.md`.
Explain delegation once: autonomy is checkpoints vs `yolo`, dispatch is which core roles may hand off externally, and sidecars set deep-thinker, researcher, and coder to `ask`, `auto`, or `off`. Init never goes `yolo`; sidecars still need approval.
Treat the repo scan and north-star interview as mandatory. Do not leave init after creating files alone.
Lock `principia/.north-star.md` only after explicit confirmation of problem, success, intuition, constraints, non-goals, and falsifiers. Save `checkpoints`/`yolo` and `ask`/`auto`/`off` in `.config.md`.
After lock, draft 3-5 claim directions; scaffold only if asked.
Use `uv run python -m principia.cli.codex_runner --root principia <cmd>` for `build` and `dashboard`.
If claim files drift from the locked north star, send the user to `patch-status`. End with the init state and the next Codex command.
