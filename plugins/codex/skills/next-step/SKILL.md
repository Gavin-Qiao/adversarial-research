---
name: next-step
description: Determine and execute the next Principia workflow action from Codex.
---

# Next Step

Check the current workflow state first:

```bash
uv run python -m principia.cli.codex_runner --root principia dashboard
```

If the dashboard reports an init state of `missing_workspace` or `discussion_in_progress`, do not dump raw workflow jargon on the user. Continue the initialization flow:

- if missing, tell the user to run `/principia:init`
- if discussion is in progress, continue the north-star discussion
- if the north star is locked but claims are not scaffolded, help the user refine and scaffold claim directions

Only advance the state machine directly once init is complete.

Then use the package CLI as needed:

```bash
uv run python -m principia.cli.manage --root principia investigate-next
uv run python -m principia.cli.manage --root principia next [claim-path]
```

In Codex, use the dashboard JSON to explain:

- whether init is still underway
- where the investigation is
- what action is next
- whether the next step is automatic, needs a claim path, or needs a human decision
