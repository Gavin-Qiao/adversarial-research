---
description: Run integrity checks on the principia workspace (frontmatter, referential integrity, cycles).
argument-hint: "[--json]"
allowed-tools: Bash
---

Check the workspace for broken references, invalid frontmatter, and dependency cycles.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp validate $ARGUMENTS`

Summarize errors and warnings for the user. If `--json` was requested, preserve the structured output.

## Checks performed

- Duplicate node IDs
- Required fields (id, type, status, date, file_path)
- Valid status values (pending, active, proven, disproven, partial, weakened, inconclusive)
- Valid type values (claim, assumption, evidence, reference, verdict, question)
- Valid attack_type values (undermines, rebuts, undercuts)
- Self-loops in dependency edges
- Dependency cycles (DFS-based detection)
- Dangling edges (references to non-existent nodes)
- ID collisions (two files mapping to the same ID)

## On failure

Report the specific errors to the user and suggest fixes. Common issues:
- Dangling `depends_on` reference: the target node doesn't exist yet
- Cycle: two nodes depend on each other (restructure the dependency)
- Invalid status: typo in frontmatter
