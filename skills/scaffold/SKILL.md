---
name: scaffold
description: Create the directory structure for a new claim, cycle, unit, or sub-unit. Use when the system needs to start a new claim investigation, or (legacy) a new design cycle.
user-invocable: false
argument-hint: <claim|cycle|unit|sub-unit> <name> [--parent <path>]
allowed-tools:
  - Bash
---

# Scaffold Design Structure

Create the directory structure and progress file for a new claim (or legacy cycle/unit/sub-unit).

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design scaffold $ARGUMENTS
```

Examples:
- `scaffold claim topology-preservation` -- creates `design/claims/claim-1-topology-preservation/` with `claim.md` and role subdirectories (`architect/`, `adversary/`, `experimenter/`, `arbiter/`, `scout/`)

### Legacy Hierarchy

- `scaffold cycle enrichment` -- creates `design/cycles/cycle-1-enrichment/`
- `scaffold unit bottleneck --parent cycles/cycle-1-enrichment` -- creates `unit-1-bottleneck/` inside the cycle
- `scaffold sub-unit ratio-test --parent cycles/cycle-1-enrichment/unit-1-bottleneck` -- creates `sub-1a-ratio-test/` with role directories

## What gets created

**Claim**: Directory + `claim.md` + role subdirectories (`architect/`, `adversary/`, `experimenter/`, `arbiter/`, `scout/`)
**Cycle** (legacy): Directory + `progress.md`
**Unit** (legacy): Directory + `progress.md`
**Sub-unit** (legacy): Directory + `progress.md` + role subdirectories

Numbering is automatic -- the command counts existing siblings and assigns the next number.

## After scaffolding

Use `/principia:new` to create individual design files within the scaffolded structure, or dispatch agents directly to start the adversarial cycle.
