---
name: new
description: Create a new design file with auto-generated frontmatter. Use when the system needs to add a new design proposal, result, prompt, or any design document to the log.
user-invocable: false
argument-hint: <relative-path>
allowed-tools:
  - Bash
---

# Create Design File

Create a new markdown file in the design log with auto-generated YAML frontmatter.

## Usage

Run:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design new "$ARGUMENTS"
```

The path should be relative to `design/`. Examples:
- `cycles/cycle-1/unit-1-enrichment/architect/round-1/prompt.md`
- `cycles/cycle-1/unit-1-enrichment/experimenter/results/output.md`
- `context/assumptions/my-assumption.md`

The `.md` extension is appended automatically if missing.

## Auto-generated frontmatter

The tool infers:
- **id**: Abbreviated from the path (e.g., `c1-u1-architect-r1-prompt`)
- **type**: From the role directory (`architect`=claim, `experimenter`=evidence, `arbiter`=verdict, `scout`=reference, prompts=question, `assumptions/`=assumption)
- **status**: `pending`
- **date**: Today
- **depends_on**: `[]` (edit manually to wire dependencies)
- **assumes**: `[]` (edit manually to link assumptions)

## After creation

Tell the user the generated ID and type. Remind them to edit `depends_on` and `assumes` fields to wire the dependency graph.
