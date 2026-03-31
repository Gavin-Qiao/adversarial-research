---
name: query
description: Run SQL queries against the research database. Use when the user wants to query nodes, edges, or the audit ledger directly.
argument-hint: "<SQL query>"
allowed-tools:
  - Bash
---

# Query Research Database

Run read-only SQL against the research SQLite database.

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research query "$ARGUMENTS"
```

## Available tables

### nodes
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key, derived from path |
| type | TEXT | claim, assumption, evidence, reference, verdict, question |
| status | TEXT | pending, active, settled, falsified, mixed |
| date | TEXT | ISO date (YYYY-MM-DD) |
| file_path | TEXT | Relative path from research root |
| title | TEXT | First `# heading` from file body |
| counterfactual | TEXT | What would change if this were false |
| attack_type | TEXT | undermines, rebuts, undercuts |

### edges
| Column | Type | Description |
|--------|------|-------------|
| source_id | TEXT | Node that has the dependency |
| target_id | TEXT | Node being depended on |
| relation | TEXT | depends_on, assumes, falsified_by |

### ledger
| Column | Type | Description |
|--------|------|-------------|
| timestamp | TEXT | ISO date of event |
| event | TEXT | falsified, updated |
| node_id | TEXT | Affected node |
| details | TEXT | Human-readable description |

## Example queries

- `"SELECT id, status FROM nodes WHERE type='assumption'"`
- `"SELECT COUNT(*) as c FROM edges GROUP BY relation"`
- `"SELECT * FROM ledger ORDER BY timestamp DESC LIMIT 10"`

Only SELECT, EXPLAIN, and PRAGMA are allowed.
