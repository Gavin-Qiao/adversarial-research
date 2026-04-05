---
name: validate
description: Check design log integrity. Use when the system needs to verify the design database, check for broken references, cycles, or invalid metadata.
user-invocable: false
allowed-tools:
  - Bash
---

# Validate Design Log

Run integrity checks on the design database.

## Usage

```bash
uv run python -m principia.cli.manage --root design validate
```

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
