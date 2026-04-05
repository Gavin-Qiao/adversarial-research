# Principia Claude Harness

This repository still supports Claude Code through the existing Claude-facing Principia layout at the repo root.

## Install

Clone this repository and point Claude Code at the checkout that contains Principia:

```bash
/plugin marketplace add Gavin-Qiao/principia
/plugin install principia
```

For local development, use the repository root as the plugin source so Claude loads the same shared Principia engine and repo assets:

```bash
claude --plugin-dir /path/to/principia
```

## Layout

- `agents/`: Claude agent definitions
- `skills/`: Claude skill definitions
- `hooks/`: Claude hook wiring
- `principia/`: shared engine package used by every harness

The Codex harness lives separately under `harnesses/codex/` and uses the same shared engine.
