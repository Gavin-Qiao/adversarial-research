# Codex Skills

This directory contains the canonical Principia Codex skills under `plugins/codex`.

The packaged runner powers the JSON engine commands:

```bash
uv run python -m principia.cli.codex_runner --root principia <command>
```

Use it for `build`, `dashboard`, `validate`, and `results`. Some workflow actions still call `principia.cli.manage`, so the bundle is not fully runner-backed yet.
