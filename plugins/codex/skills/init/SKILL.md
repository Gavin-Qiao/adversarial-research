---
name: init
description: Initialize a Principia design workspace inside Codex and confirm the packaged runner can build it.
---

# Init

If `design/` is missing, create:

```text
design/
design/claims/
design/context/assumptions/
design/.db/
```

If the user supplied a principle or project title, write it to `design/.north-star.md`. Do not create extra workflow artifacts up front.

Then verify the workspace is wired:

```bash
uv run python -m principia.cli.codex_runner --root design build
uv run python -m principia.cli.codex_runner --root design dashboard
```

In Codex, report the JSON summary and point the user to `next-step` for advancing the workflow.
