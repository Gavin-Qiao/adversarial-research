---
name: falsify
description: Disprove a design claim or assumption and cascade to dependents. Use when evidence refutes a design proposal, an assumption is invalidated, or a claim needs to be marked as disproven.
user-invocable: false
argument-hint: <node-id> [--by <evidence-id>]
allowed-tools:
  - Bash
---

# Disprove Node

Mark a design node as disproven and cascade the status change to all transitive dependents.

## Usage

```bash
uv run python -m principia.cli.manage --root design falsify $ARGUMENTS
```

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
