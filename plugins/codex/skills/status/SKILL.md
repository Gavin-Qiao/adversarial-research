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

- `init.status`, `init.north_star_locked`, and `preferences`
- `breadcrumb`, `phase`, and `action`
- `active_claim` and `active_cycle`
- `claims`
- `blocked`
- `pending_decisions`
- `last_verdict`
- `autonomy`

Only read `PROGRESS.md` or `FOUNDATIONS.md` if the user explicitly asks for the rendered reports.
