# Principia Claude Bundle

Canonical Claude Code plugin bundle for Principia.

Install from `plugins/claude` inside a full Principia checkout. This bundle is the Claude-specific surface and is allowed to diverge from the root plugin files where the canonical runtime commands need to differ.

## Runtime

The canonical Claude bundle uses the packaged Principia CLI instead of the old root plugin wrapper:

```bash
uv run python -m principia.cli.manage --root design build
uv run python -m principia.cli.manage --root design investigate-next
uv run python -m principia.cli.manage --root design next <claim-path>
```

Use `plugins/claude/skills` for workflow commands, `plugins/claude/agents` for orchestration roles, and `plugins/claude/hooks/hooks.json` for session hooks.

## Bundle metadata

- `.claude-plugin/plugin.json`: Claude plugin manifest
- `.claude-plugin/marketplace.json`: canonical Claude marketplace metadata

The root `.claude-plugin/` surface remains in the repository for now, but the canonical Claude bundle lives under `plugins/claude`.
