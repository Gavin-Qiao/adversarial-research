# Principia

Claude Code instructions for Principia. The canonical Claude bundle now lives under `plugins/claude/`; this root doc remains as a repo-level compatibility and orientation file.

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
- **cli/** — package-owned CLI entrypoints
- **core/** — database, orchestration, reporting, validation, and command logic

`scripts/` remains as a compatibility shim layer for legacy entrypoints.

Eight agents in `agents/`, thirteen skills in `skills/`, config in `config/orchestration.yaml`.

## Conventions

- All manage.py invocations use `--root principia` (the working directory created by `/principia:init`)
- Custom YAML parser — no PyYAML dependency. Only supports single-line values and inline lists `[a, b]`
- Atomic file writes via temp file + `os.replace()`
- Path globals live in `config.py`, accessed via `import config as _cfg` then `_cfg.RESEARCH_DIR`
- Node IDs derived from file paths: `claims/claim-1/` -> `h1-`
- Tests import from the module that defines the function (e.g., `from db import build_db`, `from ids import derive_id`)
