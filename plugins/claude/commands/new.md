---
description: Create a new principia markdown file with auto-generated frontmatter.
argument-hint: "<relative-path>"
allowed-tools: Bash
---

Create a new markdown file with auto-generated frontmatter (type, status, id derived from path).

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp new "$1"`

Confirm the file was created and report its id.

The path should be relative to the principia root. Examples:
- `claims/claim-1-enrichment/architect/round-1/prompt.md`
- `claims/claim-1-enrichment/experimenter/results/output.md`
- `context/assumptions/my-assumption.md`

The `.md` extension is appended automatically if missing.

## Auto-generated frontmatter

The tool infers:
- **id**: Abbreviated from the path (e.g., `h1-architect-r1-prompt`)
- **type**: From the role directory (`architect`=claim, `experimenter`=evidence, `arbiter`=verdict, `scout`=reference, prompts=question, `assumptions/`=assumption)
- **status**: `pending`
- **date**: Today
- **depends_on**: `[]` (edit manually to wire dependencies)
- **assumes**: `[]` (edit manually to link assumptions)

## After creation

Tell the user the generated ID and type. Remind them to edit `depends_on` and `assumes` fields to wire the dependency graph.
