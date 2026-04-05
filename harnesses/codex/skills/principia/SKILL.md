---
name: principia
description: Run the Principia workflow inside Codex using the shared Principia engine.
---

# Principia

Use the shared engine through `harnesses/codex/scripts/engine_runner.py`. Prefer runner-backed JSON commands over scraping generated markdown files when you need workflow state.

Canonical flow:

1. Initialize the workspace if `design/` does not exist.
2. Inspect workflow state with `uv run python harnesses/codex/scripts/engine_runner.py --root design dashboard`.
3. Advance the next step, or apply `falsify`, `settle`, `post-verdict`, `replace-verdict`, or `reopen` when the evidence warrants it.
4. Regenerate `RESULTS.md` and run validation before calling the investigation complete.

Use `uv run python -m principia.cli.manage --root design ...` for state-changing commands the engine does not expose yet.
