# Principia Plugin Bundle Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Principia from mixed root and harness plugin surfaces to symmetric `plugins/claude` and `plugins/codex` bundles backed by the shared packaged `principia` runtime.

**Architecture:** Keep `principia/` as the only shared runtime, move Claude and Codex integration files into provider-specific plugin bundles, and route both harnesses through packaged entrypoints under `principia.cli`. Codex becomes the first-class marketplace target at `./plugins/codex`, while Claude moves into `plugins/claude` without changing its high-level feature set.

**Tech Stack:** Python 3.10+, `uv`, setuptools package data, Claude Code plugin manifests, Codex plugin manifests and marketplace metadata, pytest, Ruff, mypy

**Spec:** [docs/specs/2026-04-05-plugin-bundle-migration-design.md](/Users/mohan/Desktop/principia/docs/specs/2026-04-05-plugin-bundle-migration-design.md)

---

## File Structure

### Files to create

| File | Purpose |
|------|---------|
| `plugins/claude/.claude-plugin/plugin.json` | Canonical Claude plugin manifest |
| `plugins/claude/.claude-plugin/marketplace.json` | Canonical Claude marketplace metadata |
| `plugins/claude/README.md` | Claude-specific install and layout guide |
| `plugins/codex/.codex-plugin/plugin.json` | Canonical Codex plugin manifest |
| `plugins/codex/README.md` | Codex-specific install and layout guide |
| `principia/cli/codex_runner.py` | Packaged Codex JSON runner entrypoint |
| `tests/plugins/test_claude_layout.py` | Verifies Claude canonical bundle layout |
| `tests/plugins/test_bundle_runtime_contract.py` | Verifies plugin bundles call packaged runtime entrypoints |

### Files to move or copy into canonical bundle locations

| Current path | Canonical target |
|--------------|------------------|
| `.claude-plugin/plugin.json` | `plugins/claude/.claude-plugin/plugin.json` |
| `.claude-plugin/marketplace.json` | `plugins/claude/.claude-plugin/marketplace.json` |
| `agents/*.md` | `plugins/claude/agents/*.md` |
| `skills/**` | `plugins/claude/skills/**` |
| `hooks/hooks.json` | `plugins/claude/hooks/hooks.json` |
| `harnesses/codex/.codex-plugin/plugin.json` | `plugins/codex/.codex-plugin/plugin.json` |
| `harnesses/codex/skills/**` | `plugins/codex/skills/**` |
| `harnesses/codex/README.md` | `plugins/codex/README.md` |

### Files to modify

| File | Changes |
|------|---------|
| `.agents/plugins/marketplace.json` | Point Codex marketplace entry to `./plugins/codex` |
| `README.md` | Rewrite hero and installation sections around side-by-side Claude/Codex plugin bundles |
| `principia/cli/__init__.py` | Export the new packaged Codex runner if needed |
| `pyproject.toml` | Include any additional package data or script metadata needed by the new runtime path |
| `scripts/manage.py` | Keep root wrapper stable while plugin surfaces move |
| `skills/*.md` or `plugins/claude/skills/*.md` | Change Claude skill invocations from `${CLAUDE_PLUGIN_ROOT}/scripts/manage.py` to packaged entrypoints |
| `hooks/hooks.json` or `plugins/claude/hooks/hooks.json` | Change SessionStart hook to use packaged entrypoint |
| `tests/harnesses/test_codex_layout.py` | Assert canonical plugin path under `plugins/codex` |
| `tests/harnesses/test_codex_engine_runner.py` | Replace repo-harness runner expectations with packaged Codex runner expectations |
| `tests/harnesses/test_readme_installation.py` | Assert new Claude/Codex install wording |
| `tests/cli/test_manage_wrapper.py` | Preserve wrapper behavior while canonical plugin locations move |

### Files to remove after migration completes

| File or directory | Condition for removal |
|-------------------|-----------------------|
| `harnesses/codex/` | Remove after Codex bundle and tests are green |
| root `.claude-plugin/` | Remove after Claude bundle and docs are green |
| root `agents/`, `skills/`, `hooks/` plugin distribution role | Remove only after canonical `plugins/claude` bundle is in use and tests no longer depend on root plugin layout |

---

### Task 1: Create canonical Claude and Codex plugin bundle directories

**Files:**
- Create: `plugins/claude/.claude-plugin/plugin.json`
- Create: `plugins/claude/.claude-plugin/marketplace.json`
- Create: `plugins/claude/README.md`
- Create: `plugins/codex/.codex-plugin/plugin.json`
- Create: `plugins/codex/README.md`
- Create directories: `plugins/claude/agents`, `plugins/claude/skills`, `plugins/claude/hooks`, `plugins/codex/skills`
- Modify: `tests/plugins/test_claude_layout.py`
- Modify: `tests/harnesses/test_codex_layout.py`

- [ ] **Step 1: Write the failing layout tests**

Create `tests/plugins/test_claude_layout.py`:

```python
import json
from pathlib import Path


def test_claude_plugin_manifest_exists_in_canonical_bundle() -> None:
    plugin_path = Path("plugins/claude/.claude-plugin/plugin.json")
    assert plugin_path.exists()

    manifest = json.loads(plugin_path.read_text())
    assert manifest["name"] == "principia"


def test_claude_bundle_contains_agents_skills_and_hooks() -> None:
    assert Path("plugins/claude/agents").is_dir()
    assert Path("plugins/claude/skills").is_dir()
    assert Path("plugins/claude/hooks/hooks.json").exists()
```

Update `tests/harnesses/test_codex_layout.py`:

```python
def test_codex_plugin_manifest_exists() -> None:
    plugin_path = Path("plugins/codex/.codex-plugin/plugin.json")
    assert plugin_path.exists()


def test_marketplace_exposes_principia_plugin() -> None:
    marketplace = json.loads(Path(".agents/plugins/marketplace.json").read_text())
    plugin = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == "principia")
    assert plugin["source"]["path"] == "./plugins/codex"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/plugins/test_claude_layout.py tests/harnesses/test_codex_layout.py -q
```

Expected: FAIL because `plugins/claude/...` and `plugins/codex/...` do not exist yet.

- [ ] **Step 3: Create the canonical plugin bundle directories and seed manifests**

Create the directory tree:

```text
plugins/
├── claude/
│   ├── .claude-plugin/
│   ├── agents/
│   ├── skills/
│   └── hooks/
└── codex/
    ├── .codex-plugin/
    └── skills/
```

Seed `plugins/codex/.codex-plugin/plugin.json` with the current manifest content:

```json
{
  "name": "principia",
  "version": "0.4.0a2",
  "description": "Design algorithms from first principles through adversarial testing.",
  "author": {
    "name": "Principia",
    "email": "opensource@principia.dev",
    "url": "https://github.com/Gavin-Qiao/principia"
  },
  "homepage": "https://github.com/Gavin-Qiao/principia",
  "repository": "https://github.com/Gavin-Qiao/principia",
  "license": "MIT",
  "keywords": ["principia", "research", "codex", "workflow"],
  "skills": "./skills/",
  "interface": {
    "displayName": "Principia",
    "shortDescription": "A Codex plugin for Principia's adversarial algorithm design workflow.",
    "longDescription": "Use Principia in Codex through the canonical `plugins/codex` bundle backed by the shared packaged Principia runtime.",
    "developerName": "Principia",
    "category": "Productivity",
    "capabilities": ["Interactive", "Write"],
    "websiteURL": "https://github.com/Gavin-Qiao/principia",
    "privacyPolicyURL": "https://github.com/Gavin-Qiao/principia/blob/main/README.md",
    "termsOfServiceURL": "https://github.com/Gavin-Qiao/principia/blob/main/LICENSE",
    "defaultPrompt": [
      "Initialize a Principia workspace in this repo.",
      "Advance the next Principia claim lifecycle step.",
      "Generate a Principia status summary for this workspace."
    ],
    "brandColor": "#2563EB"
  }
}
```

Seed `plugins/claude/.claude-plugin/plugin.json` with the current root manifest content:

```json
{
  "name": "principia",
  "description": "Turn a philosophical principle into a working algorithm through rigorous adversarial testing. Decomposes ideas into testable claims, stress-tests each through structured debate and empirical experiments, and composes the surviving pieces into a design you can build on.",
  "version": "0.4.0a2",
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
    "name": "Mohan"
  },
  "repository": "https://github.com/Gavin-Qiao/principia"
}
```

- [ ] **Step 4: Copy the existing provider files into the new bundle roots**

Copy the current Claude and Codex provider assets:

```bash
mkdir -p plugins/claude/agents plugins/claude/skills plugins/claude/hooks
cp -R agents/. plugins/claude/agents/
cp -R skills/. plugins/claude/skills/
cp hooks/hooks.json plugins/claude/hooks/hooks.json

mkdir -p plugins/codex/skills
cp -R harnesses/codex/skills/. plugins/codex/skills/
```

Create minimal provider READMEs:

```markdown
# Principia Claude Plugin

Canonical Claude Code plugin bundle for Principia.
```

```markdown
# Principia Codex Plugin

Canonical Codex plugin bundle for Principia.
```

- [ ] **Step 5: Run the layout tests to verify they pass**

Run:

```bash
uv run python -m pytest tests/plugins/test_claude_layout.py tests/harnesses/test_codex_layout.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins tests/plugins/test_claude_layout.py tests/harnesses/test_codex_layout.py
git commit -m "refactor: create canonical plugin bundle roots"
```

### Task 2: Add the packaged Codex runner entrypoint

**Files:**
- Create: `principia/cli/codex_runner.py`
- Modify: `principia/cli/__init__.py`
- Modify: `tests/harnesses/test_codex_engine_runner.py`
- Test: `tests/harnesses/test_codex_engine_runner.py`

- [ ] **Step 1: Write the failing runner tests against the packaged module**

Update `tests/harnesses/test_codex_engine_runner.py` so the subprocesses target the package module instead of `harnesses/codex/scripts/engine_runner.py`:

```python
result = subprocess.run(
    [
        sys.executable,
        "-m",
        "principia.cli.codex_runner",
        "--root",
        str(tmp_path),
        "build",
    ],
    capture_output=True,
    text=True,
    check=False,
)
```

Add a smoke test:

```python
def test_codex_runner_module_exposes_main() -> None:
    import principia.cli.codex_runner as runner

    assert callable(runner.main)
```

- [ ] **Step 2: Run the Codex runner tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/harnesses/test_codex_engine_runner.py -q
```

Expected: FAIL with `No module named principia.cli.codex_runner`.

- [ ] **Step 3: Create the packaged runner**

Create `principia/cli/codex_runner.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from principia.api.engine import PrincipiaEngine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("command", choices=["build", "dashboard", "validate", "results"])
    args = parser.parse_args()

    engine = PrincipiaEngine(root=args.root)
    payload = getattr(engine, args.command)()
    print(json.dumps(payload, indent=2))
    if args.command == "validate" and not payload.get("valid", True):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

Update `principia/cli/__init__.py` to export the new module cleanly:

```python
__all__ = ["manage", "codex_runner"]
```

- [ ] **Step 4: Run the runner tests to verify they pass**

Run:

```bash
uv run python -m pytest tests/harnesses/test_codex_engine_runner.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add principia/cli/codex_runner.py principia/cli/__init__.py tests/harnesses/test_codex_engine_runner.py
git commit -m "feat: add packaged codex runner"
```

### Task 3: Repoint the Codex bundle to the packaged runtime and canonical marketplace path

**Files:**
- Modify: `.agents/plugins/marketplace.json`
- Modify: `plugins/codex/skills/init/SKILL.md`
- Modify: `plugins/codex/skills/principia/SKILL.md`
- Modify: `plugins/codex/skills/status/SKILL.md`
- Modify: `plugins/codex/skills/validate/SKILL.md`
- Modify: `plugins/codex/skills/results/SKILL.md`
- Modify: `plugins/codex/skills/next-step/SKILL.md`
- Modify: `plugins/codex/skills/falsify/SKILL.md`
- Modify: `plugins/codex/skills/settle/SKILL.md`
- Modify: `plugins/codex/skills/reopen/SKILL.md`
- Modify: `plugins/codex/skills/post-verdict/SKILL.md`
- Modify: `plugins/codex/skills/replace-verdict/SKILL.md`
- Modify: `plugins/codex/README.md`
- Test: `tests/harnesses/test_codex_layout.py`
- Test: `tests/harnesses/test_readme_installation.py`

- [ ] **Step 1: Write the failing marketplace and documentation assertions**

Update `tests/harnesses/test_readme_installation.py`:

```python
def test_codex_harness_readme_points_at_plugins_bundle() -> None:
    text = Path("plugins/codex/README.md").read_text()
    assert "plugins/codex" in text
    assert "uv run python -m principia.cli.codex_runner" in text
```

Update the marketplace expectation if not already done:

```python
assert plugin["source"]["path"] == "./plugins/codex"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/harnesses/test_codex_layout.py tests/harnesses/test_readme_installation.py -q
```

Expected: FAIL because the marketplace still points at `./harnesses/codex` and the new README is not written yet.

- [ ] **Step 3: Update the repo-local marketplace**

Replace the Codex entry in `.agents/plugins/marketplace.json` with:

```json
{
  "name": "principia",
  "source": {
    "source": "local",
    "path": "./plugins/codex"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

- [ ] **Step 4: Rewrite the Codex skills to use the packaged runner**

For JSON runner calls, replace:

```bash
uv run python harnesses/codex/scripts/engine_runner.py --root design dashboard
```

with:

```bash
uv run python -m principia.cli.codex_runner --root design dashboard
```

For state-changing commands, keep:

```bash
uv run python -m principia.cli.manage --root design ...
```

Apply this to every skill under `plugins/codex/skills/`.

- [ ] **Step 5: Rewrite `plugins/codex/README.md`**

Use this structure:

```markdown
# Principia Codex Plugin

Install Principia in Codex from the canonical `plugins/codex` bundle.

## Runtime

This plugin calls the packaged Principia runtime through:

```bash
uv run python -m principia.cli.codex_runner --root design dashboard
```

## Repo-local marketplace

The repository marketplace entry lives at `.agents/plugins/marketplace.json` and points at `./plugins/codex`.
```

- [ ] **Step 6: Run the Codex layout and docs tests to verify they pass**

Run:

```bash
uv run python -m pytest tests/harnesses/test_codex_layout.py tests/harnesses/test_readme_installation.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add .agents/plugins/marketplace.json plugins/codex tests/harnesses/test_codex_layout.py tests/harnesses/test_readme_installation.py
git commit -m "refactor: migrate codex bundle to packaged runtime"
```

### Task 4: Migrate the Claude bundle to packaged entrypoints

**Files:**
- Modify: `plugins/claude/skills/init/SKILL.md`
- Modify: `plugins/claude/skills/design/SKILL.md`
- Modify: `plugins/claude/skills/step/SKILL.md`
- Modify: `plugins/claude/skills/status/SKILL.md`
- Modify: `plugins/claude/skills/help/SKILL.md`
- Modify: `plugins/claude/skills/validate/SKILL.md`
- Modify: `plugins/claude/skills/impact/SKILL.md`
- Modify: `plugins/claude/skills/query/SKILL.md`
- Modify: `plugins/claude/skills/new/SKILL.md`
- Modify: `plugins/claude/skills/scaffold/SKILL.md`
- Modify: `plugins/claude/skills/settle/SKILL.md`
- Modify: `plugins/claude/skills/falsify/SKILL.md`
- Modify: `plugins/claude/hooks/hooks.json`
- Modify: `plugins/claude/README.md`
- Test: `tests/plugins/test_claude_layout.py`

- [ ] **Step 1: Write the failing Claude runtime contract test**

Create `tests/plugins/test_bundle_runtime_contract.py`:

```python
from pathlib import Path


def test_claude_bundle_uses_packaged_manage_entrypoint() -> None:
    init_skill = Path("plugins/claude/skills/init/SKILL.md").read_text()
    assert "uv run python -m principia.cli.manage" in init_skill
    assert "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" not in init_skill
```

- [ ] **Step 2: Run the Claude bundle tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/plugins/test_claude_layout.py tests/plugins/test_bundle_runtime_contract.py -q
```

Expected: FAIL because the copied Claude skills still use `${CLAUDE_PLUGIN_ROOT}/scripts/manage.py`.

- [ ] **Step 3: Replace Claude skill command examples with the packaged manage module**

For every Claude skill command example, replace:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design status
```

with:

```bash
uv run python -m principia.cli.manage --root design status
```

Do the same for `build`, `assumptions`, `investigate-next`, `next`, `context`, `post-verdict`, `autonomy-config`, `validate-paste`, `query`, `scaffold`, `settle`, and `falsify`.

- [ ] **Step 4: Update the Claude SessionStart hook**

Change `plugins/claude/hooks/hooks.json` to:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "if [ -d design/claims ] || [ -d design/context ]; then uv run python -m principia.cli.manage --root design build 2>&1 | tail -5; fi",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 5: Write `plugins/claude/README.md`**

Use this structure:

```markdown
# Principia Claude Plugin

Install Principia in Claude Code from the canonical `plugins/claude` bundle.

## Runtime

The Claude plugin calls the packaged Principia runtime through `uv run python -m principia.cli.manage`.

## Bundle layout

- `.claude-plugin/`
- `agents/`
- `skills/`
- `hooks/`
```

- [ ] **Step 6: Run the Claude bundle tests to verify they pass**

Run:

```bash
uv run python -m pytest tests/plugins/test_claude_layout.py tests/plugins/test_bundle_runtime_contract.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add plugins/claude tests/plugins/test_bundle_runtime_contract.py
git commit -m "refactor: migrate claude bundle to packaged runtime"
```

### Task 5: Rewrite the top-level README around the symmetric plugin bundle model

**Files:**
- Modify: `README.md`
- Modify: `tests/harnesses/test_readme_installation.py`
- Test: `tests/harnesses/test_readme_installation.py`

- [ ] **Step 1: Write the failing README assertions**

Update `tests/harnesses/test_readme_installation.py`:

```python
def test_readme_mentions_canonical_plugin_bundles() -> None:
    text = Path("README.md").read_text()
    assert "plugins/claude" in text
    assert "plugins/codex" in text
    assert "shared packaged runtime" in text
```

- [ ] **Step 2: Run the README test to verify it fails**

Run:

```bash
uv run python -m pytest tests/harnesses/test_readme_installation.py -q
```

Expected: FAIL because the current README still references `harnesses/codex` and root Claude layout.

- [ ] **Step 3: Rewrite the README hero and installation sections**

Use this shape near the top of `README.md`:

```markdown
## Installation

Choose your plugin bundle:

- [Claude plugin](plugins/claude/README.md)
- [Codex plugin](plugins/codex/README.md)

Both plugins share the same packaged Principia runtime under `principia/`.
```

Keep the existing concept explanation and diagrams, but remove repo-layout wording that implies Codex installs from `harnesses/codex`.

- [ ] **Step 4: Run the README tests to verify they pass**

Run:

```bash
uv run python -m pytest tests/harnesses/test_readme_installation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/harnesses/test_readme_installation.py
git commit -m "docs: rewrite readme around canonical plugin bundles"
```

### Task 6: Remove obsolete distribution surfaces and finish the migration cleanup

**Files:**
- Delete: `harnesses/codex/`
- Delete: `.claude-plugin/plugin.json`
- Delete: `.claude-plugin/marketplace.json`
- Delete or relocate: root `agents/`, `skills/`, `hooks/` distribution role
- Modify: `harnesses/claude/README.md`
- Modify: `tests/cli/test_manage_wrapper.py`
- Modify: `tests/test_commands.py`
- Modify: `tests/test_security.py`

- [ ] **Step 1: Write the failing cleanup assertions**

Extend `tests/plugins/test_claude_layout.py`:

```python
def test_legacy_plugin_roots_are_removed() -> None:
    assert not Path("harnesses/codex").exists()
    assert not Path(".claude-plugin").exists()
```

- [ ] **Step 2: Run the cleanup tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/plugins/test_claude_layout.py -q
```

Expected: FAIL because the legacy paths still exist.

- [ ] **Step 3: Remove the obsolete plugin distribution surfaces**

Delete the old paths once the new bundles are green:

```bash
rm -rf harnesses/codex
rm -rf .claude-plugin
```

Update `harnesses/claude/README.md` to say the canonical Claude bundle now lives at `plugins/claude`.

Keep `scripts/manage.py` because tests and direct CLI usage still rely on it as a wrapper.

- [ ] **Step 4: Run the focused tests to verify cleanup passes**

Run:

```bash
uv run python -m pytest tests/plugins/test_claude_layout.py tests/cli/test_manage_wrapper.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove legacy plugin distribution paths"
```

### Task 7: Run the full verification suite and prepare release metadata

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml`
- Modify: `plugins/codex/.codex-plugin/plugin.json`
- Modify: `plugins/claude/.claude-plugin/plugin.json`

- [ ] **Step 1: Add a release note entry for the migration**

Append a new changelog section:

```markdown
## [0.4.0a3] - 2026-04-05

### Changed

- Moved Claude and Codex to canonical plugin bundles under `plugins/`.

### Fixes

- Repointed both harnesses at packaged Principia runtime entrypoints.

### Docs

- Rewrote the README and provider guides around the new plugin bundle structure.
```

- [ ] **Step 2: Bump package and plugin versions**

Update:

```toml
[project]
version = "0.4.0a3"
```

and:

```json
"version": "0.4.0a3"
```

in both provider manifests.

- [ ] **Step 3: Run the full quality gate**

Run:

```bash
uv run ruff check scripts/ tests/ principia
uv run ruff format --check scripts/ tests/ principia
uv run python -m mypy scripts/
uv run python -m pytest tests/ -q
```

Expected:

```text
All checks pass
```

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md pyproject.toml plugins
git commit -m "release: prepare plugin bundle migration alpha" -m "- migrate Claude and Codex to canonical plugin bundles\n- rewire both harnesses to packaged runtime entrypoints\n- rewrite installation docs around the new structure"
```

---

## Self-Review

### Spec coverage

- Symmetric `plugins/claude` and `plugins/codex` bundles: covered by Tasks 1, 3, 4, and 6.
- Shared `principia/` runtime only: covered by Tasks 2, 3, and 4.
- README and harness docs rewrite: covered by Task 5.
- Repo-local Codex marketplace migration: covered by Task 3.
- Verification and release readiness: covered by Task 7.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain in the task steps.
- Every code-changing task contains exact file paths and concrete snippets or commands.

### Type and naming consistency

- Canonical bundle names are consistently `plugins/claude` and `plugins/codex`.
- Packaged entrypoints are consistently `principia.cli.manage` and `principia.cli.codex_runner`.
- Marketplace target is consistently `./plugins/codex`.
