---
name: validate
description: Run Principia integrity checks through the packaged Codex runner and report structured failures.
---

# Validate

Run validation through the adapter:

```bash
uv run python -m principia.cli.codex_runner --root principia validate
```

The runner prints the same JSON shape as `manage.py validate --json`. In Codex, summarize `valid`, `error_count`, and any listed `errors` without reformatting the report into prose unless the user asks.
