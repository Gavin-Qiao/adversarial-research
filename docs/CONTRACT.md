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

## Public operations

All invoked as `python -m principia.cli.manage --root <root> <op> [args]`.

### Workflow

| Op | Input | Output (data) | Semantics |
|---|---|---|---|
| `build` | `--root` | `{nodes_count, edges_count}` (when `--json`; human text otherwise) | Rebuild SQLite DB from markdown. |
| `next` | `<claim-path>` | `{breadcrumb, action, dispatch_mode, context_files, ...}` | Next state for one claim. |
| `investigate-next` | `--root` | same shape as `next` | Next investigation-wide state. |
| `post-verdict` | `<claim-path>` | `{actions_taken, cascaded}` | Apply cascade after verdict. |
| `extend-debate` | `<claim-path> <round_count>` | `{new_max_rounds}` | Allow more debate rounds. |
| `reopen` | `<claim-path>` | `{reopened}` | Revert verdict, reopen claim. |
| `replace-verdict` | `<claim-path>` | `{replaced}` | Substitute a new verdict. |

### Inspection

| Op | Input | Output (data) | Semantics |
|---|---|---|---|
| `status` | `--root` | (writes `PROGRESS.md`; stdout = summary) | Regenerate `PROGRESS.md`. |
| `validate` | `--root [--json]` | `{errors: [...], warnings: [...], node_count, ok}` | Integrity check. |
| `query` | `"<sql>" [--json]` | `{columns, rows}` | Run SQL against the DB. |
| `dashboard` | `--root` | `{phase, claims, verdicts, blockers, dispatch_overview, ...}` | Workspace state payload. |
| `dispatch-log` | `[--cycle N] [--json]` | `[{timestamp, agent, round, claim}, ...]` | Dispatch history. |
| `assumptions` | `--root` | (writes `FOUNDATIONS.md`) | Regenerate `FOUNDATIONS.md`. |

### Mutation

| Op | Input | Output (data) | Semantics |
|---|---|---|---|
| `scaffold` | `<level> <name>` | `{created, path}` | Create claim directory skeleton. |
| `new` | `<relative-path>` | `{created, path, id}` | Create markdown with auto frontmatter. |
| `settle` | `<claim-id>` | `{settled, id}` | Mark claim proven. |
| `falsify` | `<claim-id> [--by id]` | `{falsified, id, cascade: [...]}` | Mark claim disproven, cascade. |
| `register` | `<path>` | `{registered, id}` | Register a new claim in the DB. |

### Planning

| Op | Input | Output (data) | Semantics |
|---|---|---|---|
| `cascade` | `<claim-id>` | `{would_weaken: [...]}` | Preview cascade impact. |
| `waves` | `[--claim id] [--json]` | `[[claim-id, ...], ...]` | Parallelizable claim groups. |
| `context` | `<claim-path>` | `{files: [...], summary}` | Gather agent context. |
| `packet` | `<claim-path>` | `{written_to}` | Write context packet artifact. |
| `prompt` | `<claim-path>` | `{prompt}` | External-mode prompt text. |

### Bookkeeping

| Op | Input | Output (data) | Semantics |
|---|---|---|---|
| `log-dispatch` | `<claim-path> <agent> <round>` | `{logged}` | Record agent dispatch. |
| `parse-framework` | `<path>` | `{claims: [...]}` | Parse synthesizer blueprint. |
| `artifacts` | `<claim-path>` | `{artifacts: [...]}` | List artifacts for a claim. |
| `codebook` | (none) | `{patterns: [...]}` | Experimentation patterns reference. |
| `autonomy-config` | `--root` | `{autonomy, dispatch_prefs}` | Read `principia/.config.md`. |

### Discovery (contract v1)

| Op | Input | Output (data) | Semantics |
|---|---|---|---|
| `paths` | `--root [--json]` | `{root, db, claims_dir, context_dir, progress, foundations, config}` | Workspace path layout. |
| `roles` | `--root [--json]` | `[{name, phase, type?}, ...]` | Role registry. |
| `phases` | `--root [--json]` | `[{name, roles, exit_condition?}, ...]` | Phase machinery. |
| `schema` | `--root [--json]` | `{types, statuses, maturities, confidences}` | Frontmatter value sets. |

## Versioning

- **Contract version** (this document): `1`.
- **Patch** (additive): add op, add optional field in `data` — no version bump.
- **Breaking**: rename op, remove op, incompatible output shape — bump to `2`. Old and new may coexist until consumers migrate.

## Non-contract (internal)

Subcommands of `manage.py` NOT listed above are internal and may change without notice. Adapters MUST NOT reference them directly; wire them through the adapter's wrapper.
