---
description: Initialize a new Principia workspace — inspect the repo, guide the user through the north star, and bootstrap the directory + DB.
argument-hint: "[project-title]"
allowed-tools:
  - Bash
  - Write
  - Read
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
---

# Initialize Principia Project

Bootstrap a new principia workspace in the current working directory.

## Steps

1. Create the `principia/` directory structure:
   ```
   principia/
   ├── claims/          # Flat claim directories (claim-N-name/)
   ├── context/         # Background surveys, tracked assumptions
   │   └── assumptions/
   ├── deep-thinker/    # Deep thinker analysis (ambient, cross-claim)
   └── .db/             # SQLite database (auto-generated)
   ```

2. If the user provided a project title or principle, create `principia/.north-star.md`:
   ```markdown
   # [User's principle or title]

   [If the user provided a description, include it here. Otherwise leave blank for the Understand phase to fill in.]
   ```

   If no title/principle was provided, do NOT create `.north-star.md` — the Understand phase will create it through discussion.

3. Do NOT create `principia/.context.md` — the Understand phase's inspection sub-step creates this.

4. Run the initial build:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/pp build
   ```

5. Generate initial PROGRESS.md and FOUNDATIONS.md:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/pp status
   ${CLAUDE_PLUGIN_ROOT}/scripts/pp assumptions
   ```

6. Add the database directory to `.gitignore`: run `pp paths --json` and add the `db` path to `.gitignore` if not already present.

7. Save default config to `principia/.config.md`. This file controls **agent dispatch mode only** (internal = subagent, external = prompt file for copy/paste). It does NOT control workflow behavior — that's in `config/orchestration.yaml`.
   ```markdown
   # Design Configuration

   ## Agent Dispatch Preferences
   - Scout: internal
   - Architect: internal
   - Adversary: internal
   - Experimenter: internal
   - Arbiter: internal
   - Synthesizer: internal
   - Deep Thinker: internal
   ```

   Autonomy settings (checkpoints vs yolo mode) are in `config/orchestration.yaml`, not here.

## After initialization

Inform the user:
- Use `/principia:design "<principle>"` to run a full 4-phase design process (Understand > Divide > Test > Synthesize)
- Use `/principia:step` to advance manually, one agent at a time
- Use `/principia:status` to see progress
- Use `/principia:help` for a full command reference
- All agents run as Claude Code subagents by default. To use external LLMs for any agent, edit `principia/.config.md` and set it to `external` — the system will generate a self-contained prompt you can paste into any LLM. Note: external dispatch requires manual copy/paste, so it is incompatible with yolo mode.
- Autonomy mode (checkpoints vs yolo for overnight runs) is in `config/orchestration.yaml`
