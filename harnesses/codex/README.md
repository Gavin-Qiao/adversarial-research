# Principia Codex Harness

Install Principia in Codex from `harnesses/codex/`.

This harness is Codex-native. It uses Codex skills and a Codex plugin manifest while calling the shared Principia engine in this repository.

The repo-local marketplace entry in `.agents/plugins/marketplace.json` points at `harnesses/codex`, so harness selection stays tied to the checkout instead of a global install.

## Layout

- `.codex-plugin/plugin.json`: Codex plugin manifest
- `scripts/engine_runner.py`: thin adapter over the shared engine API
- `skills/`: harness-specific Codex workflow skills
