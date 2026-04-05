---
name: settle
description: Prove a design claim or assumption after evidence supports it. Use when a design proposal has been validated, an arbiter has rendered a PROVEN verdict, or a claim has sufficient evidence to be accepted.
user-invocable: false
argument-hint: <node-id>
allowed-tools:
  - Bash
---

# Prove Node

Mark a design node as proven, recording the decision in the audit ledger.

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design settle $ARGUMENTS
```

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
