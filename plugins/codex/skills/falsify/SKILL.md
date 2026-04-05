---
name: falsify
description: Mark a Principia node disproven and explain the resulting cascade in Codex.
---

# Falsify

Apply the state change with the package CLI:

```bash
uv run python -m principia.cli.manage --root principia falsify <node-id> [--by <evidence-id>]
```

Then refresh workflow state with:

```bash
uv run python -m principia.cli.codex_runner --root principia dashboard
```

In Codex, summarize the disproven node, any cascade effects, and the next action from the refreshed dashboard payload.
