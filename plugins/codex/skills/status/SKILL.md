---
name: status
description: Inspect the current Principia workflow state in Codex without scraping generated reports.
---

# Status

Use the runner-backed dashboard view:

```bash
uv run python harnesses/codex/scripts/engine_runner.py --root design dashboard
```

Present the Codex-native summary from the JSON payload:

- `breadcrumb`, `phase`, and `action`
- `active_claim` and `active_cycle`
- `claims`
- `blocked`
- `pending_decisions`
- `last_verdict`
- `autonomy`

Only read `PROGRESS.md` or `FOUNDATIONS.md` if the user explicitly asks for the rendered reports.
