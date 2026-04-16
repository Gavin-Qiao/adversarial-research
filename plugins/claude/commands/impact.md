---
description: Preview what would be weakened if a principia claim were disproven (dry run).
argument-hint: "<claim-id>"
allowed-tools: Bash
---

Show the cascade preview — what breaks if this claim is disproven. Read-only, no changes applied.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp cascade "$1"`

Present the list to the user as a decision aid.

## Output

Shows:
- The target node's current status and file path
- All nodes that would be set to `partial` (transitively via depends_on and assumes edges)
- Whether each affected node is a direct or transitive dependent
- The relation type (depends_on, assumes)

Use this before `/principia:falsify` to understand the impact.
