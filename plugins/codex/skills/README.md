# Codex Skills

This directory contains the canonical Principia Codex skills under `plugins/codex`.

The packaged runner powers the JSON engine commands:

```bash
uv run python -m principia.cli.codex_runner --root principia <command>
```

Use it for `build`, `dashboard`, `validate`, and `results`. Some workflow actions still call `principia.cli.manage`, so the bundle is not fully runner-backed yet.
It now also exposes `next`, `packet`, `prompt`, `dispatch-log`, and `patch-status` for Codex-native workflow control and patch awareness. Some mutation-oriented actions still call `principia.cli.manage`, so the bundle is not fully runner-backed yet.

`dispatch-log` tracks the external handoff lifecycle with structured events:

- `packet`
- `dispatch`
- `received`
- `recorded`
