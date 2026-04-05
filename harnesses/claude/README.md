# Principia Claude Compatibility Note

This directory is kept as a compatibility note for older Claude-facing references. The canonical Claude Code bundle now lives in [`plugins/claude/README.md`](../../plugins/claude/README.md).

## Install

Follow the canonical Claude bundle instructions in `plugins/claude/README.md`.

For local development, point Claude Code at the canonical bundle directory:

```bash
claude --plugin-dir /path/to/principia/plugins/claude
```

## Layout

- `plugins/claude/`: canonical Claude bundle
- `principia/`: shared engine package used by every harness

The legacy root Claude plugin surface has been removed.
