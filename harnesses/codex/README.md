# Principia Codex Harness

This directory contains the native Codex harness for Principia.

Use this harness when selecting a plugin from this repository inside Codex. The repo-local marketplace entry in `.agents/plugins/marketplace.json` points at `harnesses/codex`, so harness selection stays tied to the checkout.

## Layout

- `.codex-plugin/plugin.json`: Codex plugin manifest
- `skills/`: reserved for harness-specific Codex skills
