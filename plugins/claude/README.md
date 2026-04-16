# Principia Claude Bundle

Canonical Claude Code plugin bundle for Principia.

Install from `plugins/claude` inside a full Principia checkout. The canonical Claude bundle lives under `plugins/claude` and is allowed to diverge from the old root plugin files where the runtime commands need to differ.

## Local install and smoke test

Use Claude Code's local plugin-dir flow while developing the bundle:

```bash
claude --plugin-dir ./plugins/claude
```

After Claude starts, run `/help` to confirm the namespaced Principia skills are available from the canonical bundle.

The intended first command is `/principia:init`, which now treats `principia/` as the canonical workspace root.

## Runtime

The canonical Claude bundle uses the `pp` wrapper (in `scripts/pp`) for all core CLI calls:

```bash
pp build
pp investigate-next
pp next <claim-path>
```

Use `plugins/claude/skills` for workflow commands, `plugins/claude/agents` for orchestration roles, and `plugins/claude/hooks/hooks.json` for session hooks.

## Bundle metadata

- `.claude-plugin/plugin.json`: Claude plugin manifest
- `.claude-plugin/marketplace.json`: canonical Claude marketplace metadata

The legacy root `.claude-plugin/` distribution has been removed. `plugins/claude` is the canonical Claude bundle.
