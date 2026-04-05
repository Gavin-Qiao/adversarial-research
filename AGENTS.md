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

- `harnesses/claude/` contains the Claude-specific wrapper for the existing Claude Code surface.
- `harnesses/codex/` contains the Codex-native plugin scaffold and workflow adapter.

Eight agents in `agents/`, thirteen skills in `skills/`, config in `config/orchestration.yaml`.

## Conventions

- All `manage.py` invocations use `--root design` (the working directory created by `/principia:init`)
- Custom YAML parser — no PyYAML dependency. Only supports single-line values and inline lists `[a, b]`
- Atomic file writes via temp file + `os.replace()`
- Path globals live in `config.py`, accessed via `import config as _cfg` then `_cfg.RESEARCH_DIR`
- Node IDs derived from file paths: `claims/claim-1/` -> `h1-`
- Tests import from the module that defines the function (e.g., `from db import build_db`, `from ids import derive_id`)
- Keep docs accurate to the current harness layout: README should point users to harness-specific installation instructions, not a single-plugin-only flow.
