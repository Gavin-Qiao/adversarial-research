---
name: settle
description: Settle a research claim or assumption after evidence supports it. Use when a hypothesis has been validated, a judge has rendered a SETTLED verdict, or a claim has sufficient evidence to be accepted.
argument-hint: <node-id>
allowed-tools:
  - Bash
---

# Settle Node

Mark a research node as settled, recording the decision in the audit ledger.

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research settle $ARGUMENTS
```

Examples:
- `settle c1-u1-s1a-thinker-r1-result`
- `settle assumption-homogeneity`

## What happens

1. The target node's status is set to `settled` in its frontmatter
2. A ledger entry is recorded with timestamp
3. Falsified nodes cannot be settled (use a new hypothesis instead)
4. Already-settled nodes are skipped with a warning

## After settling

Run `/adversarial-research:status` to regenerate FRONTIER.md and see the updated state.
