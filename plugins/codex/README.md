# Principia Codex Bundle

Canonical repo-local `plugins/codex` bundle for Principia.

Install Principia in Codex from the canonical `plugins/codex` surface inside a full Principia checkout.

This bundle is Codex-native. It uses the packaged runner to talk to the shared Principia engine:

```bash
uv run python -m principia.cli.codex_runner --root design dashboard
uv run python -m principia.cli.codex_runner --root design validate
uv run python -m principia.cli.codex_runner --root design results
```

The bundle depends on shared repo content, including `principia/`, `agents/`, and `config/`. Copying `plugins/codex` by itself is unsupported.

The repo-local marketplace entry in `.agents/plugins/marketplace.json` points at `./plugins/codex`, so Codex discovers this bundle from the checkout rather than from a separate package install.

## Layout

- `.codex-plugin/plugin.json`: Codex plugin manifest
- `skills/`: canonical Codex workflow skills
