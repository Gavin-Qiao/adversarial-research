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
uv run mypy scripts/
```

## Architecture

Three Python scripts in `scripts/` (stdlib-only, no pip packages at runtime):

- **manage.py** (~2,450 lines) — CLI + SQLite database for claims, evidence, verdicts, cascades
- **orchestration.py** (~1,280 lines) — state machine, context assembly, severity/verdict parsing
- **frontmatter.py** (~150 lines) — dependency-free YAML subset parser shared by both

Eight agents in `agents/`, thirteen skills in `skills/`, config in `config/orchestration.yaml`.

## Conventions

- All manage.py invocations use `--root design` (the working directory created by `/principia:init`)
- Custom YAML parser — no PyYAML dependency. Only supports single-line values and inline lists `[a, b]`
- Atomic file writes via temp file + `os.replace()`
- Node IDs derived from file paths: `claims/claim-1/` -> `h1-` (legacy: `cycles/cycle-1/` -> `c1-`)
- Tests import from `manage` (which re-exports from `frontmatter`) or from `frontmatter` directly
