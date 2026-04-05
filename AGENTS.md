# Principia

Shared engine for a multi-harness Principia distribution. The same Python core powers both Claude and Codex wrappers in this repo.

## Commands

```bash
# Tests
uv run python -m pytest tests/ -q

# Lint
uv run ruff check scripts/ tests/

# Format
uv run ruff format scripts/ tests/

# Type check
uv run python -m mypy scripts/
```

## Architecture

Python modules in `principia/` are the shared engine (stdlib-only, no pip packages at runtime):

- **api/** — structured engine API used by harness adapters
- **cli/** — package-owned CLI entrypoint
- **core/** — database, orchestration, reporting, validation, and command logic

`scripts/` remains as a compatibility shim layer for legacy entrypoints.

- `plugins/claude/` contains the canonical Claude Code bundle.
- `plugins/codex/` contains the canonical Codex bundle and workflow adapter.
- `harnesses/claude/` remains as a compatibility note that redirects older Claude-facing docs to `plugins/claude/`.

The legacy `harnesses/codex/` surface and root `.claude-plugin/` distribution have been removed.

Eight agents in `agents/`, thirteen skills in `skills/`, config in `config/orchestration.yaml`.

## Conventions

- All `manage.py` invocations use `--root design` (the working directory created by `/principia:init`)
- Custom YAML parser — no PyYAML dependency. Only supports single-line values and inline lists `[a, b]`
- Atomic file writes via temp file + `os.replace()`
- Path globals live in `config.py`, accessed via `import config as _cfg` then `_cfg.RESEARCH_DIR`
- Node IDs derived from file paths: `claims/claim-1/` -> `h1-`
- Tests import from the module that defines the function (e.g., `from db import build_db`, `from ids import derive_id`)
- Keep docs accurate to the current plugin-bundle layout: README should point users to the canonical `plugins/claude` and `plugins/codex` installation surfaces, not removed legacy harness roots.
