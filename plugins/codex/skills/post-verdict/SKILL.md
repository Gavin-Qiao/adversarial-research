---
name: post-verdict
description: Run Principia post-verdict bookkeeping from Codex and refresh the workflow view.
---

# Post Verdict

Run the bookkeeping command:

```bash
uv run python -m principia.cli.manage --root design post-verdict <claim-path>
```

Then refresh state with:

```bash
uv run python harnesses/codex/scripts/engine_runner.py --root design dashboard
```

In Codex, explain the bookkeeping outcome in workflow terms: verdict recorded, cascades applied if needed, and the next action from the dashboard JSON.
