# Principia Codex Bundle

Canonical Codex bundle for the `principia` plugin in a full Principia checkout.

Terminology: `principia` is the plugin identity and Python package, `plugins/codex` is the bundle path, and `principia/` is the generated workflow workspace.

## Install

```bash
codex marketplace add Gavin-Qiao/principia
```

`marketplace.json` and `.agents/plugins/marketplace.json` both expose `./plugins/codex`. Open the checkout, then install the `principia` plugin from the repo-local marketplace or the remote marketplace.

Codex exposes Principia through skills, not slash commands.

Ordered Codex flow:

1. Install the `principia` plugin from `plugins/codex`.
2. Reload Codex.
3. Run `principia:init`.
4. Use `principia:status`, `principia:next-step`, and `principia:results`.

First 10 minutes in Codex:

1. `principia:init` creates `principia/`, writes the repo scan to `principia/.context.md`, and locks the north star.
2. `principia:status` shows warnings, delegation policy, drift, and operator guidance.
3. `principia:next-step` answers "what do I do next?" with the preferred command or human review instruction.
4. `principia:results` summarizes the current report before pointing to `principia/RESULTS.md`.

Runner commands:

```bash
uv run python -m principia.cli.codex_runner --root principia dashboard
uv run python -m principia.cli.codex_runner --root principia packet --path claims/claim-1-example
uv run python -m principia.cli.codex_runner --root principia dispatch-log --cycle claim-1-example
uv run python -m principia.cli.codex_runner --root principia patch-status
uv run python -m principia.cli.codex_runner --root principia results
uv run python -m principia.cli.codex_runner --root principia visualize
```

Artifact ladder:

- `principia:status` or `dashboard`: current workflow state and operator guidance.
- `principia:next-step` or `next`: the next action.
- `patch-status`: north-star drift and reconciliation.
- `packet`, `prompt`, `dispatch-log`: stateful handoff tools.
- `principia:results` or `results`: stakeholder-facing synthesis.
- `visualize`: structural exploration.

Use `principia.cli.manage` only for state-changing operations like `falsify`, `settle`, `reopen`, `replace-verdict`, and `post-verdict`.

This bundle needs shared repo content under `principia/`, `agents/`, and `config/`; copying `plugins/codex` alone is unsupported.

## Layout

- `.codex-plugin/plugin.json`
- `skills/`
