---
name: scaffold
description: Create the directory structure for a new cycle, unit, or sub-unit. Use when the user wants to start a new research cycle, add a unit to an existing cycle, or add a sub-unit to investigate a specific approach.
argument-hint: <cycle|unit|sub-unit> <name> [--parent <path>]
allowed-tools:
  - Bash
---

# Scaffold Research Structure

Create the directory structure and frontier file for a new cycle, unit, or sub-unit.

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research scaffold $ARGUMENTS
```

Examples:
- `scaffold cycle enrichment` — creates `research/cycles/cycle-1-enrichment/`
- `scaffold unit bottleneck --parent cycles/cycle-1-enrichment` — creates `unit-1-bottleneck/` inside the cycle
- `scaffold sub-unit ratio-test --parent cycles/cycle-1-enrichment/unit-1-bottleneck` — creates `sub-1a-ratio-test/` with role directories

## What gets created

**Cycle**: Directory + `frontier.md`
**Unit**: Directory + `frontier.md`
**Sub-unit**: Directory + `frontier.md` + role subdirectories (`thinker/`, `refutor/`, `coder/`, `judge/`, `researcher/`)

Numbering is automatic — the command counts existing siblings and assigns the next number.

## After scaffolding

Use `/adversarial-research:new` to create individual research files within the scaffolded structure, or dispatch agents directly to start the adversarial cycle.
