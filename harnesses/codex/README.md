# Principia Codex Harness

Install Principia in Codex from the repo-local `harnesses/codex` surface inside a full Principia checkout.

This harness is Codex-native. It uses Codex skills and a Codex plugin manifest while calling the shared Principia engine in this repository.

This is a repo-local harness, not a standalone plugin distribution. It depends on shared repo content, including `principia/`, `agents/`, and `config/`. Copying `harnesses/codex` by itself is unsupported.

The repo-local marketplace entry in `.agents/plugins/marketplace.json` points at `harnesses/codex`, so harness selection stays tied to the checkout instead of a global install. That entry is convenience for this checkout, not a standalone package source.

## Layout

- `.codex-plugin/plugin.json`: Codex plugin manifest
- `scripts/engine_runner.py`: thin adapter over the shared engine API
- `skills/`: harness-specific Codex workflow skills
