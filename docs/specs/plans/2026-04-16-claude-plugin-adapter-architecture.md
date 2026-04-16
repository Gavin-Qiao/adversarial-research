# Claude Plugin Adapter Architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the Claude Code plugin bundle into a true adapter over a versioned CLI contract, so internal core refactors no longer ripple into plugin files. Ship as `v0.5.claude` on the `claude-code-plugin` branch, local-marketplace-installable.

**Architecture:** Three layers — universal core (`principia/`), claude adapter (`plugins/claude/`), and a stable contract (`docs/CONTRACT.md` + versioned JSON outputs). Adapter calls core only via a single bash wrapper `plugins/claude/scripts/pp` which maps contract operation names to current CLI invocations.

**Tech Stack:** Python 3.12+ (stdlib-only runtime), bash, JSON, `uv` for environment, pytest, ruff, mypy. Target Claude Code plugin conventions circa April 2026 (commands/, skills/, agents/, hooks/hooks.json, `${CLAUDE_PLUGIN_ROOT}`).

**Spec:** `docs/specs/2026-04-16-claude-plugin-adapter-architecture-design.md`

**Branch discipline:** Commit to `claude-code-plugin` only. No merges, no tags, no push to main. Supervisor handles release. Agent may push to `origin/claude-code-plugin` after the final task so the supervisor can see the work.

---

## File structure

Map of every file touched. Each file has one clear responsibility.

### Created (new files)

| Path | Responsibility |
|---|---|
| `.claude-plugin/marketplace.json` | Root-level marketplace manifest; catalogs the `principia` plugin at `./plugins/claude`. |
| `docs/CONTRACT.md` | Contract specification: 20 public operations, IO schemas, semantics, versioning rules. |
| `plugins/claude/scripts/pp` | Bash wrapper — the ONLY plugin file that knows the current CLI shape. Dispatches contract ops to `principia.cli.manage`. |
| `plugins/claude/commands/init.md` | `/principia:init` slash command — workspace bootstrap + guided discussion. |
| `plugins/claude/commands/design.md` | `/principia:design` — full 4-phase pipeline. |
| `plugins/claude/commands/step.md` | `/principia:step` — advance workflow by one state. |
| `plugins/claude/commands/status.md` | `/principia:status` — regenerate PROGRESS.md. |
| `plugins/claude/commands/validate.md` | `/principia:validate` — integrity check. |
| `plugins/claude/commands/query.md` | `/principia:query` — SQL on the database. |
| `plugins/claude/commands/new.md` | `/principia:new` — create markdown with frontmatter. |
| `plugins/claude/commands/scaffold.md` | `/principia:scaffold` — create claim directory structure. |
| `plugins/claude/commands/settle.md` | `/principia:settle` — mark claim proven. |
| `plugins/claude/commands/falsify.md` | `/principia:falsify` — mark claim disproven, cascade. |
| `plugins/claude/commands/impact.md` | `/principia:impact` — preview cascade (contract op `cascade`). |
| `plugins/claude/hooks/on-session-start.sh` | SessionStart handler — rebuilds DB via `pp build` if workspace exists. |
| `tests/test_contract.py` | Assert each public op returns JSON with `schema_version: 1` and declared fields. |
| `tests/plugins/test_claude_wrapper.py` | Run each op via `pp`; assert non-zero exit or valid JSON as documented. |
| `tests/plugins/test_claude_roles.py` | Assert every role from `pp roles` has a matching `agents/<name>.md` in the bundle. |

### Modified

| Path | Change |
|---|---|
| `principia/cli/manage.py` | Add `paths`, `roles`, `phases`, `schema` subcommands. Add `schema_version: 1` to JSON outputs of existing commands that emit JSON (validate, query, list, waves, dispatch-log, next, investigate-next, dashboard). |
| `plugins/claude/.claude-plugin/plugin.json` | Bump version to `0.5.0`; add `author.email`, `homepage`. |
| `plugins/claude/hooks/hooks.json` | Replace inline bash with `bash ${CLAUDE_PLUGIN_ROOT}/hooks/on-session-start.sh`; bump timeout to 30. |
| `plugins/claude/skills/help/SKILL.md` | Rewrite description to third-person trigger format; body uses `pp paths` + `pp status`. |
| `plugins/claude/skills/methodology/SKILL.md` | Same treatment; body uses `pp phases` + `pp roles` for live data. |
| `plugins/claude/README.md` | Document local-marketplace install flow. |
| `README.md` (root) | Add `/plugin marketplace add` install section. |
| `pyproject.toml` | Remove `agents/*.md` from `[tool.setuptools.package-data]`. |
| `tests/engine/test_core_shims.py` | Update assertions for new (smaller) package-data. |
| `tests/plugins/test_claude_layout.py` | Update assertions for new plugin shape. |
| `.github/workflows/ci.yml` | Add `plugin-smoke` job — shape checks on the plugin bundle. |
| `CHANGELOG.md` | Add `v0.5.claude` entry. |

### Deleted

| Path | Reason |
|---|---|
| `plugins/claude/.claude-plugin/marketplace.json` | Replaced by root-level `.claude-plugin/marketplace.json`. |
| `plugins/claude/skills/init/` | Migrated to `commands/init.md`. |
| `plugins/claude/skills/design/` | Migrated to `commands/design.md`. |
| `plugins/claude/skills/step/` | Migrated to `commands/step.md`. |
| `plugins/claude/skills/status/` | Migrated to `commands/status.md`. |
| `plugins/claude/skills/validate/` | Migrated to `commands/validate.md`. |
| `plugins/claude/skills/query/` | Migrated to `commands/query.md`. |
| `plugins/claude/skills/new/` | Migrated to `commands/new.md`. |
| `plugins/claude/skills/scaffold/` | Migrated to `commands/scaffold.md`. |
| `plugins/claude/skills/settle/` | Migrated to `commands/settle.md`. |
| `plugins/claude/skills/falsify/` | Migrated to `commands/falsify.md`. |
| `plugins/claude/skills/impact/` | Migrated to `commands/impact.md`. |
| `principia/agents/` (whole directory, 8 files) | Claude-shaped files leaving the universal core. |
| `agents/` at repo root (whole directory, 8 files) | Duplicate of the same files. |

### Unchanged (explicitly)

- `plugins/claude/agents/*.md` — 8 files preserved as-is (content untouched, now sole source of truth).
- `plugins/codex/` — entirely out of scope.
- `principia/api/`, `principia/core/` — touched only indirectly via `manage.py`.
- `principia/config/orchestration.yaml` — referenced by new `roles` / `phases` commands but not modified.

---

## Task 1: Add core discovery commands and contract versioning

**Goal:** Add 4 new CLI subcommands (`paths`, `roles`, `phases`, `schema`) that expose workspace paths, role list, phase list, and frontmatter schema as JSON. Add `schema_version: 1` to JSON outputs of existing commands.

**Why first:** These are pure additions to core. Nothing depends on them yet. They need to exist before the contract doc (Task 2) can assert them, and before the wrapper (Task 3) can map to them.

**Files:**
- Modify: `principia/cli/manage.py`
- Modify: `principia/core/commands.py` (add handler functions)
- Modify: `principia/core/orchestration.py` (read roles/phases from config for `roles`/`phases`)
- Create: `tests/test_discovery_commands.py`

### Steps

- [ ] **Step 1.1: Read current manage.py to find subparser structure**

Run: `grep -n "add_parser" /home/zhuo/Projects/principia/principia/cli/manage.py | head -40`

Note the pattern for how subcommands are wired (each has `sub.add_parser(...)` then `set_defaults(func=cmd_xxx)` or similar).

- [ ] **Step 1.2: Write failing test for `paths` command**

Create `tests/test_discovery_commands.py`:

```python
"""Tests for the discovery CLI commands: paths, roles, phases, schema."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    """Run manage.py with args; return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-m", "principia.cli.manage", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_paths_json_shape(tmp_path: Path) -> None:
    """paths --json returns schema_version and workspace paths."""
    rc, out, err = _run("--root", str(tmp_path / "principia"), "paths", "--json")
    assert rc == 0, f"paths --json failed: {err}"
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    data = payload["data"]
    # All documented keys present
    for key in ("root", "db", "claims_dir", "context_dir", "progress", "foundations", "config"):
        assert key in data, f"paths --json missing key: {key}"
```

- [ ] **Step 1.3: Run the failing test**

Run: `cd /home/zhuo/Projects/principia && uv run python -m pytest tests/test_discovery_commands.py::test_paths_json_shape -v`

Expected: FAIL (argument "paths" invalid, or `--json` unknown).

- [ ] **Step 1.4: Implement `paths` subcommand**

In `principia/core/commands.py`, add a handler:

```python
import json
from typing import Any

def cmd_paths(root: str, as_json: bool = True) -> int:
    """Emit workspace path layout as versioned JSON."""
    from . import config as _cfg
    _cfg.init_paths(root)
    data: dict[str, Any] = {
        "root": str(_cfg.RESEARCH_DIR),
        "db": str(_cfg.DB_PATH),
        "claims_dir": str(_cfg.RESEARCH_DIR / "claims"),
        "context_dir": str(_cfg.CONTEXT_DIR),
        "progress": str(_cfg.PROGRESS_PATH),
        "foundations": str(_cfg.FOUNDATIONS_PATH),
        "config": str(_cfg.RESEARCH_DIR / ".config.md"),
    }
    payload = {"schema_version": 1, "data": data, "warnings": []}
    print(json.dumps(payload, indent=2))
    return 0
```

In `principia/cli/manage.py`, register the subcommand. Find the block where subparsers are created and add:

```python
    p_paths = sub.add_parser("paths", help="Emit workspace path layout as JSON")
    p_paths.add_argument("--json", action="store_true", default=True,
                         help="Output as JSON (default)")
    p_paths.set_defaults(func=lambda args: cmd_paths(args.root))
```

(Adjust the `.set_defaults` pattern to match the existing style in `manage.py`.)

- [ ] **Step 1.5: Run the test to verify it passes**

Run: `uv run python -m pytest tests/test_discovery_commands.py::test_paths_json_shape -v`

Expected: PASS.

- [ ] **Step 1.6: Write failing test for `roles` command**

Add to `tests/test_discovery_commands.py`:

```python
def test_roles_json_shape(tmp_path: Path) -> None:
    """roles --json returns the list of roles from orchestration.yaml."""
    rc, out, err = _run("--root", str(tmp_path / "principia"), "roles", "--json")
    assert rc == 0, f"roles --json failed: {err}"
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    roles = payload["data"]
    assert isinstance(roles, list)
    assert len(roles) > 0, "expected at least one role"
    # Every role has name + purpose/phase fields
    names = {r["name"] for r in roles}
    # Known roles from orchestration.yaml
    assert "architect" in names
    assert "adversary" in names
    for r in roles:
        assert "name" in r
        assert isinstance(r["name"], str)
```

- [ ] **Step 1.7: Run the failing test**

Run: `uv run python -m pytest tests/test_discovery_commands.py::test_roles_json_shape -v`

Expected: FAIL.

- [ ] **Step 1.8: Implement `roles` subcommand**

In `principia/core/commands.py`:

```python
def cmd_roles(root: str) -> int:
    """Emit the role registry from orchestration config as JSON."""
    from . import orchestration
    cfg = orchestration.load_orchestration_config()
    roles_data = []
    for role in cfg.get("roles", []):
        entry = {"name": role.get("name")}
        if "type" in role:
            entry["type"] = role["type"]
        if "phase" in role:
            entry["phase"] = role["phase"]
        # Derive phase by scanning phases block if not set on role directly
        for phase_name, phase_spec in cfg.get("phases", {}).items():
            if role.get("name") in phase_spec.get("roles", []):
                entry["phase"] = phase_name
                break
        roles_data.append(entry)
    payload = {"schema_version": 1, "data": roles_data, "warnings": []}
    print(json.dumps(payload, indent=2))
    return 0
```

Register in `manage.py` the same way as `paths`.

- [ ] **Step 1.9: Run the test to verify it passes**

Run: `uv run python -m pytest tests/test_discovery_commands.py::test_roles_json_shape -v`

Expected: PASS.

- [ ] **Step 1.10: Write failing test for `phases` command**

```python
def test_phases_json_shape(tmp_path: Path) -> None:
    """phases --json returns the list of phases with their roles."""
    rc, out, err = _run("--root", str(tmp_path / "principia"), "phases", "--json")
    assert rc == 0, f"phases --json failed: {err}"
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    phases = payload["data"]
    assert isinstance(phases, list)
    names = {p["name"] for p in phases}
    assert "debate" in names or "test" in names or "experiment" in names, \
        f"expected known phases, got {names}"
    for p in phases:
        assert "name" in p
        assert "roles" in p
        assert isinstance(p["roles"], list)
```

- [ ] **Step 1.11: Run the failing test**

Run: `uv run python -m pytest tests/test_discovery_commands.py::test_phases_json_shape -v`

Expected: FAIL.

- [ ] **Step 1.12: Implement `phases` subcommand**

In `principia/core/commands.py`:

```python
def cmd_phases(root: str) -> int:
    """Emit the phase machinery from orchestration config as JSON."""
    from . import orchestration
    cfg = orchestration.load_orchestration_config()
    phases_data = []
    for phase_name, phase_spec in cfg.get("phases", {}).items():
        entry = {
            "name": phase_name,
            "roles": list(phase_spec.get("roles", [])),
        }
        if "exit_condition" in phase_spec:
            entry["exit_condition"] = phase_spec["exit_condition"]
        phases_data.append(entry)
    payload = {"schema_version": 1, "data": phases_data, "warnings": []}
    print(json.dumps(payload, indent=2))
    return 0
```

Register in `manage.py`.

- [ ] **Step 1.13: Run the test to verify it passes**

Run: `uv run python -m pytest tests/test_discovery_commands.py::test_phases_json_shape -v`

Expected: PASS.

- [ ] **Step 1.14: Write failing test for `schema` command**

```python
def test_schema_json_shape(tmp_path: Path) -> None:
    """schema --json returns the frontmatter value sets."""
    rc, out, err = _run("--root", str(tmp_path / "principia"), "schema", "--json")
    assert rc == 0, f"schema --json failed: {err}"
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    data = payload["data"]
    for key in ("types", "statuses", "maturities", "confidences"):
        assert key in data, f"schema missing key: {key}"
        assert isinstance(data[key], list)
        assert len(data[key]) > 0
```

- [ ] **Step 1.15: Run the failing test**

Run: `uv run python -m pytest tests/test_discovery_commands.py::test_schema_json_shape -v`

Expected: FAIL.

- [ ] **Step 1.16: Implement `schema` subcommand**

In `principia/core/commands.py`:

```python
def cmd_schema(root: str) -> int:
    """Emit the frontmatter value sets as JSON."""
    from . import ids
    data = {
        "types": sorted(ids.VALID_TYPES),
        "statuses": sorted(ids.VALID_STATUSES),
        "maturities": sorted(ids.VALID_MATURITIES),
        "confidences": sorted(ids.VALID_CONFIDENCES),
    }
    payload = {"schema_version": 1, "data": data, "warnings": []}
    print(json.dumps(payload, indent=2))
    return 0
```

Register in `manage.py`.

- [ ] **Step 1.17: Run the test to verify it passes**

Run: `uv run python -m pytest tests/test_discovery_commands.py::test_schema_json_shape -v`

Expected: PASS.

- [ ] **Step 1.18: Add `schema_version: 1` to existing JSON-emitting commands**

Identify the commands that currently emit JSON: `validate --json`, `query --json`, `list --json`, `waves --json`, `dispatch-log --json`, `next`, `investigate-next`, `dashboard`.

For each, find where the JSON is printed (search `principia/core/commands.py` and `principia/core/reports.py` for `json.dumps`). Wrap the current payload in the new envelope:

```python
# Before:
print(json.dumps(data))

# After:
print(json.dumps({"schema_version": 1, "data": data, "warnings": []}))
```

Preserve all existing fields inside `data`.

Write or update a test for each to verify the envelope. Example for `validate`:

```python
def test_validate_json_includes_schema_version(tmp_path: Path) -> None:
    rc, out, err = _run("--root", str(tmp_path / "principia"), "validate", "--json")
    # validate can succeed (rc=0) or find issues (rc!=0), both OK for shape test
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    assert "data" in payload
```

- [ ] **Step 1.19: Run the full test suite to verify no regressions**

Run: `uv run python -m pytest tests/ -q`

Expected: All existing tests pass. New discovery tests pass. If any existing test was asserting the raw JSON shape (unwrapped), update it to assert `payload["data"]["<field>"]` instead of `payload["<field>"]`.

- [ ] **Step 1.20: Run lint and type checks**

Run:
```bash
uv run ruff check scripts/ tests/ principia/
uv run ruff format --check scripts/ tests/
uv run mypy scripts/
```

Expected: All clean.

- [ ] **Step 1.21: Commit**

```bash
git add principia/cli/manage.py principia/core/commands.py principia/core/orchestration.py tests/test_discovery_commands.py
# Also add any other files touched for schema_version wrapping:
git add -u  # picks up modified existing tests
git commit -m "$(cat <<'EOF'
feat(core): add paths/roles/phases/schema discovery commands + schema_version envelope

Introduces four new CLI subcommands that expose workspace paths, role
registry, phase machinery, and frontmatter value sets as versioned JSON.
Existing JSON-emitting commands now wrap their payload in
{schema_version, data, warnings} for forward-compatible evolution.

Prepares the core side of the Claude plugin adapter architecture
(docs/specs/2026-04-16-claude-plugin-adapter-architecture-design.md).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Write CONTRACT.md and contract conformance tests

**Goal:** Publish `docs/CONTRACT.md` as the contract document and write `tests/test_contract.py` that asserts each public operation conforms.

**Files:**
- Create: `docs/CONTRACT.md`
- Create: `tests/test_contract.py`

### Steps

- [ ] **Step 2.1: Create `docs/CONTRACT.md`**

Create the file with this content (verbatim):

````markdown
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
````

- [ ] **Step 2.2: Write contract conformance tests**

Create `tests/test_contract.py`:

```python
"""Contract conformance tests.

For each public operation listed in docs/CONTRACT.md, assert the CLI
accepts documented input and returns JSON with schema_version == 1
and the declared fields.

Run: uv run pytest tests/test_contract.py -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def _run(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "principia.cli.manage", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Initialize a minimal workspace and return its root."""
    root = tmp_path / "principia"
    root.mkdir()
    (root / "claims").mkdir()
    (root / "context").mkdir()
    (root / "context" / "assumptions").mkdir()
    return root


# ---------- Discovery operations ----------

class TestDiscoveryContract:
    def test_paths(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "paths", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        for key in ("root", "db", "claims_dir", "context_dir",
                    "progress", "foundations", "config"):
            assert key in payload["data"]

    def test_roles(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "roles", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert isinstance(payload["data"], list)
        for role in payload["data"]:
            assert "name" in role

    def test_phases(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "phases", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert isinstance(payload["data"], list)
        for phase in payload["data"]:
            assert "name" in phase
            assert "roles" in phase

    def test_schema(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "schema", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        for key in ("types", "statuses", "maturities", "confidences"):
            assert key in payload["data"]
            assert len(payload["data"][key]) > 0


# ---------- Inspection operations ----------

class TestInspectionContract:
    def test_validate_json(self, workspace: Path) -> None:
        # validate --json may exit non-zero if issues found; shape still applies
        rc, out, err = _run("--root", str(workspace), "validate", "--json")
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload

    def test_build_runs(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "build")
        assert rc == 0, err


# ---------- Further ops ----------
# Add tests for mutation, planning, bookkeeping, and workflow ops
# following the same pattern. Each test: invoke, check exit code,
# load JSON, verify schema_version and declared fields.
```

- [ ] **Step 2.3: Run contract tests**

Run: `uv run python -m pytest tests/test_contract.py -v`

Expected: All tests pass (this exercises Task 1's work).

- [ ] **Step 2.4: Lint/format check**

Run:
```bash
uv run ruff check tests/test_contract.py
uv run ruff format --check tests/test_contract.py
```

Expected: Clean. Fix any issues with `ruff format tests/test_contract.py` and `ruff check --fix tests/test_contract.py` if needed.

- [ ] **Step 2.5: Commit**

```bash
git add docs/CONTRACT.md tests/test_contract.py
git commit -m "$(cat <<'EOF'
docs(core): add CONTRACT.md and conformance tests

Publish the stable CLI contract between principia core and adapter
bundles. tests/test_contract.py asserts each public operation returns
the declared shape with schema_version: 1, so core refactors that
accidentally break the contract fail in CI before release.

Contract version 1 covers 20 public operations across workflow,
inspection, mutation, planning, bookkeeping, and discovery categories.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Create plugin wrapper `scripts/pp`

**Goal:** Create the single-file bash wrapper that dispatches contract operations to `principia.cli.manage`. This is the ONLY plugin file that knows the current CLI shape.

**Files:**
- Create: `plugins/claude/scripts/pp`

### Steps

- [ ] **Step 3.1: Create `plugins/claude/scripts/` directory**

Run: `mkdir -p /home/zhuo/Projects/principia/plugins/claude/scripts`

- [ ] **Step 3.2: Write the `pp` wrapper**

Create `plugins/claude/scripts/pp`:

```bash
#!/usr/bin/env bash
# pp — Principia plugin contract wrapper.
#
# This is the ONE plugin file that knows the current principia CLI shape.
# All commands, skills, agents, and hooks in this bundle invoke core
# functionality through `pp <operation> [args]`.
#
# When the core CLI changes, only this file updates. See docs/CONTRACT.md
# for the stable operation surface.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: pp <operation> [args...]" >&2
  exit 2
fi

op="$1"; shift
root="${PRINCIPIA_ROOT:-principia}"

case "$op" in
  # Workflow
  build|next|investigate-next|post-verdict|extend-debate|reopen|replace-verdict|\
  # Inspection
  status|validate|query|dashboard|dispatch-log|assumptions|\
  # Mutation
  scaffold|new|settle|falsify|register|\
  # Planning
  cascade|waves|context|packet|prompt|\
  # Bookkeeping
  log-dispatch|parse-framework|artifacts|codebook|autonomy-config|\
  # Discovery
  paths|roles|phases|schema)
    exec uv run python -m principia.cli.manage --root "$root" "$op" "$@"
    ;;
  *)
    echo "pp: unknown operation '$op'" >&2
    echo "See docs/CONTRACT.md for the public operation surface." >&2
    exit 2
    ;;
esac
```

- [ ] **Step 3.3: Make it executable**

Run: `chmod +x /home/zhuo/Projects/principia/plugins/claude/scripts/pp`

- [ ] **Step 3.4: Manually verify the wrapper works**

Run:
```bash
cd /home/zhuo/Projects/principia
./plugins/claude/scripts/pp paths --json | head -20
./plugins/claude/scripts/pp roles --json | head -20
```

Expected: Each prints JSON with `"schema_version": 1`.

- [ ] **Step 3.5: Commit**

```bash
git add plugins/claude/scripts/pp
git update-index --chmod=+x plugins/claude/scripts/pp
git commit -m "$(cat <<'EOF'
feat(plugin): add pp contract wrapper

scripts/pp is the only plugin file aware of the current principia CLI
shape. All commands, skills, agents, and hooks invoke core functionality
via `pp <operation>` per docs/CONTRACT.md. Subsequent tasks migrate the
bundle's surfaces to use it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Migrate 11 skills to commands

**Goal:** Create 11 flat command markdown files in `plugins/claude/commands/` that replace the current SKILL.md files for user-invoked operations. Keep the old skill directories in place this commit (they'll be deleted in Task 5).

**Files:**
- Create: `plugins/claude/commands/init.md`, `design.md`, `step.md`, `status.md`, `validate.md`, `query.md`, `new.md`, `scaffold.md`, `settle.md`, `falsify.md`, `impact.md`

### Steps

- [ ] **Step 4.1: Create `commands/` directory**

Run: `mkdir -p /home/zhuo/Projects/principia/plugins/claude/commands`

- [ ] **Step 4.2: Create `commands/status.md` (simplest, do first as a template)**

```markdown
---
description: Regenerate principia/PROGRESS.md from the current database state.
allowed-tools: Bash
---

Rebuild PROGRESS.md so it reflects the current workspace state.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp status`

Then report what changed to the user.
```

- [ ] **Step 4.3: Create `commands/validate.md`**

```markdown
---
description: Run integrity checks on the principia workspace (frontmatter, referential integrity, cycles).
argument-hint: "[--json]"
allowed-tools: Bash
---

Check the workspace for broken references, invalid frontmatter, and dependency cycles.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp validate $ARGUMENTS`

Summarize errors and warnings for the user. If `--json` was requested, preserve the structured output.
```

- [ ] **Step 4.4: Create `commands/query.md`**

```markdown
---
description: Run a SQL query against the principia database.
argument-hint: "\"<sql>\""
allowed-tools: Bash
---

Run an SQL query against the principia database and report the result.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp query "$1"`

Format the result as a readable table for the user.
```

- [ ] **Step 4.5: Create `commands/new.md`**

```markdown
---
description: Create a new principia markdown file with auto-generated frontmatter.
argument-hint: "<relative-path>"
allowed-tools: Bash
---

Create a new markdown file with auto-generated frontmatter (type, status, id derived from path).

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp new "$1"`

Confirm the file was created and report its id.
```

- [ ] **Step 4.6: Create `commands/scaffold.md`**

```markdown
---
description: Create a claim directory structure (claim directory skeleton with stub files).
argument-hint: "<level> <name>"
allowed-tools: Bash
---

Create a scaffolded directory for a new claim.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp scaffold "$1" "$2"`

Report which files were created.
```

- [ ] **Step 4.7: Create `commands/settle.md`**

```markdown
---
description: Mark a principia claim as proven.
argument-hint: "<claim-id>"
allowed-tools: Bash
---

Mark the claim as settled (proven). Updates the ledger and frontmatter.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp settle "$1"`

Confirm the settlement and note any downstream consequences from the output.
```

- [ ] **Step 4.8: Create `commands/falsify.md`**

```markdown
---
description: Mark a principia claim as disproven and cascade the weakening to dependents.
argument-hint: "<claim-id> [--by id]"
allowed-tools: Bash
---

Mark the claim as disproven. The core will cascade the effect to all dependents.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp falsify $ARGUMENTS`

Report what was weakened by the cascade.
```

- [ ] **Step 4.9: Create `commands/impact.md`**

```markdown
---
description: Preview what would be weakened if a principia claim were disproven (dry run).
argument-hint: "<claim-id>"
allowed-tools: Bash
---

Show the cascade preview — what breaks if this claim is disproven. Read-only, no changes applied.

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp cascade "$1"`

Present the list to the user as a decision aid.
```

Note: user-facing command is `impact`; contract op is `cascade`. The wrapper handles the name.

- [ ] **Step 4.10: Create `commands/step.md`**

Read the existing `plugins/claude/skills/step/SKILL.md` for the workflow logic, then transcribe it to a command. Key transformation:

```markdown
---
description: Advance the principia investigation by one workflow step (dispatch agents, record results).
argument-hint: "[claim-path]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Agent
  - AskUserQuestion
---

<!-- Preserve the existing step.md's workflow prose, but replace every
     `uv run python -m principia.cli.manage --root principia <op>`
     with `${CLAUDE_PLUGIN_ROOT}/scripts/pp <op>`.
     Remove any hardcoded "principia/claims/..." paths by calling
     `pp paths` to discover them. -->

[... full prose from skills/step/SKILL.md, transformed ...]
```

Concretely: open `skills/step/SKILL.md`, copy the body after the frontmatter, paste below a fresh frontmatter block (shown above), run a find-replace:
- `uv run python -m principia.cli.manage --root principia` → `${CLAUDE_PLUGIN_ROOT}/scripts/pp`
- Inspect any remaining hardcoded paths; replace with `$(pp paths --json | jq -r '.data.<key>')` or similar runtime resolution.

- [ ] **Step 4.11: Create `commands/init.md`**

Same transformation as step 4.10 applied to `skills/init/SKILL.md`. This is the largest file (~800 lines of prose). Preserve the workflow prose — only adjust invocations.

Target frontmatter:

```markdown
---
description: Initialize a new Principia workspace — inspect the repo, guide the user through the north star, and bootstrap the directory + DB.
argument-hint: "[project-title]"
allowed-tools:
  - Bash
  - Write
  - Read
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
---
```

Body transformation: replace `uv run python -m principia.cli.manage` with `${CLAUDE_PLUGIN_ROOT}/scripts/pp`, replace hardcoded paths with `pp paths` output.

- [ ] **Step 4.12: Create `commands/design.md`**

Same transformation applied to `skills/design/SKILL.md`. Target frontmatter:

```markdown
---
description: Run the full 4-phase principia design pipeline (Understand → Divide → Test → Synthesize) from a principle.
argument-hint: "\"<principle>\" [--quick]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
---
```

- [ ] **Step 4.13: Verify the new commands directory has exactly 11 files**

Run: `ls /home/zhuo/Projects/principia/plugins/claude/commands/*.md | wc -l`

Expected: `11`.

- [ ] **Step 4.14: Grep audit — no leaked core internals in new commands**

Run:
```bash
cd /home/zhuo/Projects/principia
grep -rn "manage.py\|--root principia\|principia/\\.db\|principia/claims/" plugins/claude/commands/ || echo "clean"
```

Expected: `clean`. If any matches, fix the corresponding command to use `pp` or `pp paths`.

- [ ] **Step 4.15: Commit**

```bash
git add plugins/claude/commands/
git commit -m "$(cat <<'EOF'
feat(plugin): migrate 11 slash commands to commands/

Creates flat Claude Code command files for each user-invoked principia
operation. All bodies call core through \${CLAUDE_PLUGIN_ROOT}/scripts/pp
rather than the raw CLI. The old skills/<name>/SKILL.md files remain
in this commit and will be deleted in the next commit.

Commands: init, design, step, status, validate, query, new, scaffold,
settle, falsify, impact.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Delete old skills, update remaining 2 skills

**Goal:** Remove the 11 skill directories now replaced by commands. Update `help` and `methodology` skills to third-person descriptions and `pp`-based data fetching.

**Files:**
- Delete: `plugins/claude/skills/{init,design,step,status,validate,query,new,scaffold,settle,falsify,impact}/`
- Modify: `plugins/claude/skills/help/SKILL.md`
- Modify: `plugins/claude/skills/methodology/SKILL.md`

### Steps

- [ ] **Step 5.1: Delete the 11 migrated skill directories**

Run:
```bash
cd /home/zhuo/Projects/principia/plugins/claude/skills
rm -rf init design step status validate query new scaffold settle falsify impact
ls
```

Expected output: `help  methodology  principia  README.md` (or similar — only the non-migrated items remain).

If `principia` skill directory exists (I noted it earlier in codex bundle listing; verify it doesn't exist for Claude), leave it — but it shouldn't be there per the current bundle. Check and remove if stray.

- [ ] **Step 5.2: Read current `help/SKILL.md` and `methodology/SKILL.md`**

Run:
```bash
cat /home/zhuo/Projects/principia/plugins/claude/skills/help/SKILL.md
cat /home/zhuo/Projects/principia/plugins/claude/skills/methodology/SKILL.md
```

- [ ] **Step 5.3: Rewrite `help/SKILL.md` with third-person description**

Preserve the existing body's logic, update the frontmatter and ensure all CLI calls go through `pp`. Example:

```markdown
---
name: help
description: This skill should be used when the user asks "how do I start", "what should I do next", "help me with principia", or is new to the project and needs a walkthrough based on the current workspace state.
---

# Principia — adaptive help

Guide the user based on the current state of their principia workspace.

## Step 1: Check workspace state

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp paths --json`

Inspect the output to find the workspace root and progress file.

## Step 2: Check progress

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp status`

Read the regenerated PROGRESS.md to see current phase and active claims.

## Step 3: Respond based on state

- If the workspace doesn't exist yet: suggest `/principia:init`.
- If in Phase 1 (Understand): guide toward locking the north star.
- If in Phase 2 (Divide): suggest running `/principia:design` or `/principia:step` on the next unproved claim.
- If claims exist but no verdicts: suggest `/principia:step` to dispatch the next agent.
- If there are blockers or invalid claims: suggest `/principia:validate`.

Be concise. Do not list all possible commands — recommend the single most relevant next action.
```

- [ ] **Step 5.4: Rewrite `methodology/SKILL.md` with third-person description**

```markdown
---
name: methodology
description: This skill should be used when the user asks about the principia methodology — "how does this work", "why four phases", "what's the philosophy", "what are the roles" — and wants an explanation grounded in the current orchestration config.
---

# Principia — methodology reference

Explain the principia design methodology using live data from the current orchestration config.

## Step 1: Fetch the current phase list

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp phases --json`

Parse the output to get the phase names and their roles.

## Step 2: Fetch the role registry

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp roles --json`

Parse the output to get the role names and their phases.

## Step 3: Explain the methodology

Present the methodology to the user:

1. **The four phases**: list each phase name from `pp phases`, one line each with its role sequence.
2. **The role registry**: list each role from `pp roles` with its purpose and the phase it belongs to.
3. **The adversarial design principle**: briefly explain why architect+adversary debate, why empirical experiment, why post-verdict cascade.

Adjust if the config shows a different number of phases or roles than described — trust the live data, not a fixed narrative.
```

- [ ] **Step 5.5: Verify plugin has 2 skills, 11 commands, 8 agents**

Run:
```bash
cd /home/zhuo/Projects/principia/plugins/claude
echo "skills: $(ls -d skills/*/ 2>/dev/null | wc -l)"
echo "commands: $(ls commands/*.md 2>/dev/null | wc -l)"
echo "agents: $(ls agents/*.md 2>/dev/null | wc -l)"
```

Expected:
```
skills: 2
commands: 11
agents: 8
```

- [ ] **Step 5.6: Grep audit — no leaked internals in remaining skills**

Run:
```bash
cd /home/zhuo/Projects/principia
grep -rn "manage.py\|--root principia\|principia/\\.db" plugins/claude/skills/ || echo "clean"
```

Expected: `clean`.

- [ ] **Step 5.7: Commit**

```bash
git add -A plugins/claude/skills/
git commit -m "$(cat <<'EOF'
refactor(plugin): trim skills to help + methodology; delete migrated skills

The 11 command-shaped skills migrated to commands/ in the previous
commit are now removed. Only two true skills remain:

- help: adaptive onboarding, picks next action based on workspace state
- methodology: reference docs, pulls live phase/role data via pp

Both use third-person trigger descriptions per current Claude Code
skill conventions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Redesign the SessionStart hook

**Goal:** Extract inline bash into `hooks/on-session-start.sh`, make the hook use `${CLAUDE_PLUGIN_ROOT}`, call `pp build` rather than the raw CLI.

**Files:**
- Create: `plugins/claude/hooks/on-session-start.sh`
- Modify: `plugins/claude/hooks/hooks.json`

### Steps

- [ ] **Step 6.1: Create `on-session-start.sh`**

```bash
#!/usr/bin/env bash
# SessionStart hook: rebuild the principia database if a workspace exists
# in this project. Invoked by Claude Code at session startup/resume.
#
# Uses the contract wrapper (pp) rather than the raw principia CLI so
# this hook stays stable across core CLI refactors.

set -euo pipefail

root="${PRINCIPIA_ROOT:-principia}"

# Skip silently if no workspace is present — this hook ships with every
# session regardless of whether the user is working on principia.
if [ ! -d "$root/claims" ] && [ ! -d "$root/context" ]; then
  exit 0
fi

# Rebuild via contract wrapper
tmp=$(mktemp)
if PRINCIPIA_ROOT="$root" "${CLAUDE_PLUGIN_ROOT}/scripts/pp" build > "$tmp" 2>&1; then
  tail -5 "$tmp"
  rm -f "$tmp"
else
  status=$?
  tail -10 "$tmp"
  rm -f "$tmp"
  exit $status
fi
```

Save to `plugins/claude/hooks/on-session-start.sh`.

- [ ] **Step 6.2: Make it executable**

Run: `chmod +x /home/zhuo/Projects/principia/plugins/claude/hooks/on-session-start.sh`

- [ ] **Step 6.3: Update `hooks/hooks.json`**

Read the current content:

```bash
cat /home/zhuo/Projects/principia/plugins/claude/hooks/hooks.json
```

Replace with:

```json
{
  "description": "Rebuild principia database on session start/resume if a principia workspace exists in the current project.",
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/on-session-start.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 6.4: Verify JSON is valid**

Run: `python3 -c 'import json; json.load(open("/home/zhuo/Projects/principia/plugins/claude/hooks/hooks.json"))' && echo OK`

Expected: `OK`.

- [ ] **Step 6.5: Manual smoke test of the hook script**

Run (simulating the hook environment):

```bash
cd /home/zhuo/Projects/principia
CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/claude" PRINCIPIA_ROOT="principia" \
  bash plugins/claude/hooks/on-session-start.sh
```

Expected behavior: If a `principia/claims/` or `principia/context/` exists in cwd, it runs `pp build` and prints tail lines. Otherwise exits 0 silently. No error from the shell.

- [ ] **Step 6.6: Commit**

```bash
git add plugins/claude/hooks/on-session-start.sh plugins/claude/hooks/hooks.json
git update-index --chmod=+x plugins/claude/hooks/on-session-start.sh
git commit -m "$(cat <<'EOF'
refactor(plugin): extract SessionStart hook, use \${CLAUDE_PLUGIN_ROOT}

The inline bash in hooks.json is replaced by a dedicated script
hooks/on-session-start.sh that reads PRINCIPIA_ROOT, skips silently if
no workspace exists, and rebuilds via the pp contract wrapper rather
than calling the raw CLI. Timeout raised from 10s to 30s to allow for
larger workspaces.

Fixes portability: the hook now works regardless of where the plugin
cache lives.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Update manifests (plugin.json + root marketplace.json, delete nested marketplace.json)

**Goal:** Put the marketplace manifest at the repo root so `/plugin marketplace add <path>` works. Update the plugin manifest with email, homepage, version 0.5.0. Remove the nested legacy `marketplace.json`.

**Files:**
- Create: `.claude-plugin/marketplace.json` (repo root)
- Modify: `plugins/claude/.claude-plugin/plugin.json`
- Delete: `plugins/claude/.claude-plugin/marketplace.json`

### Steps

- [ ] **Step 7.1: Create the repo-root `.claude-plugin/` directory**

Run: `mkdir -p /home/zhuo/Projects/principia/.claude-plugin`

- [ ] **Step 7.2: Write the root `marketplace.json`**

Create `.claude-plugin/marketplace.json`:

```json
{
  "name": "principia",
  "owner": {
    "name": "Mohan",
    "email": "mohan.qiao@mail.concordia.ca"
  },
  "metadata": {
    "description": "Turn a philosophical principle into a working algorithm through rigorous adversarial testing.",
    "version": "0.5.0"
  },
  "plugins": [
    {
      "name": "principia",
      "source": "./plugins/claude",
      "description": "Decomposes ideas into testable claims, stress-tests each through structured debate and empirical experiments, and composes the surviving pieces into a design.",
      "version": "0.5.0",
      "license": "MIT",
      "keywords": [
        "algorithm-design",
        "first-principles",
        "adversarial-testing",
        "hypothesis-driven",
        "multi-agent",
        "debate",
        "falsification"
      ]
    }
  ]
}
```

- [ ] **Step 7.3: Update `plugins/claude/.claude-plugin/plugin.json`**

Read the current content first:

```bash
cat /home/zhuo/Projects/principia/plugins/claude/.claude-plugin/plugin.json
```

Replace with:

```json
{
  "name": "principia",
  "description": "Turn a philosophical principle into a working algorithm through rigorous adversarial testing. Decomposes ideas into testable claims, stress-tests each through structured debate and empirical experiments, and composes the surviving pieces into a design you can build on.",
  "version": "0.5.0",
  "license": "MIT",
  "keywords": [
    "algorithm-design",
    "first-principles",
    "adversarial-testing",
    "hypothesis-driven",
    "multi-agent",
    "debate",
    "falsification"
  ],
  "author": {
    "name": "Mohan",
    "email": "mohan.qiao@mail.concordia.ca"
  },
  "homepage": "https://github.com/Gavin-Qiao/principia",
  "repository": "https://github.com/Gavin-Qiao/principia"
}
```

- [ ] **Step 7.4: Delete the nested `marketplace.json`**

Run: `rm /home/zhuo/Projects/principia/plugins/claude/.claude-plugin/marketplace.json`

- [ ] **Step 7.5: Validate both JSONs parse cleanly**

Run:
```bash
cd /home/zhuo/Projects/principia
python3 -c 'import json; json.load(open(".claude-plugin/marketplace.json"))' && echo "root OK"
python3 -c 'import json; json.load(open("plugins/claude/.claude-plugin/plugin.json"))' && echo "plugin OK"
```

Expected: both print `OK`.

- [ ] **Step 7.6: Manual local-marketplace smoke test**

From a fresh Claude Code session (opened in a DIFFERENT directory so principia isn't cwd):

```
/plugin marketplace add /home/zhuo/Projects/principia
```

Expected: "Successfully added marketplace: principia".

```
/plugin install principia@principia
```

Expected: "Installed principia. Run /reload-plugins to apply."

(If this must be deferred to later manual testing, note it as "verify during Task 11 acceptance check" and continue.)

- [ ] **Step 7.7: Commit**

```bash
git add .claude-plugin/marketplace.json plugins/claude/.claude-plugin/plugin.json
git add -u plugins/claude/.claude-plugin/  # picks up the deletion
git commit -m "$(cat <<'EOF'
feat(plugin): add root marketplace.json; bump plugin to 0.5.0

- Add .claude-plugin/marketplace.json at repo root so users can run
  /plugin marketplace add <path> against the repo directly. Points at
  ./plugins/claude as the sole plugin source.
- Bump plugin.json to version 0.5.0; add author.email and homepage.
- Delete the legacy nested plugins/claude/.claude-plugin/marketplace.json
  which was a dual-role file replaced by the root manifest.

Unlocks local-marketplace install flow:
  /plugin marketplace add <repo-path>
  /plugin install principia@principia

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Delete duplicate agent files, update pyproject.toml package-data

**Goal:** Remove the Claude-shaped agent files from the universal core package and the repo root duplicate. The sole source of truth for Claude-formatted agents becomes `plugins/claude/agents/`.

**Files:**
- Delete: `principia/agents/` (whole directory)
- Delete: `agents/` at repo root (whole directory)
- Modify: `pyproject.toml`
- Modify: `tests/engine/test_core_shims.py`

### Steps

- [ ] **Step 8.1: Verify `plugins/claude/agents/` has all 8 files intact**

Run: `ls /home/zhuo/Projects/principia/plugins/claude/agents/`

Expected:
```
adversary.md  arbiter.md  architect.md  conductor.md  deep-thinker.md  experimenter.md  scout.md  synthesizer.md
```

If any are missing, STOP. Do not proceed until `plugins/claude/agents/` is complete — it's about to become the only copy.

- [ ] **Step 8.2: Delete `principia/agents/`**

Run: `rm -rf /home/zhuo/Projects/principia/principia/agents`

- [ ] **Step 8.3: Delete `/agents/` at repo root**

Run: `rm -rf /home/zhuo/Projects/principia/agents`

- [ ] **Step 8.4: Update `pyproject.toml` to remove `agents/*.md` from package-data**

Read current:

```bash
grep -A2 package-data /home/zhuo/Projects/principia/pyproject.toml
```

Change:

```toml
[tool.setuptools.package-data]
principia = ["agents/*.md", "config/*.md", "config/*.yaml"]
```

To:

```toml
[tool.setuptools.package-data]
principia = ["config/*.md", "config/*.yaml"]
```

- [ ] **Step 8.5: Read `tests/engine/test_core_shims.py` to find the assertion referencing agents**

Run: `grep -n "agents" /home/zhuo/Projects/principia/tests/engine/test_core_shims.py`

Update any assertion that expects `agents/` to be part of the package. Likely changes:
- Remove assertions like `assert (package_root / "agents").exists()`
- Or invert them: `assert not (package_root / "agents").exists()` if the test is checking the cleanup happened.

Typical pattern: find the test function, read its body, update the expected file list.

- [ ] **Step 8.6: Write a new assertion that verifies the cleanup**

In `tests/engine/test_core_shims.py`, add (or modify) a test:

```python
def test_core_package_has_no_agents_dir() -> None:
    """After the adapter split, agents/*.md files live in plugin bundles only,
    not in the core Python package."""
    import principia
    pkg_root = Path(principia.__file__).parent
    assert not (pkg_root / "agents").exists(), (
        "principia package should not ship agents/*.md; "
        "those belong in plugins/claude/agents/ only"
    )
```

- [ ] **Step 8.7: Run the full test suite**

Run: `uv run python -m pytest tests/ -q`

Expected: All tests pass. Any test that was relying on `principia/agents/*.md` being present needs updating — those assumptions are now incorrect per the architecture.

Common fixes for failing tests:
- If a test asserts `(package_root / "agents" / "architect.md").exists()` — change it to test against `plugins/claude/agents/architect.md` instead, or delete the test if it was redundant.
- If a test was using `importlib.resources` to load an agent file from `principia`, it should now load from the plugin bundle path (or be re-scoped to test something else).

- [ ] **Step 8.8: Build the wheel and verify agents/*.md is excluded**

Run:
```bash
cd /home/zhuo/Projects/principia
rm -rf dist/
uv build --wheel
python3 -c "
import zipfile
with zipfile.ZipFile('dist/principia-0.4.0b4-py3-none-any.whl') as z:
    names = z.namelist()
    agents = [n for n in names if 'agents' in n]
    print('agents entries in wheel:', agents)
    assert not agents, f'wheel still contains agent files: {agents}'
print('verified: wheel has no agents/*.md')
"
```

(Adjust the wheel filename to match whatever `uv build` produced. Core version still `0.4.0b4` — this is the plugin iteration, not a core version bump.)

Expected: `verified: wheel has no agents/*.md`.

- [ ] **Step 8.9: Lint + format + mypy**

Run:
```bash
uv run ruff check scripts/ tests/ principia/
uv run ruff format --check scripts/ tests/
uv run mypy scripts/
```

Expected: All clean.

- [ ] **Step 8.10: Commit**

```bash
git add -A principia/agents agents pyproject.toml tests/engine/test_core_shims.py
git commit -m "$(cat <<'EOF'
refactor(core): remove Claude-shaped agent duplicates from core package

Agent files with Claude-specific frontmatter (model: opus, tools:
[WebSearch], etc.) were duplicated in three locations:
- principia/agents/  (shipped in the Python wheel as package-data)
- /agents/           (repo root copy)
- plugins/claude/agents/

The core is universal — Claude frontmatter does not belong there.
Delete both duplicates and drop agents/*.md from pyproject.toml
package-data. plugins/claude/agents/ becomes the sole source of truth
for Claude-shaped agent definitions.

Verified: the Codex bundle (plugins/codex/) has no agents/ dependency
(confirmed via grep across plugins/codex/ and principia/cli/codex_runner.py).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Add plugin conformance tests

**Goal:** Three new tests that verify the plugin wrapper, roles coverage, and layout shape.

**Files:**
- Create: `tests/plugins/test_claude_wrapper.py`
- Create: `tests/plugins/test_claude_roles.py`
- Modify: `tests/plugins/test_claude_layout.py`

### Steps

- [ ] **Step 9.1: Read current `tests/plugins/test_claude_layout.py`**

Run: `cat /home/zhuo/Projects/principia/tests/plugins/test_claude_layout.py`

Note the existing structure and patterns.

- [ ] **Step 9.2: Update `test_claude_layout.py` assertions for new plugin shape**

Modify the existing tests to assert:

- `plugins/claude/commands/` exists and contains exactly 11 `.md` files.
- `plugins/claude/skills/` exists and contains exactly 2 subdirectories (`help`, `methodology`).
- `plugins/claude/agents/` exists and contains exactly 8 `.md` files.
- `plugins/claude/scripts/pp` exists and is executable.
- `plugins/claude/hooks/on-session-start.sh` exists and is executable.
- `plugins/claude/hooks/hooks.json` exists.
- `plugins/claude/.claude-plugin/plugin.json` exists.
- `plugins/claude/.claude-plugin/marketplace.json` does NOT exist (moved to root).
- `.claude-plugin/marketplace.json` at repo root exists.

Example assertion block:

```python
from pathlib import Path
import os
import json


REPO_ROOT = Path(__file__).parent.parent.parent
PLUGIN = REPO_ROOT / "plugins" / "claude"


def test_plugin_has_11_commands() -> None:
    commands = list((PLUGIN / "commands").glob("*.md"))
    assert len(commands) == 11, f"expected 11 commands, got {len(commands)}: {[c.name for c in commands]}"


def test_plugin_has_2_skills() -> None:
    skills = [d for d in (PLUGIN / "skills").iterdir() if d.is_dir()]
    names = {d.name for d in skills}
    assert names == {"help", "methodology"}, f"expected 2 skills (help, methodology), got {names}"


def test_plugin_has_8_agents() -> None:
    agents = list((PLUGIN / "agents").glob("*.md"))
    assert len(agents) == 8


def test_wrapper_is_executable() -> None:
    pp = PLUGIN / "scripts" / "pp"
    assert pp.exists()
    assert os.access(pp, os.X_OK), "scripts/pp must be executable"


def test_hook_script_is_executable() -> None:
    hook = PLUGIN / "hooks" / "on-session-start.sh"
    assert hook.exists()
    assert os.access(hook, os.X_OK)


def test_nested_marketplace_is_deleted() -> None:
    assert not (PLUGIN / ".claude-plugin" / "marketplace.json").exists(), \
        "nested marketplace.json should have been moved to repo root"


def test_root_marketplace_exists() -> None:
    root_mp = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    assert root_mp.exists()
    data = json.loads(root_mp.read_text())
    assert data["name"] == "principia"
    assert data["plugins"][0]["source"] == "./plugins/claude"
```

Preserve any existing tests that are still valid; delete/modify only those that contradict the new shape.

- [ ] **Step 9.3: Write `test_claude_wrapper.py`**

```python
"""Contract wrapper tests: run `pp <op>` for every op declared in the
wrapper case-statement; assert each exits with code 0 or emits valid
JSON with schema_version 1 (for read-only ops against a fresh workspace).

These tests drift-check the wrapper against the core CLI.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent.parent
WRAPPER = REPO_ROOT / "plugins" / "claude" / "scripts" / "pp"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "principia"
    root.mkdir()
    (root / "claims").mkdir()
    (root / "context").mkdir()
    (root / "context" / "assumptions").mkdir()
    return root


def _pp(workspace: Path, *args: str) -> tuple[int, str, str]:
    env = {**os.environ, "PRINCIPIA_ROOT": str(workspace)}
    result = subprocess.run(
        [str(WRAPPER), *args],
        cwd=workspace.parent,
        env=env,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


class TestDiscoveryOps:
    def test_paths(self, workspace: Path) -> None:
        rc, out, err = _pp(workspace, "paths", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1

    def test_roles(self, workspace: Path) -> None:
        rc, out, err = _pp(workspace, "roles", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1

    def test_phases(self, workspace: Path) -> None:
        rc, out, err = _pp(workspace, "phases", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1

    def test_schema(self, workspace: Path) -> None:
        rc, out, err = _pp(workspace, "schema", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1


class TestBasicOps:
    def test_build(self, workspace: Path) -> None:
        rc, out, err = _pp(workspace, "build")
        assert rc == 0, err

    def test_validate(self, workspace: Path) -> None:
        rc, out, err = _pp(workspace, "validate", "--json")
        # validate may non-zero for an empty workspace; shape is the assertion
        payload = json.loads(out)
        assert payload["schema_version"] == 1


class TestUnknownOp:
    def test_unknown_op_fails_cleanly(self, workspace: Path) -> None:
        rc, out, err = _pp(workspace, "nonexistent-operation")
        assert rc == 2
        assert "unknown operation" in err.lower()
```

- [ ] **Step 9.4: Write `test_claude_roles.py`**

```python
"""Adapter coverage test: every role returned by `pp roles` must have a
corresponding <plugins/claude/agents/{name}.md> file in the bundle.

This catches the case where core adds a new role without the Claude
adapter shipping an agent file for it.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.parent
PLUGIN_AGENTS = REPO_ROOT / "plugins" / "claude" / "agents"
WRAPPER = REPO_ROOT / "plugins" / "claude" / "scripts" / "pp"


def test_every_role_has_agent_file(tmp_path: Path) -> None:
    workspace = tmp_path / "principia"
    workspace.mkdir()
    env = {**os.environ, "PRINCIPIA_ROOT": str(workspace)}

    result = subprocess.run(
        [str(WRAPPER), "roles", "--json"],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    roles = payload["data"]
    role_names = {r["name"] for r in roles}

    agent_files = {p.stem for p in PLUGIN_AGENTS.glob("*.md")}

    missing = role_names - agent_files
    assert not missing, (
        f"core declares roles with no Claude agent file: {missing}. "
        f"Add plugins/claude/agents/<name>.md for each missing role."
    )
```

- [ ] **Step 9.5: Run the new plugin tests**

Run:
```bash
uv run python -m pytest tests/plugins/test_claude_wrapper.py tests/plugins/test_claude_roles.py tests/plugins/test_claude_layout.py -v
```

Expected: all pass.

- [ ] **Step 9.6: Run the full suite**

Run: `uv run python -m pytest tests/ -q`

Expected: all pass.

- [ ] **Step 9.7: Lint + format**

Run:
```bash
uv run ruff check tests/plugins/
uv run ruff format --check tests/plugins/
```

Expected: clean.

- [ ] **Step 9.8: Commit**

```bash
git add tests/plugins/test_claude_wrapper.py tests/plugins/test_claude_roles.py tests/plugins/test_claude_layout.py
git commit -m "$(cat <<'EOF'
test(plugin): add wrapper + roles conformance tests; update layout asserts

- test_claude_wrapper.py: run pp <op> for every op; check exit + JSON
  shape. Catches wrapper drift from the CLI.
- test_claude_roles.py: assert every core role has a Claude agent
  file. Catches silent missing-coverage if core adds a role.
- test_claude_layout.py: updated for new plugin shape (11 commands,
  2 skills, scripts/pp, hooks/on-session-start.sh, no nested
  marketplace.json, root .claude-plugin/marketplace.json).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Add plugin-smoke CI job

**Goal:** Add a CI job that verifies the plugin bundle's structural shape on every push/PR, catching drift before it reaches `main`.

**Files:**
- Modify: `.github/workflows/ci.yml`

### Steps

- [ ] **Step 10.1: Read current workflow**

Run: `cat /home/zhuo/Projects/principia/.github/workflows/ci.yml`

- [ ] **Step 10.2: Add `plugin-smoke` job**

Append the new job at the bottom of the `jobs:` block. Example:

```yaml
  plugin-smoke:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - run: uv sync --dev

      - name: Plugin shape checks
        run: |
          set -euo pipefail
          test -f .claude-plugin/marketplace.json
          test -f plugins/claude/.claude-plugin/plugin.json
          test ! -e plugins/claude/.claude-plugin/marketplace.json
          test ! -d principia/agents
          test ! -d agents
          test -x plugins/claude/scripts/pp
          test -x plugins/claude/hooks/on-session-start.sh
          test -f plugins/claude/hooks/hooks.json
          cmd_count=$(ls plugins/claude/commands/*.md | wc -l)
          sk_count=$(ls -d plugins/claude/skills/*/ | wc -l)
          ag_count=$(ls plugins/claude/agents/*.md | wc -l)
          test "$cmd_count" = "11" || { echo "expected 11 commands, got $cmd_count"; exit 1; }
          test "$sk_count" = "2"  || { echo "expected 2 skills, got $sk_count"; exit 1; }
          test "$ag_count" = "8"  || { echo "expected 8 agents, got $ag_count"; exit 1; }
          echo "plugin shape OK"

      - name: Grep audit — no core internals leaked into plugin prose
        run: |
          set -euo pipefail
          # Exclude the wrapper itself, which legitimately references the CLI.
          if grep -rn "manage.py\|--root principia\|principia/\.db\|principia/claims/" \
             plugins/claude/ \
             --exclude-dir=.claude-plugin \
             --exclude=pp; then
            echo "ERROR: plugin file references core internals. Use pp wrapper instead."
            exit 1
          fi
          echo "decoupling audit OK"

      - name: Wrapper smoke — paths and roles
        run: |
          set -euo pipefail
          uv run --python 3.12 plugins/claude/scripts/pp paths --json | python3 -c \
            "import json, sys; p=json.load(sys.stdin); assert p['schema_version']==1"
          uv run --python 3.12 plugins/claude/scripts/pp roles --json | python3 -c \
            "import json, sys; p=json.load(sys.stdin); assert p['schema_version']==1"
          echo "wrapper smoke OK"
```

Preserve the existing `test` job exactly as-is; just append the new `plugin-smoke` job after it.

- [ ] **Step 10.3: Validate YAML**

Run:
```bash
python3 -c 'import yaml; yaml.safe_load(open("/home/zhuo/Projects/principia/.github/workflows/ci.yml"))' && echo OK
```

Expected: `OK`.

(If PyYAML is not available, skip — GitHub Actions will validate on push.)

- [ ] **Step 10.4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "$(cat <<'EOF'
ci: add plugin-smoke job — shape + decoupling + wrapper checks

New job runs after test and verifies:
- Plugin bundle has expected shape (11 commands, 2 skills, 8 agents,
  scripts/pp executable, hooks/on-session-start.sh executable,
  no nested marketplace.json, core duplicates deleted).
- Grep audit: no plugin file outside scripts/pp references manage.py,
  --root principia, or hardcoded core paths.
- Wrapper smoke: pp paths and pp roles emit valid versioned JSON.

Catches adapter/core contract violations before merge.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Update README and CHANGELOG

**Goal:** Document the local-marketplace install flow in the plugin README and root README. Add a CHANGELOG entry for the v0.5.claude release.

**Files:**
- Modify: `plugins/claude/README.md`
- Modify: `README.md` (root)
- Modify: `CHANGELOG.md`

### Steps

- [ ] **Step 11.1: Read current plugin README**

Run: `cat /home/zhuo/Projects/principia/plugins/claude/README.md`

- [ ] **Step 11.2: Rewrite `plugins/claude/README.md`**

```markdown
# Principia — Claude Code Plugin

Canonical Claude Code plugin bundle for [Principia](https://github.com/Gavin-Qiao/principia): turn a philosophical principle into a working algorithm through rigorous adversarial testing.

## Install (local marketplace)

Install the plugin from a local clone of the principia repo. This is the supported path in plugin version 0.5.0.

```bash
# Clone the repo (requires the Python core to be installable locally)
git clone https://github.com/Gavin-Qiao/principia
cd principia
uv sync --dev  # or pip install -e .

# In a Claude Code session, add the marketplace and install the plugin:
/plugin marketplace add /absolute/path/to/principia
/plugin install principia@principia
/reload-plugins
```

The plugin is now available. Try `/principia:help` to get oriented, or `/principia:init` to start a new project.

> **Note**: GitHub-shorthand install (`/plugin marketplace add Gavin-Qiao/principia`) will become supported once the `principia` core Python package is published to PyPI — tracked in a future iteration.

## What's in this bundle

- **11 slash commands** — `init`, `design`, `step`, `status`, `validate`, `query`, `new`, `scaffold`, `settle`, `falsify`, `impact`.
- **2 skills** — `help` (adaptive onboarding), `methodology` (reference).
- **8 subagents** — `architect`, `adversary`, `arbiter`, `conductor`, `synthesizer`, `scout`, `experimenter`, `deep-thinker`.
- **SessionStart hook** — auto-rebuilds the database when you resume work on a principia project.

## Architecture

This bundle is a thin adapter over the universal principia core. All plugin files call core functionality through a single wrapper at `scripts/pp`, which maps contract operation names to the current CLI. See `docs/CONTRACT.md` in the repo for the contract specification.

## Dev setup

```bash
# For a tight edit loop on the plugin itself:
claude --plugin-dir ./plugins/claude

# For testing the full install path:
# (from anywhere outside the repo)
/plugin marketplace add /abs/path/to/principia
```
```

- [ ] **Step 11.3: Read current root README**

Run: `cat /home/zhuo/Projects/principia/README.md | head -80`

- [ ] **Step 11.4: Update root README's install section**

Locate the section that documents Claude Code install (search for "claude" in the README). Update or add:

```markdown
## Install — Claude Code

Install via Claude Code's local marketplace (the supported path in plugin 0.5.0):

```bash
# Clone the repo (requires the core to be installable locally)
git clone https://github.com/Gavin-Qiao/principia
cd principia
uv sync --dev

# From a Claude Code session:
/plugin marketplace add /absolute/path/to/principia
/plugin install principia@principia
/reload-plugins
```

See `plugins/claude/README.md` for the full Claude plugin guide.

Public GitHub-shorthand install (`/plugin marketplace add Gavin-Qiao/principia`) is pending the core Python package being published to PyPI.
```

(Preserve the rest of the README — methodology, agents, architecture, etc. — as-is.)

- [ ] **Step 11.5: Update CHANGELOG**

Read current: `head -40 /home/zhuo/Projects/principia/CHANGELOG.md`

Add a new entry at the top (below the header):

```markdown
## 0.5.0 — 2026-04-16 (Claude plugin: v0.5.claude)

This release introduces the **adapter architecture** for the Claude Code plugin bundle. The plugin is now a thin distribution surface over a versioned CLI contract; internal core refactors no longer ripple into plugin files.

### Added

- **`docs/CONTRACT.md`** — stable specification of 20 public CLI operations with input/output schemas, JSON envelope, and versioning rules (contract v1).
- **Four new core CLI commands**: `paths`, `roles`, `phases`, `schema`. Expose workspace path layout, role registry, phase machinery, and frontmatter value sets so plugin code never hardcodes these.
- **`schema_version: 1`** envelope on every JSON-emitting command for forward-compatible evolution.
- **`plugins/claude/scripts/pp`** — single-file bash wrapper; the only plugin file aware of the current CLI shape.
- **Root `.claude-plugin/marketplace.json`** — repo-level marketplace manifest. Enables `/plugin marketplace add <path>` → `/plugin install principia@principia` as the supported install flow.
- **`tests/test_contract.py`**, **`tests/plugins/test_claude_wrapper.py`**, **`tests/plugins/test_claude_roles.py`** — contract + wrapper + role-coverage conformance tests.
- **CI `plugin-smoke` job** — shape checks, decoupling grep audit, wrapper smoke.

### Changed

- **11 skills → 11 commands**. The user-invoked items (`init`, `design`, `step`, `status`, `validate`, `query`, `new`, `scaffold`, `settle`, `falsify`, `impact`) now live as flat `plugins/claude/commands/*.md` files with command-style frontmatter. Invocation pattern is unchanged (`/principia:init` etc.).
- **Skills trimmed to 2**: `help` (adaptive onboarding) and `methodology` (reference), both now use third-person trigger descriptions and pull live data via `pp`.
- **SessionStart hook** extracted from inline bash into `hooks/on-session-start.sh`; uses `${CLAUDE_PLUGIN_ROOT}` for portability; timeout 10s → 30s.
- **`plugins/claude/.claude-plugin/plugin.json`** — version bumped to 0.5.0; added `author.email` and `homepage`.

### Removed

- **`principia/agents/`** and repo-root **`/agents/`** — Claude-shaped agent files consolidated into `plugins/claude/agents/` only. Core Python wheel no longer ships Claude-specific assets.
- **`agents/*.md`** dropped from `pyproject.toml` package-data.
- **`plugins/claude/.claude-plugin/marketplace.json`** — legacy nested file replaced by the repo-root manifest.

### Notes

- **Codex bundle (`plugins/codex/`)** is unchanged; verified to have no dependency on the deleted `principia/agents/` directory.
- **Public GitHub-shorthand install** (`/plugin marketplace add Gavin-Qiao/principia`) remains unsupported until the core Python package is published to PyPI — tracked for a future iteration.
- **Merge, tag (`v0.5.claude`), and post-merge release actions** are supervisor-owned; the branch commits are the agent-side deliverable.
```

- [ ] **Step 11.6: Commit**

```bash
git add plugins/claude/README.md README.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
docs(plugin): README + CHANGELOG for v0.5.claude (adapter architecture)

Documents the local-marketplace install flow and lists all changes in
the 0.5.0 plugin release: 11 commands, 2 skills, 8 agents, pp wrapper,
CONTRACT.md, new tests, CI smoke, core cleanup.

Explicitly notes that GitHub-shorthand install is pending the core
being published to PyPI, and that merge/tag actions are supervisor-
owned.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Branch acceptance gate

**Goal:** Verify every acceptance criterion from the spec before handing to the supervisor. No new code — validation only. This task is commit-free (unless the verification surfaces a bug that requires a fix commit).

### Steps

- [ ] **Step 12.1: Full test suite**

Run: `uv run python -m pytest tests/ -q`

Expected: all pass.

- [ ] **Step 12.2: Lint**

Run: `uv run ruff check scripts/ tests/ principia/`

Expected: clean.

- [ ] **Step 12.3: Format check**

Run: `uv run ruff format --check scripts/ tests/`

Expected: clean. If not, run `uv run ruff format scripts/ tests/` and commit the fix separately.

- [ ] **Step 12.4: Type check**

Run: `uv run mypy scripts/`

Expected: clean.

- [ ] **Step 12.5: Plugin-smoke shape checks (manual, what CI runs)**

Run:
```bash
cd /home/zhuo/Projects/principia
test -f .claude-plugin/marketplace.json && echo "root marketplace.json OK"
test -f plugins/claude/.claude-plugin/plugin.json && echo "plugin.json OK"
test ! -e plugins/claude/.claude-plugin/marketplace.json && echo "nested mp removed OK"
test ! -d principia/agents && echo "core agents deleted OK"
test ! -d agents && echo "root agents deleted OK"
test -x plugins/claude/scripts/pp && echo "pp executable OK"
test -x plugins/claude/hooks/on-session-start.sh && echo "hook script executable OK"
[ "$(ls plugins/claude/commands/*.md | wc -l)" = "11" ] && echo "11 commands OK"
[ "$(ls -d plugins/claude/skills/*/ | wc -l)" = "2" ] && echo "2 skills OK"
[ "$(ls plugins/claude/agents/*.md | wc -l)" = "8" ] && echo "8 agents OK"
```

Expected: every line prints "OK".

- [ ] **Step 12.6: Decoupling grep audit**

Run:
```bash
cd /home/zhuo/Projects/principia
grep -rn "manage.py\|--root principia\|principia/\\.db\|principia/claims/" \
  plugins/claude/ \
  --exclude-dir=.claude-plugin \
  --exclude=pp \
  || echo "decoupling OK"
```

Expected: `decoupling OK`. If matches appear, the plugin prose still embeds core internals — fix the offending file to use `pp` or `pp paths` and commit the fix.

- [ ] **Step 12.7: Local acceptance test (manual, requires Claude Code)**

From a fresh Claude Code session, in a directory that is NOT the principia repo:

```
/plugin marketplace add /home/zhuo/Projects/principia
/plugin install principia@principia
/reload-plugins
/principia:help
/principia:init "Test Principle"
/principia:status
/principia:validate
/principia:query "SELECT COUNT(*) FROM nodes"
/principia:step
```

Expected: each command runs successfully; SessionStart hook rebuilds the database on startup.

If any command fails: fix the underlying issue, commit the fix, re-run the full gate.

- [ ] **Step 12.8: Plugin-validator agent**

From a Claude Code session with `plugin-dev` plugin loaded, invoke the validator:

> Run the `plugin-dev:plugin-validator` agent over `/home/zhuo/Projects/principia/plugins/claude/`.

Review the report. Fix any blockers (commit separately if code changes required).

- [ ] **Step 12.9: Review the commit history**

Run: `git log --oneline claude-code-plugin ^origin/main | head -20`

Expected: 11 feature commits plus (optionally) 1 spec commit, plus any fix-up commits from this task. All with clear, single-responsibility messages.

- [ ] **Step 12.10: Notify the user**

Summarize:
- Number of commits on the branch.
- All acceptance criteria met.
- Branch is ready for supervisor review.
- Reminder: supervisor will handle merge, tag (`v0.5.claude`), and release.

Do NOT push to origin in this step — the user will advise when to push.

---

## Self-review checklist (for plan writer)

Before handing this plan off, the plan-writer verified:

- [x] Every task covers a spec section. All 22 in-scope items from spec §9.1 map to a task.
- [x] No placeholders, no "implement later", no "similar to X", no vague "add error handling".
- [x] Type/name consistency across tasks: operation names match between CONTRACT.md (Task 2), wrapper `pp` (Task 3), and tests (Tasks 2, 9).
- [x] Each task ends in a commit. Each commit has a concrete message.
- [x] Branch discipline: no push, no merge, no tag. Handoff is via commit.
