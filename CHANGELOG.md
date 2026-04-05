# Changelog

All notable changes to this project are documented in this file.

The format is inspired by Keep a Changelog, but organized around the release-note sections used for Principia releases: Features, Changed, Fixes, Docs, Packaging, Upgrade Notes, and Verification.

## [0.4.0a2] - 2026-04-05

### Features

- Introduced the packaged Principia runtime under `principia/`, including `principia.api.PrincipiaEngine` and `principia.cli.manage`.
- Added a Codex-native harness under `harnesses/codex/` with a plugin manifest, workflow skills, and a structured engine runner.

### Fixes

- Made `PrincipiaEngine` workspace-bound across `build`, `dashboard`, `validate`, and `results`, including concurrent use across separate workspaces.
- Bundled `agents/*.md` and `config/orchestration.yaml` so package-only imports can still load orchestration config and generate prompts.
- Hardened package import shims, CLI entrypoint behavior, Codex runner precedence, validate exit status handling, path traversal protection, duplicate-ID handling, reopen and replace-verdict semantics, RESULTS verdict display, and audit surfaces.

### Docs

- Added harness selection guidance for Claude and Codex in the top-level README.
- Clarified the repo-coupled Codex install contract and the packaged-asset behavior in the harness README and plugin manifest.

### Packaging

- Added setuptools build metadata and bundled package data for packaged orchestration assets.
- Bumped Principia and Codex plugin metadata to `0.4.0a2`.

### Upgrade Notes

- Install Codex from the repo-local `harnesses/codex/` surface inside a full repository checkout.
- Python package consumers now receive bundled orchestration config and agent instructions.

### Verification

- `uv run ruff check scripts/ tests/ principia`
- `uv run python -m pytest tests/ -q`
- `432 passed`

## [0.3.3] - 2026-04-04

### Features

- Made `/principia:help` adaptive to the current project state so onboarding guidance changes with workflow progress.

### Changed

- Removed legacy v0.2 compatibility aliases and old cycle/unit/sub-unit paths so the canonical vocabulary is now the only supported surface.

### Fixes

- Corrected report and cascade surfaces to use canonical verdict and status names consistently.
- Updated help guidance and init follow-up messaging to reflect dispatch and yolo-mode behavior.

### Internal

- Refreshed the lockfile for the dependency-group migration.

### Upgrade Notes

- Legacy aliases and nested layouts are no longer supported; use flat `claims/claim-N-name/claim.md` paths, canonical role names, and canonical verdict and status terms.

### Verification

- `346 tests` passing
- lint, format, and mypy clean

## [0.3.2] - 2026-04-04

### Features

- Added `/principia:help` onboarding with command reference, agent overview, mode explanations, and a getting-started example.

### Fixes

- Corrected marketplace installation guidance to use the proper `owner/repo` shorthand.
- Replaced the unreadable Mermaid agent-phase map with clear markdown tables.

### Upgrade Notes

- Update the plugin, reload it, and run `/principia:help` to see the new guide.

## [0.3.1] - 2026-04-04

### Docs

- Rewrote the README diagrams to show ambient agent participation across the pipeline.
- Added agent-phase and access-level reference tables.
- Expanded the agent documentation for isolation, anti-convergence, and knowledge divergence.

### Verification

- Documentation-only release; same functionality and test baseline as `v0.3.0`

## [0.3.0] - 2026-04-03

### Features

- Introduced the 4-phase investigation model: Understand, Divide, Test, and Synthesize.
- Replaced the nested cycle/unit/sub-unit hierarchy with flat claims and dependency-wave execution.
- Added configurable autonomy, quick mode, `@deep-thinker`, conductor-driven debate extension, `validate-paste`, `autonomy-config`, and `extend-debate`.

### Changed

- Added schema v3 with agent attribution in the ledger and stronger post-build integrity checks.

### Fixes

- Corrected confidence extraction, claim scaffolding metadata propagation, flat-claim discovery, type inference for `claim.md` vs `frontier.md`, post-verdict fallbacks, and orphan-edge cleanup.

### Docs

- Rewrote the README with diagrams and aligned the skills, agents, and methodology docs with the flat-claims model.

### Upgrade Notes

- The database auto-migrates from schema v2 to v3 while preserving ledger and dispatch history.

### Verification

- `373 tests` passing
