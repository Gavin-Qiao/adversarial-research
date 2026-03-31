---
name: falsify
description: Falsify a research claim or assumption and cascade to dependents. Use when evidence disproves a hypothesis, an assumption is invalidated, or a claim needs to be marked as falsified.
argument-hint: <node-id> [--by <evidence-id>]
allowed-tools:
  - Bash
---

# Falsify Node

Mark a research node as falsified and cascade the status change to all transitive dependents.

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research falsify $ARGUMENTS
```

Examples:
- `falsify assumption-homogeneity --by c1-u1-coder-output`
- `falsify c1-u1-s1a-thinker-r1-result`

## What happens

1. The target node's status is set to `falsified` in its frontmatter
2. If `--by` is provided, a `falsified_by` edge is created
3. All nodes that transitively `depends_on` or `assumes` the target are set to `mixed`
4. A ledger entry is recorded for each change
5. Nodes already `falsified` or `mixed` are skipped (no duplicates)

## After falsification

Run `/adversarial-research:status` to regenerate FRONTIER.md and see the updated state.
