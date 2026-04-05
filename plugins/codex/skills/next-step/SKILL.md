---
name: next-step
description: Determine and execute the next Principia workflow action from Codex.
---

# Next Step

Check the current workflow state first:

```bash
uv run python -m principia.cli.codex_runner --root design dashboard
```

Then advance with the package CLI:

```bash
uv run python -m principia.cli.manage --root design investigate-next
uv run python -m principia.cli.manage --root design next [claim-path]
```

In Codex, use the dashboard JSON to explain where the investigation is, what action is next, and whether the next step is automatic, needs a claim path, or needs a human decision.
