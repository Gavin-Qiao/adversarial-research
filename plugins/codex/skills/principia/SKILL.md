---
name: principia
description: Run the Principia workflow inside Codex using the shared Principia engine and packaged runner.
---

# Principia

Use the shared engine through `principia.cli.codex_runner`. Prefer runner-backed JSON commands over scraping generated markdown files when you need workflow state.

Canonical flow:

1. Initialize the repo if `principia/` does not exist, or if the north star has not been locked yet.
2. Inspect workflow state with `uv run python -m principia.cli.codex_runner --root principia dashboard`.
3. While init is incomplete, actively help the user inspect the repo, discuss the problem, and lock the north star.
4. After init, advance the next step, or apply `falsify`, `settle`, `post-verdict`, `replace-verdict`, or `reopen` when the evidence warrants it.
5. Regenerate `RESULTS.md` and run validation before calling the investigation complete.

Use `uv run python -m principia.cli.manage --root principia ...` for state-changing commands the engine does not expose yet.
