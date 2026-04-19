---
name: results
description: Use when summarizing Principia results.
---

Here `principia` is the plugin identity, `plugins/codex` is the bundle path, and `principia/` is the generated workflow workspace.
`uv run python -m principia.cli.codex_runner --root principia results`
Confirm `exists`, `results_path`, `message`, and `results_summary`. Summarize the `topline`, `open_claim_count`, `verdict_counts`, `confidence_counts`, `latest_verdict`, and `limitation_preview` before only pointing to `RESULTS.md`. Read `RESULTS.md` only on request.
