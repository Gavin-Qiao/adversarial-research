---
name: results
description: Regenerate Principia RESULTS.md through the packaged Codex runner and present the result location.
---

# Results

Generate the summary through the adapter:

```bash
uv run python -m principia.cli.codex_runner --root design results
```

Use the returned JSON to confirm whether `RESULTS.md` was generated and where it lives. Read the file only if the user asks for the rendered narrative.
