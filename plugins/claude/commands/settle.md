---
description: Mark a principia claim as proven.
argument-hint: "<claim-id>"
allowed-tools: Bash
---

Mark the claim as settled (proven). Updates the ledger and frontmatter.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp settle "$1"`

Confirm the settlement and note any downstream consequences from the output.

Examples:
- `settle c1-u1-s1a-architect-r1-result`
- `settle assumption-homogeneity`

## What happens

1. The target node's status is set to `proven` in its frontmatter
2. A ledger entry is recorded with timestamp
3. Disproven nodes cannot be proven (use a new design proposal instead)
4. Already-proven nodes are skipped with a warning

## After proving

Run `/principia:status` to regenerate PROGRESS.md and see the updated state.
