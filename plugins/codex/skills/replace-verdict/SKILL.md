---
name: replace-verdict
description: Reset a completed Principia claim so a verdict can be re-run from Codex.
---

# Replace Verdict

Reset the claim with:

```bash
uv run python -m principia.cli.manage --root design replace-verdict <claim-path>
```

Then inspect the refreshed workflow:

```bash
uv run python harnesses/codex/scripts/engine_runner.py --root design dashboard
```

In Codex, describe that the verdict was cleared, note any reopened state, and use the dashboard payload to tell the user what step is now expected.
