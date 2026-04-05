---
name: status
description: Generate the design progress and assumptions report. Use when the user wants to see the current state of the design, what's proven, what's disproven, what's next, or the assumption registry.
allowed-tools:
  - Bash
  - Read
---

# Design Status

Regenerate PROGRESS.md and FOUNDATIONS.md from the current state of all design files.

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design status
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design assumptions
```

Then read and present the key sections from `design/PROGRESS.md`:
- **Current blockers**: Active nodes blocking pending work
- **What is proven**: Claims that have been established
- **What is disproven**: Claims that have been refuted
- **Assumptions**: Status of all tracked assumptions
- **Next action**: The first pending node to work on

## PROGRESS.md sections

| Section | What it shows |
|---------|--------------|
| Current blockers | Active nodes with pending dependents |
| What is proven | Proven claims grouped by cycle |
| What is disproven | Disproven nodes with evidence |
| Assumptions | All assumptions with dependent counts |
| Claim log | Status of all claims (plus legacy cycle log if present) |
| Next action | First pending node by file path |
