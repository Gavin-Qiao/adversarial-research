---
name: reopen
description: Reopen a completed Principia claim and restore the workflow state in Codex.
---

# Reopen

Reopen the claim:

```bash
uv run python -m principia.cli.manage --root design reopen <node-id>
```

Then refresh with:

```bash
uv run python -m principia.cli.codex_runner --root design dashboard
```

In Codex, explain what was reopened, whether weakened dependents were restored, and what the dashboard now shows as the next action.
