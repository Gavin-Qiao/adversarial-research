---
name: scaffold
description: Create the directory structure for a new claim. Use when the system needs to start a new claim investigation.
user-invocable: false
argument-hint: claim <name>
allowed-tools:
  - Bash
---

# Scaffold Design Structure

Create the directory structure for a new claim.

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design scaffold $ARGUMENTS
```

Examples:
- `scaffold claim topology-preservation` -- creates `design/claims/claim-1-topology-preservation/` with `claim.md` and role subdirectories (`architect/`, `adversary/`, `experimenter/`, `arbiter/`, `scout/`)

## What gets created

**Claim**: Directory + `claim.md` + role subdirectories (`architect/`, `adversary/`, `experimenter/`, `arbiter/`, `scout/`)

Numbering is automatic -- the command counts existing siblings and assigns the next number.

## After scaffolding

Use `/principia:new` to create individual design files within the scaffolded structure, or dispatch agents directly to start the adversarial cycle.
