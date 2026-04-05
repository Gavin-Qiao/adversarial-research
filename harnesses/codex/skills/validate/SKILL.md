---
name: validate
description: Run Principia integrity checks through the Codex adapter and report structured failures.
---

# Validate

Run validation through the adapter:

```bash
uv run python harnesses/codex/scripts/engine_runner.py --root design validate
```

The runner prints the same JSON shape as `manage.py validate --json`. In Codex, summarize `valid`, `error_count`, and any listed `errors` without reformatting the report into prose unless the user asks.
