# Principia Plugin Bundle Migration Design

## Summary

Restructure Principia so Claude Code and Codex both consume explicit plugin bundles while sharing one packaged runtime.

The target model is:

- `principia/` is the only shared runtime and packaging surface.
- `plugins/claude/` is the Claude Code distribution bundle.
- `plugins/codex/` is the Codex distribution bundle.
- provider-specific plugin folders contain only manifests, skills, hooks, agent definitions, thin scripts, and documentation.
- plugin bundles call stable package entrypoints in `principia`, not repo-relative harness glue.

This migration prioritizes Codex installability and documentation quality, while also moving Claude to the same high-level abstraction so the repository structure is coherent.

## Problem

Principia currently has an uneven harness split:

- Claude Code uses the repository root as the plugin bundle via `.claude-plugin/`, `agents/`, `skills/`, and `hooks/`.
- Codex uses `harnesses/codex/`, which behaves like a plugin bundle but still carries repo-coupled assumptions and a less obvious install story.
- The repository therefore mixes runtime code, provider-specific integration surfaces, and documentation in a way that is harder to explain than it should be.

This causes three product problems:

1. Codex installation is less obvious than it should be for a fresh external user.
2. The two harnesses are structurally inconsistent, which makes the README and packaging story harder to keep honest.
3. Harness bundles still risk accumulating repo-relative assumptions instead of depending on a stable packaged runtime.

## Goals

1. Make Codex use the official plugin-bundle model cleanly.
2. Move Claude and Codex to symmetric plugin bundle locations.
3. Keep `principia/` as the only shared runtime.
4. Make plugin bundles thin and provider-specific.
5. Ensure both bundles can be documented clearly in a side-by-side harness chooser.
6. Keep local development practical through a repo-local marketplace flow.

## Non-Goals

- Rewriting the Principia engine architecture beyond what is required for stable package entrypoints.
- Shipping a new visual brand, logo, or hero asset in this migration.
- Adding MCP as a new backend surface for Principia.
- Preserving the old root-Claude and `harnesses/codex` layouts as permanent public interfaces.

## Current State

```text
principia/
├── .claude-plugin/
├── agents/
├── skills/
├── hooks/
├── harnesses/
│   ├── claude/
│   └── codex/
├── principia/
└── .agents/plugins/marketplace.json
```

## Target State

```text
principia/
├── principia/
│   ├── api/
│   ├── cli/
│   ├── agents/
│   └── config/
├── plugins/
│   ├── claude/
│   │   ├── .claude-plugin/
│   │   ├── agents/
│   │   ├── skills/
│   │   ├── hooks/
│   │   └── README.md
│   └── codex/
│       ├── .codex-plugin/
│       ├── skills/
│       ├── scripts/
│       └── README.md
├── .agents/plugins/marketplace.json
├── README.md
└── CHANGELOG.md
```

## Core Abstraction

### Runtime vs. Bundle

The migration standardizes one boundary:

- `principia/` is the runtime.
- `plugins/<provider>/` is the distribution bundle for that provider.

The runtime owns:

- engine APIs
- CLI entrypoints
- packaged orchestration assets
- packaged agent instructions
- shared validation and reporting logic

The plugin bundles own:

- provider manifests
- provider-facing skills
- provider-only hooks or agent definitions
- thin launcher scripts
- harness-specific docs

No provider bundle should import arbitrary repo files outside the package runtime.

### Stable Entrypoints

Both plugin bundles should invoke stable packaged entrypoints under `principia.cli`.

For Codex, the planned execution path is:

```text
plugin skill -> thin wrapper -> uv run python -m principia.cli.codex_runner
```

For Claude, any existing script or hook execution should similarly resolve through package-owned modules or packaged files, not through assumptions about repository-root adjacency.

## Claude Code Bundle

Claude already follows the official plugin model conceptually:

- `.claude-plugin/plugin.json`
- `agents/`
- `skills/`
- `hooks/`

The migration changes the location, not the model.

### Claude Migration Rules

- Move the canonical Claude plugin surface from repository root into `plugins/claude/`.
- Preserve the same logical contents:
  - `.claude-plugin/`
  - `agents/`
  - `skills/`
  - `hooks/`
- Update Claude-facing docs to reference the new bundle location.
- Avoid rewriting Claude behavior beyond path corrections required by the move.

Claude is included in this migration to make the final repository abstraction clean, but Codex remains the primary product priority during implementation and verification.

## Codex Bundle

Codex becomes a first-class plugin bundle under `plugins/codex/`.

### Codex Migration Rules

- Move the canonical Codex plugin surface from `harnesses/codex/` into `plugins/codex/`.
- Update `.agents/plugins/marketplace.json` so the repo-local marketplace points to `./plugins/codex`.
- Replace repo-relative runner assumptions with package entrypoints under `principia.cli`.
- Keep Codex skills as the main user workflow surface.
- Keep `uv` as the documented runtime wrapper for Codex commands.

### Codex Install Model

This migration adopts the official plugin-bundle model correctly:

- repo-local development uses the repository marketplace at `.agents/plugins/marketplace.json`
- Codex plugin bundle lives under `plugins/codex/`
- the bundle is the install surface
- the shared runtime comes from the packaged `principia` code

The release documentation must only describe install paths that are verified end to end.

## Marketplace Model

### Repo-Local Marketplace

The repository marketplace remains at:

- `.agents/plugins/marketplace.json`

After migration, it should expose the Codex bundle via:

```json
{
  "name": "principia",
  "interface": {
    "displayName": "Principia"
  },
  "plugins": [
    {
      "name": "principia",
      "source": {
        "source": "local",
        "path": "./plugins/codex"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

This marketplace is for repo-local development and testing.

### Personal Install Support

Personal installation is not the primary target of this migration. If it is documented later, it should follow the official Codex conventions rather than ad hoc paths.

## Documentation Model

The top-level README should become concept-first, then harness-first.

### Required README Behavior

- explain what Principia is in a sharper, shorter opening section
- present Claude and Codex side by side as equal harness choices
- make Codex installation explicit and executable
- explain that both harnesses share one packaged runtime
- remove misleading or ambiguous install language

### Harness Docs

Each plugin bundle should own a provider-specific README:

- `plugins/claude/README.md`
- `plugins/codex/README.md`

These should contain:

- exact install path for the provider
- bundle layout summary
- runtime expectations
- local development notes if needed

## Migration Plan

### Phase 1: Create Canonical Bundles

1. Create `plugins/claude/`.
2. Create `plugins/codex/`.
3. Copy or move provider-specific files into those bundle locations.
4. Keep behavior unchanged where possible while paths move.

### Phase 2: Package-Owned Entrypoints

1. Add package entrypoints required by the bundles under `principia.cli`.
2. Update Codex wrapper scripts and skills to call those entrypoints through `uv`.
3. Update Claude path references if any root-relative assumptions exist.

### Phase 3: Marketplace and Docs

1. Update `.agents/plugins/marketplace.json` to point at `./plugins/codex`.
2. Rewrite README around the new harness chooser.
3. Update provider-specific READMEs for the new bundle locations.

### Phase 4: Compatibility Cleanup

1. Remove or reduce `harnesses/codex/` once the new bundle is proven.
2. Remove the old root-Claude plugin surface once the new Claude bundle is proven.
3. Update tests to enforce only the new canonical paths.

## Verification Contract

The migration is not complete until these conditions are true.

### Codex

- a fresh user can follow the documented Codex install instructions verbatim
- the plugin loads from the official bundle location
- Codex skills resolve from `plugins/codex/`
- Codex workflow commands execute via the packaged runtime

### Claude

- Claude still loads the plugin successfully after the bundle move
- Claude skills, hooks, and agents resolve from `plugins/claude/`
- the documented Claude install path is correct

### Shared Runtime

- both harnesses invoke the same packaged runtime
- no plugin bundle requires repo-root path walking for normal operation
- package-installed assets remain sufficient for prompt generation and orchestration config loading

### Docs

- README instructions are verified exactly as written
- bundle READMEs match actual file locations

## Risks

### Claude Path Breakage

Moving the Claude bundle off the repository root may break assumptions in hooks, manifests, or docs.

Mitigation:

- move files conservatively
- verify hooks and skills after each step
- keep the migration focused on location and entrypoint changes, not behavioral redesign

### Codex Runtime Drift

Codex scripts may accidentally retain repo-relative assumptions.

Mitigation:

- require package entrypoints
- test from fresh environments
- avoid calling arbitrary files outside `principia`

### Documentation Mismatch

A polished README can still be wrong if the exact steps are not exercised.

Mitigation:

- treat README instructions as executable acceptance tests
- do not ship until the documented steps work verbatim

## Acceptance Criteria

This migration is complete when:

1. `plugins/claude/` and `plugins/codex/` are the canonical plugin bundles.
2. `principia/` is the only shared runtime surface.
3. Codex installs and runs from the official plugin model cleanly.
4. Claude is migrated to the new bundle location.
5. The README can honestly present Claude and Codex side by side.
6. Fresh-user installation works from the published instructions.
