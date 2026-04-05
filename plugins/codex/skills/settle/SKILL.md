---
name: settle
description: Mark a Principia node proven and refresh workflow state inside Codex.
---

# Settle

Apply the proof decision:

```bash
uv run python -m principia.cli.manage --root principia settle <node-id>
```

Then inspect the updated state:

```bash
uv run python -m principia.cli.codex_runner --root principia dashboard
```

In Codex, report the proof result, any updated last verdict information, and what the dashboard says should happen next.
