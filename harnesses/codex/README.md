# Principia Codex Harness

This directory contains the Task 4 Codex harness scaffold for Principia.

Use this scaffold when selecting a plugin from this repository inside Codex. The repo-local marketplace entry in `.agents/plugins/marketplace.json` points at `harnesses/codex`, so harness selection stays tied to the checkout. Task 4 only wires the static layout; Task 5 adds the functional workflow.

## Layout

- `.codex-plugin/plugin.json`: Codex plugin manifest
- `skills/`: reserved for harness-specific Codex skills
