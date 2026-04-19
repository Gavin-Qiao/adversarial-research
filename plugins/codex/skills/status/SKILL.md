---
name: status
description: Use when checking live Principia state.
---

Here `principia` is the plugin identity, `plugins/codex` is the bundle path, and `principia/` is the generated workflow workspace.
`uv run python -m principia.cli.codex_runner --root principia dashboard`
Summarize warnings first. Then explain in prose what Principia says to do next, how autonomy and delegation are configured, which claim is active, whether a human decision is pending, and whether a verdict was already recorded.
If init is incomplete, say whether the repo scan, the north-star interview, or both are still missing before anything else.
Mention handoff lifecycle only when it changes the next action.
If drift warnings appear, tell the user to inspect `patch-status`; if a handoff is stale, call out the claim and `dispatch-log --cycle [claim-slug]`.
Read `PROGRESS.md` or `FOUNDATIONS.md` only on request.
