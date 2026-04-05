---
name: query
description: Run SQL queries against the design database. Use when the user wants to query nodes, edges, or the audit ledger directly.
argument-hint: "<SQL query>"
allowed-tools:
  - Bash
---

# Query Design Database

Run read-only SQL against the design SQLite database.

## Usage

```bash
uv run python -m principia.cli.manage --root principia query "$ARGUMENTS"
```

## Available tables

### nodes
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key, derived from path |
| type | TEXT | claim, assumption, evidence, reference, verdict, question |
| status | TEXT | pending, active, proven, disproven, partial |
| date | TEXT | ISO date (YYYY-MM-DD) |
| file_path | TEXT | Relative path from design root |
| title | TEXT | First `# heading` from file body |
| counterfactual | TEXT | What would change if this were false |
| attack_type | TEXT | undermines, rebuts, undercuts |

### edges
| Column | Type | Description |
|--------|------|-------------|
| source_id | TEXT | Node that has the dependency |
| target_id | TEXT | Node being depended on |
| relation | TEXT | depends_on, assumes, disproven_by |

### ledger
| Column | Type | Description |
|--------|------|-------------|
| timestamp | TEXT | ISO date of event |
| event | TEXT | disproven, updated |
| node_id | TEXT | Affected node |
| details | TEXT | Human-readable description |

## Example queries

- `"SELECT id, status FROM nodes WHERE type='assumption'"`
- `"SELECT COUNT(*) as c FROM edges GROUP BY relation"`
- `"SELECT * FROM ledger ORDER BY timestamp DESC LIMIT 10"`

Only SELECT, EXPLAIN, and PRAGMA are allowed.
