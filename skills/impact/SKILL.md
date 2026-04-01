---
name: impact
description: Dry-run cascade analysis showing what would be affected if a node were disproven. Use when the user wants to see the blast radius of disproving a claim or assumption before committing.
argument-hint: <node-id>
allowed-tools:
  - Bash
---

# Cascade Analysis (Dry Run)

Show what nodes would be affected if a given node were disproven, without making any changes.

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design cascade $ARGUMENTS
```

## Output

Shows:
- The target node's current status and file path
- All nodes that would be set to `partial` (transitively via depends_on and assumes edges)
- Whether each affected node is a direct or transitive dependent
- The relation type (depends_on, assumes)

Use this before `/principia:falsify` to understand the impact.
