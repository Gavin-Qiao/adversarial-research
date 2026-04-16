# Principia Core ↔ Adapter Contract

**Contract version:** 1

This document is the stable interface between `principia/` (core) and any adapter bundle (including `plugins/claude/`). Public CLI operations listed here MUST preserve input/output shape. Breaking changes require a contract version bump.

## JSON envelope

All machine-readable (JSON) responses share this structure:

```json
{
  "schema_version": 1,
  "data":   { ... operation-specific payload ... },
  "warnings": []
}
```

- `schema_version` (int, required) — bump on breaking output changes.
- `data` (object or array) — the operation's payload.
- `warnings` (array of strings) — non-fatal notices.

### Compatibility rules

- **Additive change** (new optional field in `data`): no bump. Adapters ignore unknown fields.
- **Breaking change** (remove/rename field, change type, change semantics): bump `schema_version`; adapters update.

## Categories

Operations are grouped by output form:

- **JSON-emitting**: return the envelope `{schema_version, data, warnings}`. Plugin parses `data`.
- **Text-only**: print human-readable output. Plugin reads exit code and optionally displays stdout to the user. No stable structured contract.

All invoked as `python -m principia.cli.manage --root <root> <op> [args]`.

## JSON-emitting operations

### Discovery

| Op | Input | `data` shape | Semantics |
|---|---|---|---|
| `paths` | `--root [--json]` | `{root, db, claims_dir, context_dir, progress, foundations, config}` | Workspace path layout. |
| `roles` | `--root [--json]` | `[{name, phase, type?}, ...]` | Role registry. |
| `phases` | `--root [--json]` | `[{name, roles, exit_condition?}, ...]` | Phase machinery. |
| `schema` | `--root [--json]` | `{types, statuses, maturities, confidences}` | Frontmatter value sets. |

### Inspection

| Op | Input | `data` shape | Semantics |
|---|---|---|---|
| `validate` | `--root [--json]` | `{valid, error_count, errors, node_count?, edge_count?}` | Integrity check. `node_count`/`edge_count` present only when `valid` is true. |
| `query` | `"<sql>" [--json]` | `[{col: val, ...}, ...]` — flat list of row dicts | Run SQL against the DB. |
| `list` | `[--json]` | `[{id, type, status, maturity?, confidence?, title?, file_path}, ...]` | All nodes. |
| `waves` | `[--claim id] [--json]` | `[[{id, type, status, ...}, ...], ...]` — list of lists of row dicts | Parallelizable claim groups. |
| `dispatch-log` | `[--cycle N] [--json]` | `[{cycle_id, agent, action, round, timestamp, details, sub_unit?, dispatch_mode, packet_path, prompt_path, result_path}, ...]` | Dispatch history. `cycle_id` identifies which claim the dispatch belongs to. `sub_unit` is nullable (present in every row, may be null). |
| `dashboard` | `--root` | `{phase, action, breadcrumb, active_claim, active_cycle, dispatch_lifecycle, dispatch_overview, last_verdict, claims, blocked, pending_decisions, autonomy, init, ...}` | Workspace state payload. |
| `next` | `[<claim-path>]` | `{action, phase, agent?, round?, sub_unit?, dispatch_mode?, packet_path?, prompt_path?, result_path?, context_files?, north_star?}` | Next state for one claim (or investigation-wide if no path). |
| `investigate-next` | `--root` | `{action, phase, substeps?, breadcrumb}` | Next investigation-wide state. |

### Workflow

| Op | Input | `data` shape | Semantics |
|---|---|---|---|
| `post-verdict` | `<claim-path>` | `{verdict, confidence, node_id, changes}` | Apply cascade after verdict. `changes` is a list of strings. |

### Bookkeeping

| Op | Input | `data` shape | Semantics |
|---|---|---|---|
| `parse-framework` | (reads `blueprint.md`) | `[{id, statement, maturity, confidence, depends_on, falsification}, ...]` | Parse synthesizer blueprint. |
| `autonomy-config` | `--root` | `{mode, checkpoint_at}` | Read autonomy settings. `mode` is `"checkpoints"` or `"yolo"`. |

## Text-only operations

These operations print human-readable text to stdout. The plugin contract is: **exit code** (0 = success, non-zero = failure) plus optional display of stdout to the user. There is no stable structured JSON contract for these.

| Op | Input | Exit code semantics |
|---|---|---|
| `build` | `--root` | 0 = DB rebuilt. (Note: `--json` flag is not supported; output is always text.) |
| `status` | `--root` | 0 = `PROGRESS.md` regenerated. |
| `assumptions` | `--root` | 0 = `FOUNDATIONS.md` regenerated. |
| `scaffold` | `<level> <name>` | 0 = directory skeleton created. |
| `new` | `<relative-path>` | 0 = markdown file created with auto frontmatter. |
| `settle` | `<claim-id>` | 0 = claim marked proven. |
| `falsify` | `<claim-id> [--force] [--by id]` | 0 = claim marked disproven; cascade applied. |
| `reopen` | `<claim-path>` | 0 = verdict reverted, claim reopened. |
| `replace-verdict` | `<claim-path>` | 0 = verdict replaced. |
| `extend-debate` | `<claim-path> <round_count>` | 0 = max rounds increased. |
| `cascade` | `<claim-id>` | 0 = cascade preview printed (dry-run, no mutations). |
| `log-dispatch` | `--cycle <id> --agent <a> --action <act> --round <n>` | 0 = dispatch event recorded. |
| `register` | `<id> --name <n> --type <t> --path <p>` | 0 = artifact registered. |
| `artifacts` | `--root` | 0 = artifact table printed. |
| `codebook` | `--root` | 0 = `TOOLKIT.md` generated. |
| `context` | `<claim-path>` | 0 = context document printed. |
| `packet` | `<claim-path>` | 0 = packet artifact written. |
| `prompt` | `<claim-path>` | 0 = prompt artifact written. |

## Versioning

- **Contract version** (this document): `1`.
- **Patch** (additive): add op, add optional field in `data` — no version bump.
- **Breaking**: rename op, remove op, incompatible output shape — bump to `2`. Old and new may coexist until consumers migrate.

## Non-contract (internal)

Subcommands of `manage.py` NOT listed above are internal and may change without notice. Adapters MUST NOT reference them directly; wire them through the adapter's wrapper.
