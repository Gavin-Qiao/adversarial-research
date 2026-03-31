---
name: new
description: Create a new research file with auto-generated frontmatter. Use when the user wants to add a new hypothesis, result, prompt, or any research document to the log.
argument-hint: <relative-path>
allowed-tools:
  - Bash
---

# Create Research File

Create a new markdown file in the research log with auto-generated YAML frontmatter.

## Usage

Run:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research new "$ARGUMENTS"
```

The path should be relative to `research/`. Examples:
- `cycles/cycle-1/unit-1-enrichment/thinker/round-1/prompt.md`
- `cycles/cycle-1/unit-1-enrichment/coder/results/output.md`
- `context/assumptions/my-assumption.md`

The `.md` extension is appended automatically if missing.

## Auto-generated frontmatter

The tool infers:
- **id**: Abbreviated from the path (e.g., `c1-u1-thinker-r1-prompt`)
- **type**: From the role directory (`thinker`=claim, `coder`=evidence, `judge`=verdict, `researcher`=reference, prompts=question, `assumptions/`=assumption)
- **status**: `pending`
- **date**: Today
- **depends_on**: `[]` (edit manually to wire dependencies)
- **assumes**: `[]` (edit manually to link assumptions)

## After creation

Tell the user the generated ID and type. Remind them to edit `depends_on` and `assumes` fields to wire the dependency graph.
