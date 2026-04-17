# Principia Codex Bundle

Canonical repo-local `plugins/codex` bundle for Principia.

Install Principia in Codex from the canonical `plugins/codex` surface inside a full Principia checkout.

## Remote marketplace install

Codex CLI `0.121.0` and newer can add Principia from GitHub without first opening the checkout as a repo-local marketplace:

```bash
codex marketplace add Gavin-Qiao/principia
```

The remote install surface is the repository root `marketplace.json`, which exposes `./plugins/codex` from the cloned marketplace root.

## Local marketplace install

The repository also publishes a repo-local Codex marketplace entry at `.agents/plugins/marketplace.json`, with `source.path` set to `./plugins/codex`.

Open the full Principia checkout in Codex, then install the `principia` plugin from the repo-local marketplace. This keeps the Codex bundle aligned with the official `plugins/<name>` structure while still using the shared runtime from the checkout.

Codex plugins expose Principia as skills, not slash commands. Start by asking Codex to use the `principia:init` skill, or simply ask it to initialize a Principia workspace for the current repository.

Common Codex skill entry points:

- `principia:init`
- `principia:status`
- `principia:next-step`
- `principia:validate`
- `principia:results`

In Codex, init is a guided repo ritual: it inspects the current project, scaffolds `principia/` if needed, collects autonomy and sidecar preferences, and stays in discussion until the north star is explicitly locked.

This bundle is Codex-native. It uses the packaged runner to talk to the shared Principia engine:

```bash
uv run python -m principia.cli.codex_runner --root principia dashboard
uv run python -m principia.cli.codex_runner --root principia next --path claims/claim-1-example
uv run python -m principia.cli.codex_runner --root principia packet --path claims/claim-1-example
uv run python -m principia.cli.codex_runner --root principia prompt --path claims/claim-1-example
uv run python -m principia.cli.codex_runner --root principia dispatch-log --cycle claim-1-example
uv run python -m principia.cli.codex_runner --root principia patch-status
uv run python -m principia.cli.codex_runner --root principia validate
uv run python -m principia.cli.codex_runner --root principia results
uv run python -m principia.cli.codex_runner --root principia visualize
```

Dispatch lifecycle is now explicit in the audit log:

- `packet`: canonical `packet.md` was materialized
- `dispatch`: external handoff artifacts were written
- `received`: a result artifact landed back in the claim workspace
- `recorded`: arbiter verdict bookkeeping was committed

The dashboard payload exposes:

- `dispatch_lifecycle` for the active or most recently touched claim
- `dispatch_overview` for workspace-wide stale/outstanding aggregation across all claims with dispatch history

Derived handoff statuses in `dispatch_lifecycle` are intentionally state-machine aware:

- `ready_to_send`: packet exists, but the handoff has not been dispatched yet
- `waiting_result`: dispatch artifacts exist and Principia is waiting on the external result
- `stale`: the audit log and the current claim/filesystem state disagree

`dispatch_handoff_stale` warnings are generated from `dispatch_overview`, so Codex can still surface stale claims even when the active claim itself is clean.
`dispatch_overview` also breaks out `ready_to_send_claims` and `waiting_result_claims`, so Codex can answer which claims are unsent versus genuinely waiting on an external return.

The bundle depends on shared repo content, including `principia/`, `agents/`, and `config/`. Copying `plugins/codex` by itself is unsupported.

The root `marketplace.json` and the repo-local entry in `.agents/plugins/marketplace.json` both point at `./plugins/codex`, so Codex can discover this bundle either from a remote marketplace add flow or directly from the checkout.

## Layout

- `.codex-plugin/plugin.json`: Codex plugin manifest
- `skills/`: canonical Codex workflow skills
