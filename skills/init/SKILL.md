---
name: init
description: Initialize a new principia algorithm design project. Use when the user wants to start a new design project, set up the design directory structure, or bootstrap the principia system.
argument-hint: [project-title]
allowed-tools:
  - Bash
  - Write
---

# Initialize Design Project

Bootstrap a new principia algorithm design project in the current working directory.

## Steps

1. Create the `design/` directory structure:
   ```
   design/
   ├── claims/          # Flat claim directories (claim-N-name/)
   ├── context/         # Background surveys, tracked assumptions
   │   └── assumptions/
   └── .db/             # SQLite database (auto-generated)
   ```

2. Run the initial build:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design build
   ```

3. Generate initial PROGRESS.md and FOUNDATIONS.md:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design status
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design assumptions
   ```

4. If the user provided a project title, add it as context in `design/context/project.md` with appropriate frontmatter.

5. Add `design/.db/` to `.gitignore` if not already present.

6. Save default config to `design/.config.md`:
   ```markdown
   # Design Configuration

   ## Agent Dispatch Preferences
   - Scout: internal
   - Architect: internal
   - Adversary: internal
   - Experimenter: internal
   - Arbiter: internal
   - Synthesizer: internal
   ```

## After initialization

Inform the user:
- Use `/principia:design "<principle>"` to run a full design process
- Use `/principia:step` to advance manually, one agent at a time
- Use `/principia:status` to see progress
- Edit `design/.config.md` to change agent dispatch preferences (internal vs external)
