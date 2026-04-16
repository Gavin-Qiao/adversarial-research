---
description: Mark a principia claim as disproven and cascade the weakening to dependents.
argument-hint: "<claim-id> [--by id]"
allowed-tools: Bash
---

Mark the claim as disproven. The core will cascade the effect to all dependents.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp falsify $ARGUMENTS`

Report what was weakened by the cascade.

Examples:
- `falsify assumption-homogeneity --by c1-u1-experimenter-output`
- `falsify c1-u1-s1a-architect-r1-result`

## What happens

1. The target node's status is set to `disproven` in its frontmatter
2. If `--by` is provided, a `disproven_by` edge is created
3. All nodes that transitively `depends_on` or `assumes` the target are set to `weakened`
4. A ledger entry is recorded for each change
5. Nodes already `disproven` or `weakened` are skipped (no duplicates)

## After disproval

Run `/principia:status` to regenerate PROGRESS.md and see the updated state.
