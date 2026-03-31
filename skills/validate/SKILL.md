---
name: validate
description: Check research log integrity. Use when the user wants to verify the research database, check for broken references, cycles, or invalid metadata.
allowed-tools:
  - Bash
---

# Validate Research Log

Run integrity checks on the research database.

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research validate
```

## Checks performed

- Duplicate node IDs
- Required fields (id, type, status, date, file_path)
- Valid status values (pending, active, settled, falsified, mixed)
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
