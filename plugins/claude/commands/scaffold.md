---
description: Create a claim directory structure (claim directory skeleton with stub files).
argument-hint: "<level> <name>"
allowed-tools: Bash
---

Create a scaffolded directory for a new claim.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp scaffold "$1" "$2"`

Report which files were created.

Examples:
- `scaffold claim topology-preservation` — creates a claim directory with `claim.md` and role subdirectories (`architect/`, `adversary/`, `experimenter/`, `arbiter/`, `scout/`)

## What gets created

**Claim**: Directory + `claim.md` + role subdirectories (`architect/`, `adversary/`, `experimenter/`, `arbiter/`, `scout/`)

Numbering is automatic — the command counts existing siblings and assigns the next number.

## After scaffolding

Use `/principia:new` to create individual design files within the scaffolded structure, or dispatch agents directly to start the adversarial cycle.
