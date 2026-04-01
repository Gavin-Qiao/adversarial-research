---
name: scaffold
description: Create the directory structure for a new cycle, unit, or sub-unit. Use when the system needs to start a new design cycle, add a unit to an existing cycle, or add a sub-unit to investigate a specific approach.
user-invocable: false
argument-hint: <cycle|unit|sub-unit> <name> [--parent <path>]
allowed-tools:
  - Bash
---

# Scaffold Design Structure

Create the directory structure and progress file for a new cycle, unit, or sub-unit.

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design scaffold $ARGUMENTS
```

Examples:
- `scaffold cycle enrichment` -- creates `design/cycles/cycle-1-enrichment/`
- `scaffold unit bottleneck --parent cycles/cycle-1-enrichment` -- creates `unit-1-bottleneck/` inside the cycle
- `scaffold sub-unit ratio-test --parent cycles/cycle-1-enrichment/unit-1-bottleneck` -- creates `sub-1a-ratio-test/` with role directories

## What gets created

**Cycle**: Directory + `progress.md`
**Unit**: Directory + `progress.md`
**Sub-unit**: Directory + `progress.md` + role subdirectories (`architect/`, `adversary/`, `experimenter/`, `arbiter/`, `scout/`)

Numbering is automatic -- the command counts existing siblings and assigns the next number.

## After scaffolding

Use `/principia:new` to create individual design files within the scaffolded structure, or dispatch agents directly to start the adversarial cycle.
