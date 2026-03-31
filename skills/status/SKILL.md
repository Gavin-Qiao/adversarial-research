---
name: status
description: Generate the research frontier and assumptions report. Use when the user wants to see the current state of research, what's settled, what's falsified, what's next, or the assumption registry.
allowed-tools:
  - Bash
  - Read
---

# Research Status

Regenerate FRONTIER.md and ASSUMPTIONS.md from the current state of all research files.

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research status
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research assumptions
```

Then read and present the key sections from `research/FRONTIER.md`:
- **Current blockers**: Active nodes blocking pending work
- **What is settled**: Decisions that have been made
- **What is falsified**: Claims that have been disproven
- **Assumptions**: Status of all tracked assumptions
- **Next action**: The first pending node to work on

## FRONTIER.md sections

| Section | What it shows |
|---------|--------------|
| Current blockers | Active nodes with pending dependents |
| What is settled | Settled claims grouped by cycle |
| What is falsified | Falsified nodes with evidence |
| Assumptions | All assumptions with dependent counts |
| Cycle log | Hierarchical view of cycles/units/sub-units |
| Next action | First pending node by file path |
