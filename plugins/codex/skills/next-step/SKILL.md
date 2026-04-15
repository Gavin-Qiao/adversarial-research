---
name: next-step
description: Determine and execute the next Principia workflow action from Codex.
---

# Next Step

Check the current workflow state first:

```bash
uv run python -m principia.cli.codex_runner --root principia dashboard
uv run python -m principia.cli.codex_runner --root principia patch-status
```

If the dashboard reports an init state of `missing_workspace` or `discussion_in_progress`, do not dump raw workflow jargon on the user. Continue the initialization flow:

- if missing, tell the user to invoke the `principia:init` skill or ask Codex to initialize Principia for the repo
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

If `patch-status` reports stale or unversioned claims, surface that before pushing deeper into the workflow. The user may want to patch the north star or restamp claims before continuing.

When the next action is an external dispatch, materialize the canonical packet first:

```bash
uv run python -m principia.cli.codex_runner --root principia next --path [claim-path]
uv run python -m principia.cli.codex_runner --root principia packet --path [claim-path]
uv run python -m principia.cli.codex_runner --root principia prompt --path [claim-path]
```

If the user asks whether previous external work has landed, inspect the lifecycle log:

```bash
uv run python -m principia.cli.codex_runner --root principia dispatch-log --cycle [claim-slug]
```

Interpret the lifecycle conservatively:

- `packet`: Principia prepared the canonical handoff packet
- `dispatch`: the external prompt/handoff artifacts were materialized
- `received`: a result file exists in the claim workspace
- `recorded`: arbiter verdict bookkeeping has been committed

When reading `dashboard.dispatch_lifecycle`, prefer the derived status over the raw action:

- `ready_to_send`: packet exists but the handoff was not sent yet
- `waiting_result`: the handoff was sent and the workspace is still waiting on the result
- `stale`: the audit trail no longer matches the claim state and should be reviewed
