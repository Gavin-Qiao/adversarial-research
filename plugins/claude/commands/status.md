---
description: Regenerate principia/PROGRESS.md from the current database state.
allowed-tools: Bash
---

Rebuild PROGRESS.md to reflect the current workspace state.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp status`

Then read and present the key sections from PROGRESS.md:
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
