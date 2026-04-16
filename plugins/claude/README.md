# Principia — Claude Code Plugin

Canonical Claude Code plugin bundle for [Principia](https://github.com/Gavin-Qiao/principia): turn a philosophical principle into a working algorithm through rigorous adversarial testing.

## Install (local marketplace)

Install the plugin from a local clone of the principia repo. This is the supported path in plugin version 0.5.0.

```bash
# Clone the repo (requires the Python core to be installable locally)
git clone https://github.com/Gavin-Qiao/principia
cd principia
uv sync --dev  # or pip install -e .

# In a Claude Code session, add the marketplace and install the plugin:
/plugin marketplace add /absolute/path/to/principia
/plugin install principia@principia
/reload-plugins
```

The plugin is now available. Try `/principia:help` to get oriented, or `/principia:init` to start a new project.

> **Note**: GitHub-shorthand install (`/plugin marketplace add Gavin-Qiao/principia`) will become supported once the `principia` core Python package is published to PyPI — tracked in a future iteration.

## What's in this bundle

- **11 slash commands** — `init`, `design`, `step`, `status`, `validate`, `query`, `new`, `scaffold`, `settle`, `falsify`, `impact`.
- **2 skills** — `help` (adaptive onboarding), `methodology` (reference).
- **8 subagents** — `architect`, `adversary`, `arbiter`, `conductor`, `synthesizer`, `scout`, `experimenter`, `deep-thinker`.
- **SessionStart hook** — auto-rebuilds the database when you resume work on a principia project.

## Architecture

This bundle is a thin adapter over the universal principia core. All plugin files call core functionality through a single wrapper at `scripts/pp`, which maps contract operation names to the current CLI. See [`docs/CONTRACT.md`](../../docs/CONTRACT.md) for the contract specification.

## Dev setup

```bash
# For a tight edit loop on the plugin itself:
claude --plugin-dir ./plugins/claude

# For testing the full install path:
# (from a Claude Code session)
/plugin marketplace add /abs/path/to/principia
/plugin install principia@principia
```
