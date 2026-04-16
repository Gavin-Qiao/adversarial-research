# Claude Plugin Adapter Architecture — Design

**Date:** 2026-04-16
**Branch:** `claude-code-plugin`
**Plugin tag (on merge):** `v0.5.claude`
**Plugin version string:** `0.5.0`
**Status:** Design approved; implementation pending

---

## 1. Context and motivation

Principia today ships as a monorepo containing:

- `principia/` — a Python stdlib-only core (database, orchestration state machine, CLI, reports, validation) used by all downstream consumers.
- `plugins/claude/` — a Claude Code bundle that exposes principia as slash commands, subagents, and hooks.
- `plugins/codex/` — a Codex bundle.

The Claude bundle has two classes of problem:

1. **Taxonomy mismatch with current Claude Code standards.** Thirteen items live under `plugins/claude/skills/<name>/SKILL.md` but are shaped as slash commands (argument-hint, allowed-tools, explicit `/principia:name` invocation). Current Anthropic convention reserves `skills/` for description-matched procedural knowledge and `commands/` for explicit user-invoked workflows.

2. **Adapter/core boundary is blurred.** Claude-specific files (`agents/*.md` with `model: opus`, `color:`, `tools: [WebSearch]`) exist in three places: `principia/agents/`, `/agents/` (repo root), and `plugins/claude/agents/`. The core Python wheel ships them as package-data. The CLI contract between core and plugin is informal — plugin markdown files embed paths, role names, and schema values that leak core internals into the adapter.

The user's architectural principle, explicit in brainstorming:

> **The core may evolve freely. The adapter must not break when it does. Their only coupling is a versioned contract.**

This spec redesigns the Claude plugin as a true adapter over a versioned CLI contract. The Claude bundle becomes a thin distribution surface whose only reference to the core is a wrapper script invoking documented CLI operations. Internal core changes do not ripple into plugin files; contract changes ripple into a single wrapper file plus any prose using the changed operation.

---

## 2. Architecture

Three layers, coupled only through the contract:

```
┌──────────────────────────────────────────────────────────────┐
│  Plugin user (Claude Code session)                            │
│  /principia:init, /principia:step, /principia:design, ...    │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  CLAUDE ADAPTER  (plugins/claude/)                            │
│  commands/*.md  skills/*/SKILL.md  agents/*.md                │
│  hooks/hooks.json + hooks/on-session-start.sh                 │
│  scripts/pp  ←── the ONLY file that knows current CLI shape   │
└──────────────────────────────────────────────────────────────┘
                               │
                     calls contract operations
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  CONTRACT  (docs/CONTRACT.md + versioned JSON in core output) │
│  Stable public operations + IO schemas + semantics + version  │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  UNIVERSAL CORE  (principia/)                                 │
│  api/, cli/, core/  (engine, stdlib-only)                     │
│  config/orchestration.yaml  (universal workflow, role names)  │
│  exposes: build, next, investigate-next, paths, roles,        │
│  phases, schema, validate, query, settle, falsify, ...        │
│  NO agent/command/skill/hook files (deleted this iteration)   │
└──────────────────────────────────────────────────────────────┘
```

**The single rule:** every plugin file calls core *only* via `${CLAUDE_PLUGIN_ROOT}/scripts/pp <operation>`. No plugin file mentions `manage.py`, `--root`, hardcoded paths, role names enumerated as literals, or frontmatter values enumerated as literals. Where role/phase/path/schema knowledge is needed, plugin asks the contract.

**Consequences of this discipline:**

| Core change type | Contract | Wrapper | Plugin files |
|---|---|---|---|
| Internal refactor (module rename, schema change, state machine rewrite) | unchanged | unchanged | unchanged |
| CLI command rename (`manage.py build` → `rebuild`) | unchanged | one-line edit | unchanged |
| Contract-visible change (rename op, new required field, output shape change) | version bump | update | prose using the op updates; plugin version bumps |

The accepted residual coupling: agent files in `plugins/claude/agents/` are keyed on role name (`architect.md`, `adversary.md`, …). If core renames a role, the plugin must rename the corresponding file. A contract test catches this.

---

## 3. Repo layout

Green = added, red = deleted, blue = modified. All paths relative to repo root (`/home/zhuo/Projects/principia/`).

```
.claude-plugin/
└── marketplace.json              ★ NEW — root-level marketplace manifest,
                                    names "principia", plugin source
                                    "./plugins/claude"

principia/                         # UNIVERSAL CORE
├── api/, core/                    (unchanged)
├── cli/
│   ├── manage.py                  ✎ MODIFIED — add paths/roles/phases/
│   │                                schema commands; add --json where
│   │                                missing; emit schema_version in JSON
│   └── codex_runner.py            (unchanged)
├── config/orchestration.yaml      (unchanged — universal)
└── agents/                        ✗ DELETED (Claude-shaped, wrong layer)

agents/                            ✗ DELETED (repo-root duplicate)

docs/
├── CONTRACT.md                    ★ NEW — contract specification
└── specs/
    └── 2026-04-16-claude-plugin-
        adapter-architecture-design.md  ★ NEW — this document

plugins/
├── claude/                        # CLAUDE ADAPTER
│   ├── .claude-plugin/
│   │   ├── plugin.json            ✎ +author.email, +homepage, version 0.5.0
│   │   └── marketplace.json       ✗ DELETED (moved to repo root)
│   ├── README.md                  ✎ document local-marketplace install flow
│   ├── commands/                  ★ NEW — 11 flat .md files
│   │   ├── init.md        design.md     step.md
│   │   ├── status.md      validate.md   query.md
│   │   ├── new.md         scaffold.md   settle.md
│   │   ├── falsify.md     impact.md
│   ├── skills/                    ✎ trimmed from 13 to 2
│   │   ├── help/SKILL.md
│   │   └── methodology/SKILL.md
│   ├── agents/                    (unchanged — 8 files, now sole source
│   │                                of truth for Claude-shaped agents)
│   ├── hooks/
│   │   ├── hooks.json             ✎ uses ${CLAUDE_PLUGIN_ROOT}
│   │   └── on-session-start.sh    ★ NEW — extracted from inline bash
│   └── scripts/
│       └── pp                     ★ NEW — contract wrapper (bash)
└── codex/                         (unchanged — out of scope)

pyproject.toml                     ✎ remove "agents/*.md" from package-data

tests/
├── test_contract.py               ★ NEW — verify CLI conforms to contract
├── engine/test_core_shims.py      ✎ update for smaller package-data
└── plugins/
    ├── test_claude_layout.py      ✎ update for new plugin shape
    ├── test_claude_wrapper.py     ★ NEW — each pp op runs cleanly
    └── test_claude_roles.py       ★ NEW — every role has agent file

.github/workflows/ci.yml           ✎ add plugin-smoke job

CHANGELOG.md                       ✎ 0.5.0 entry for plugin
```

Notable moves:

- Agent files consolidate from three locations to one (`plugins/claude/agents/`). Core wheel stops shipping Claude-shaped assets.
- Plugin's 13 command-shaped skills become 11 flat commands + 2 proper skills.
- `marketplace.json` moves from a nested, dual-role location into the canonical repo-root `.claude-plugin/`.
- `scripts/pp` becomes the only plugin file with knowledge of the CLI shape.

---

## 4. Contract specification

### 4.1 Structure

`docs/CONTRACT.md` declares a stable registry of operations. Each entry has: name, input schema, output schema, semantics. Plugin code references operations only by name via the wrapper.

### 4.2 Operation surface (contract v1)

Twenty operations, grouped by purpose.

| Category | Operations |
|---|---|
| **Workflow** | `build`, `next`, `investigate-next`, `post-verdict`, `extend-debate`, `reopen`, `replace-verdict` |
| **Inspection** | `status`, `validate`, `query`, `dashboard`, `dispatch-log`, `assumptions` |
| **Mutation** | `scaffold`, `new`, `settle`, `falsify`, `register` |
| **Planning** | `cascade`, `waves`, `context`, `packet`, `prompt` |
| **Bookkeeping** | `log-dispatch`, `parse-framework`, `artifacts`, `codebook`, `autonomy-config` |
| **Discovery (NEW)** | `paths`, `roles`, `phases`, `schema` |

### 4.3 New CLI commands added to core

Four new commands eliminate hardcoding in the plugin:

```
manage.py paths  --json   → {db, claims_dir, context_dir, progress,
                             foundations, config, root}
manage.py roles  --json   → [{name, phase, purpose, ...}, ...]
manage.py phases --json   → [{name, roles, exit_condition, ...}, ...]
manage.py schema --json   → {types: [...], statuses: [...],
                             maturities: [...], confidences: [...]}
```

Plus: `--json` added to any existing command that currently only produces human-readable output.

### 4.4 JSON output shape

All JSON responses share this envelope:

```json
{
  "schema_version": 1,
  "data":   { /* operation-specific payload */ },
  "warnings": []
}
```

Compatibility rules:

- **Adding optional fields** → no version bump; adapter ignores unknown fields.
- **Adding required fields / removing or renaming fields / changing semantics** → bump `schema_version`; adapter updates.

### 4.5 Contract versioning

Single integer: `contract_version: 1`.

- **Patch (add op, add optional field, add warning):** no bump, no adapter change.
- **Breaking (rename op, remove op, incompatible output shape):** bump to 2. Plugin ships new major supporting contract v2. Old plugins may coexist until decommissioned.

### 4.6 Wrapper `plugins/claude/scripts/pp`

```bash
#!/usr/bin/env bash
set -euo pipefail
op="$1"; shift
root="${PRINCIPIA_ROOT:-principia}"
case "$op" in
  build|status|validate|query|new|scaffold|settle|falsify|\
  cascade|waves|context|packet|prompt|post-verdict|extend-debate|\
  reopen|replace-verdict|register|log-dispatch|dispatch-log|assumptions|\
  autonomy-config|parse-framework|artifacts|codebook|dashboard|\
  paths|roles|phases|schema|next|investigate-next)
    exec uv run python -m principia.cli.manage --root "$root" "$op" "$@" ;;
  *)
    echo "pp: unknown operation '$op'" >&2
    exit 2 ;;
esac
```

For contract v1 the mapping is mostly 1:1 with the current CLI. Its value is not the mapping today — it's that when core renames an internal command, only this one file changes.

---

## 5. Plugin components

### 5.1 Commands (`plugins/claude/commands/*.md`)

Eleven flat markdown files, each invoking one or more contract ops via `pp`.

| Command | Args | Body pattern |
|---|---|---|
| `init.md` | `[project-title]` | Full init workflow (repo inspection, discussion, north-star lock). Uses `pp paths`, `pp roles`, `pp build` for setup. |
| `design.md` | `"<principle>" [--quick]` | Full 4-phase pipeline; Agent tool + `pp next` / `pp investigate-next` loop. |
| `step.md` | `[claim-path]` | `pp next <path>` or `pp investigate-next`; dispatches agent based on returned `action`. |
| `status.md` | — | `pp status` |
| `validate.md` | `[--json]` | `pp validate "$@"` |
| `query.md` | `"<sql>"` | `pp query "$1"` |
| `new.md` | `<relative-path>` | `pp new "$1"` |
| `scaffold.md` | `<level> <name>` | `pp scaffold "$1" "$2"` |
| `settle.md` | `<claim-id>` | `pp settle "$1"` |
| `falsify.md` | `<claim-id> [--by id]` | `pp falsify "$@"` |
| `impact.md` | `<claim-id>` | `pp cascade "$1"` (user-facing name `impact`, contract op `cascade`). |

Common frontmatter:
- `description`: command-style phrasing, not skill-style.
- `allowed-tools`: minimally scoped (Bash; workflow commands add Agent, AskUserQuestion).
- `argument-hint` where relevant.

Body rule: one short prose intro + `!` bash invocations referencing `${CLAUDE_PLUGIN_ROOT}/scripts/pp`. No `manage.py`, no `--root`, no hardcoded paths.

Example (`commands/status.md`):

```markdown
---
description: Regenerate principia/PROGRESS.md from current database state
allowed-tools: Bash
---

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp status`
```

### 5.2 Skills (`plugins/claude/skills/<name>/SKILL.md`)

Two skills, both proper procedural knowledge:

| Skill | Purpose | Description style |
|---|---|---|
| `help` | Adaptive onboarding — reads current PROGRESS.md via `pp paths`+`pp status` and guides user based on project state | "This skill should be used when the user asks 'how do I start', 'what next', 'help me with principia', or is new to the project and needs a walkthrough based on current state." |
| `methodology` | Reference docs on the 4-phase methodology; pulls live data via `pp phases`+`pp roles` | "This skill should be used when the user asks about the principia methodology, 'how does this work', 'why four phases', or wants to understand the design philosophy and workflow reference." |

Both use third-person descriptions. Both call `pp` for any live data; neither hardcodes role/phase names in prose.

### 5.3 Agents (`plugins/claude/agents/*.md`)

Eight agent files, content unchanged. Now the sole source of truth (the duplicates at `principia/agents/` and `/agents/` are deleted in this iteration).

Frontmatter preserved:
- `model`: explicit per agent (opus for heavy reasoning: architect, adversary, conductor, arbiter, synthesizer, deep-thinker; sonnet for experimenter, scout).
- `color`: distinct per agent.
- `tools`: Claude-specific (`WebSearch`, `WebFetch` for scout and deep-thinker).

System prompts untouched this iteration.

### 5.4 Hooks

`plugins/claude/hooks/hooks.json`:

```json
{
  "description": "Rebuild principia database on session start/resume if workspace exists",
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

`plugins/claude/hooks/on-session-start.sh` (new):

```bash
#!/usr/bin/env bash
set -euo pipefail

root="${PRINCIPIA_ROOT:-principia}"

# Skip silently if no workspace
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

Changes from current: `${CLAUDE_PLUGIN_ROOT}` portability, script extracted to its own file, timeout 10 → 30s, calls contract op not raw CLI.

---

## 6. Manifests

### 6.1 Root `.claude-plugin/marketplace.json` (new)

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

Local install command:

```
/plugin marketplace add /path/to/principia
/plugin install principia@principia
```

### 6.2 `plugins/claude/.claude-plugin/plugin.json` (modified)

```diff
 {
   "name": "principia",
   "description": "...",
-  "version": "0.4.0b4",
+  "version": "0.5.0",
   "license": "MIT",
   "keywords": [...],
   "author": {
-    "name": "Mohan"
+    "name": "Mohan",
+    "email": "mohan.qiao@mail.concordia.ca"
   },
+  "homepage": "https://github.com/Gavin-Qiao/principia",
   "repository": "https://github.com/Gavin-Qiao/principia"
 }
```

### 6.3 `plugins/claude/.claude-plugin/marketplace.json` (deleted)

Legacy dual-role file replaced by the repo-root manifest.

### 6.4 Core `pyproject.toml` version

Untouched this iteration. The core Python package versioning is on a separate schedule managed by another group; the plugin releases independently. The only `pyproject.toml` change is removing `agents/*.md` from `[tool.setuptools.package-data]` (see §9.1 item 6).

---

## 7. Testing strategy

### 7.1 Local acceptance test (primary gate)

Before claiming the branch done, run from a fresh Claude Code session:

```bash
/plugin marketplace add /abs/path/to/principia
/plugin install principia@principia
/reload-plugins

/principia:init "Test Principle"
/principia:status
/principia:validate
/principia:query "SELECT COUNT(*) FROM nodes"
/principia:step
```

Each command must return successfully. SessionStart hook must rebuild the database on startup.

### 7.2 Automated tests

Three new test files, two updates.

| File | Role | Covers |
|---|---|---|
| `tests/test_contract.py` | new | For each operation in `CONTRACT.md`: assert CLI accepts documented input and returns JSON with `schema_version: 1` and declared fields. Catches core breaking the contract. |
| `tests/plugins/test_claude_wrapper.py` | new | Run `pp <op>` for every op in the wrapper's case-statement; assert each exits cleanly and returns valid JSON. Catches wrapper drift. |
| `tests/plugins/test_claude_roles.py` | new | Call `pp roles`, assert every returned role has a matching `agents/<name>.md`. Catches role additions without agent files. |
| `tests/engine/test_core_shims.py` | updated | Assert new (smaller) `pyproject.toml` package-data (no more `agents/*.md`). |
| `tests/plugins/test_claude_layout.py` | updated | Assert new plugin shape: 11 commands, 2 skills, 8 agents, `scripts/pp` present, `hooks/on-session-start.sh` present, nested marketplace.json absent. |

### 7.3 Plugin-validator agent

Before presenting branch for review, run the `plugin-dev:plugin-validator` agent over `plugins/claude/`. Fix any blockers.

### 7.4 CI additions

Add a `plugin-smoke` job to `.github/workflows/ci.yml` downstream of `test`:

```yaml
plugin-smoke:
  needs: test
  runs-on: ubuntu-latest
  steps:
    - checkout
    - uv + Python 3.12 setup
    - uv sync --dev
    - name: Shape checks
      run: |
        test -f .claude-plugin/marketplace.json
        test -f plugins/claude/.claude-plugin/plugin.json
        test ! -e plugins/claude/.claude-plugin/marketplace.json
        test ! -d principia/agents
        test ! -d agents
        test -x plugins/claude/scripts/pp
        test -f plugins/claude/hooks/on-session-start.sh
        [ "$(ls plugins/claude/commands/*.md | wc -l)" = "11" ]
        [ "$(ls -d plugins/claude/skills/*/ | wc -l)" = "2" ]
        [ "$(ls plugins/claude/agents/*.md | wc -l)" = "8" ]
```

Shape-only. Contract and wrapper behaviour is covered by `test_contract.py` and `test_claude_wrapper.py` in the main test job.

---

## 8. Rollout / commit sequence

All work on the `claude-code-plugin` branch. The agent's responsibility ends at "all commits green on branch." A supervisor reviews and handles merge, tag, and post-merge release. The agent does not run `git merge`, `git tag`, or push to `main`.

Ordered commits — each commit green (tests pass, no broken intermediate state):

| # | Commit | What it does | Risk |
|---|---|---|---|
| 1 | **Core additions** | Add `paths`, `roles`, `phases`, `schema` CLI commands. Add `--json` to commands missing it. Add `schema_version: 1` to all JSON outputs. | Additive only. Existing tests pass. |
| 2 | **CONTRACT.md + contract tests** | Write `docs/CONTRACT.md`. Add `tests/test_contract.py` asserting #1 matches declared shapes. | Fails if #1 incomplete — self-checking. |
| 3 | **Plugin wrapper** | Create executable `plugins/claude/scripts/pp`. | New file; nothing depends on it yet. |
| 4 | **Migrate 11 skills → commands** | Create `plugins/claude/commands/*.md` with command-style frontmatter, bodies calling `pp`. Keep old skills in place. | Duplicates present during this commit — acceptable internal state. |
| 5 | **Trim skills** | Delete 11 migrated skill directories; update `help` and `methodology` to third-person descriptions and `pp`-based data fetching. | Plugin clean: 11 commands + 2 skills. |
| 6 | **Hook redesign** | Extract `hooks/on-session-start.sh`; update `hooks/hooks.json` to use `${CLAUDE_PLUGIN_ROOT}`. | SessionStart changes — verify with `/reload-plugins` in a manual test. |
| 7 | **Manifests** | Create root `.claude-plugin/marketplace.json`. Update plugin.json (email, homepage, version 0.5.0). Delete nested marketplace.json. | Local install flow switches path; verify. |
| 8 | **Delete duplicate agents** | Delete `principia/agents/`, `/agents/`. Update `pyproject.toml` package-data. Update `tests/engine/test_core_shims.py`. | Codex unaffected (verified — no dependencies). |
| 9 | **Plugin tests** | Add `tests/plugins/test_claude_wrapper.py`, `test_claude_roles.py`. Update `test_claude_layout.py`. | Self-checking across #3–#8. |
| 10 | **CI update** | Add `plugin-smoke` job to `.github/workflows/ci.yml`. | If shape checks fail, CI fails — catches drift. |
| 11 | **Docs + CHANGELOG** | Update root `README.md` with local-marketplace install flow. Update `plugins/claude/README.md`. Add CHANGELOG entry for 0.5.0 (plugin). | Doc-only. |

### 8.1 Branch acceptance gate

Before handoff to supervisor:

1. `uv run pytest tests/ -q` — all tests pass.
2. `uv run ruff check scripts/ tests/ principia/` — clean.
3. `uv run ruff format --check scripts/ tests/` — clean.
4. `uv run mypy scripts/` — clean.
5. Local acceptance test from §7.1 — works end-to-end.
6. `plugin-dev:plugin-validator` agent run — no blockers.
7. Grep audit: no plugin file **other than `plugins/claude/scripts/pp`** references `manage.py`, `--root principia`, `principia/claims/`, `principia/.db/`, or frontmatter literal values. (The wrapper is the one intentional exception — that's its job.)

### 8.2 Rollback within branch

If a commit regresses, revert that commit and fix forward in a new commit. No `--amend`. No force-push.

### 8.3 Handoff to supervisor

When the gate passes:
- Branch pushed to `origin/claude-code-plugin` with all commits.
- Agent notifies user that branch is ready for review.
- Supervisor handles: review, merge to main, tag `v0.5.claude`, any post-merge verification.

The agent does not execute merge/tag/release actions.

---

## 9. Scope

### 9.1 In scope

**Core:**
1. Four new CLI commands: `paths`, `roles`, `phases`, `schema`.
2. `--json` flag added where missing.
3. `schema_version: 1` in every JSON response.
4. `docs/CONTRACT.md` documenting 20 operations.
5. `tests/test_contract.py`.
6. Delete `principia/agents/`, `/agents/`; trim `pyproject.toml` package-data.
7. Update `tests/engine/test_core_shims.py`.

**Plugin:**
8. `plugins/claude/scripts/pp` wrapper.
9. 11 skills → 11 flat `commands/*.md`.
10. Trim to 2 skills (`help`, `methodology`).
11. Extract hook script, use `${CLAUDE_PLUGIN_ROOT}`.
12. Agent files stay in `plugins/claude/agents/` (content unchanged).
13. Delete `plugins/claude/.claude-plugin/marketplace.json`.

**Distribution:**
14. Create root `.claude-plugin/marketplace.json`.
15. Update `plugin.json` (email, homepage, version 0.5.0).
16. Expand `plugins/claude/README.md` with install flow.
17. Update root `README.md` accordingly.

**Tests & CI:**
18. `tests/plugins/test_claude_wrapper.py`.
19. `tests/plugins/test_claude_roles.py`.
20. Update `tests/plugins/test_claude_layout.py`.
21. Add `plugin-smoke` CI job.

**Docs:**
22. CHANGELOG 0.5.0 entry for plugin.

### 9.2 Out of scope

- `plugins/codex/` modernization — separate iteration.
- Plugin-settings migration (`principia/.config.md` → `.claude/principia.local.md`) — YAGNI.
- MCP server exposure of principia's database — future opportunity.
- Additional hook events (`PreToolUse`, `Stop`, `PreCompact`) beyond the redesigned `SessionStart` — future.
- Publishing the core Python package to PyPI — owned by another group, separate schedule.
- GitHub-shorthand marketplace install (`/plugin marketplace add Gavin-Qiao/principia` from a fresh machine without a clone) — enabled once core is PyPI-installable.
- **Merge to `main`, creation of `v0.5.claude` tag, and any post-merge release actions — supervisor-owned, not agent-owned.**
- End-to-end CI test that spins up Claude Code and installs the plugin — heavier; deferred. Contract + wrapper tests provide most confidence.

### 9.3 Release (supervisor handoff)

When the branch is ready and the supervisor merges:
- Tag: `v0.5.claude` on the merge commit.
- Install command (for local testing against a clone): `/plugin marketplace add <repo-path>` then `/plugin install principia@principia`.
- Public GitHub-shorthand install is pending core PyPI release; this is explicitly noted in CHANGELOG.

---

## 10. Success criteria

Branch is ready for supervisor review when all of the following hold:

1. **Local acceptance test passes.** Fresh Claude Code session in a clone can `/plugin marketplace add /abs/path`, install, and run the core commands end-to-end.
2. **All tests green.** Existing ~450 tests plus the three new test files.
3. **Ruff + mypy + ruff format** clean on `scripts/`, `tests/`, `principia/`.
4. **`plugin-dev:plugin-validator`** returns no blockers.
5. **`docs/CONTRACT.md`** lists all 20 operations with input/output schemas.
6. **Decoupling verified.** Grep audit: no plugin file **other than `plugins/claude/scripts/pp`** references `manage.py`, `--root principia`, `principia/claims/`, `principia/.db/`, or frontmatter literal values. (The wrapper is the intentional exception.)
7. **Codex still works.** Codex tests pass (the duplicate-agent cleanup in commit 8 does not affect Codex, which has no `agents/` dependency).
8. **Local marketplace install works from a fresh clone.** End-to-end verification: clone → `/plugin marketplace add` → install → smoke test.

Merge, tag, and post-merge verification are the supervisor's responsibility and are not part of these criteria.

---

## 11. References

- Current brainstorm conversation (2026-04-16, Opus 4.7 session).
- Anthropic Claude Code docs: https://code.claude.com/docs/en/plugin-marketplaces
- Reference plugin: `/home/zhuo/.claude/plugins/cache/claude-plugins-official/plugin-dev/`
- Prior specs:
  - `docs/specs/2026-04-02-principia-v03-design.md`
  - `docs/specs/2026-04-05-plugin-bundle-migration-design.md`
