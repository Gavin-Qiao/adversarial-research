# Principia

Claude Code plugin that turns a philosophical principle into a working algorithm through adversarial testing.

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

Python modules in `scripts/` (stdlib-only, no pip packages at runtime):

- **manage.py** (~275 lines) — CLI entrypoint with argparse
- **commands.py** (~1,000 lines) — all CLI command handlers
- **db.py** (~525 lines) — SQLite schema, migrations, build, cascade logic
- **reports.py** (~440 lines) — PROGRESS.md, FOUNDATIONS.md, RESULTS.md generators
- **validation.py** (~230 lines) — artifact schemas and integrity checks
- **ids.py** (~85 lines) — constants and node ID derivation
- **config.py** (~100 lines) — shared path globals and utilities
- **orchestration.py** (~1,225 lines) — state machine, context assembly, severity/verdict parsing
- **frontmatter.py** (~155 lines) — dependency-free YAML subset parser

Eight agents in `agents/`, thirteen skills in `skills/`, config in `config/orchestration.yaml`.

## Conventions

- All manage.py invocations use `--root design` (the working directory created by `/principia:init`)
- Custom YAML parser — no PyYAML dependency. Only supports single-line values and inline lists `[a, b]`
- Atomic file writes via temp file + `os.replace()`
- Path globals live in `config.py`, accessed via `import config as _cfg` then `_cfg.RESEARCH_DIR`
- Node IDs derived from file paths: `claims/claim-1/` -> `h1-`
- Tests import from the module that defines the function (e.g., `from db import build_db`, `from ids import derive_id`)
