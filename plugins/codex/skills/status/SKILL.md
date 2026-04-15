---
name: status
description: Inspect the current Principia workflow state in Codex through the packaged runner without scraping generated reports.
---

# Status

Use the runner-backed dashboard view:

```bash
uv run python -m principia.cli.codex_runner --root principia dashboard
```

Present the Codex-native summary from the JSON payload:

- `warnings` first, if present
- `init.status`, `init.north_star_locked`, and `preferences`
- `breadcrumb`, `phase`, and `action`
- `active_claim` and `active_cycle`
- `dispatch_lifecycle.latest` and `dispatch_lifecycle.outstanding` when external handoff state matters
- `dispatch_overview.stale_claims` when you need workspace-wide dispatch health
- `dispatch_overview.ready_to_send_claims` and `dispatch_overview.waiting_result_claims` when you need workspace-wide send/wait visibility
- `claims`
- `blocked`
- `pending_decisions`
- `last_verdict`
- `autonomy`

If `warnings` contains `north_star_drift`, say that explicitly before the normal workflow summary and point to the affected claims from `patch_status.needs_review`.

If `warnings` contains `dispatch_handoff_stale`, call out the affected claim set explicitly from `dispatch_overview.stale_claims`. This means the dispatch audit log no longer matches the current claim/filesystem state.

Interpret `dispatch_lifecycle` statuses literally:

- `ready_to_send`: packet exists and the handoff still needs to be sent
- `waiting_result`: the handoff was sent and Principia is waiting on the result
- `stale`: the audit trail disagrees with the current claim state and needs review

If the user is asking about external handoff progress rather than overall workflow state, inspect `dispatch-log` instead of inferring from directory presence alone.

Only read `PROGRESS.md` or `FOUNDATIONS.md` if the user explicitly asks for the rendered reports.
