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
   ├── deep-thinker/    # Deep thinker analysis (ambient, cross-claim)
   └── .db/             # SQLite database (auto-generated)
   ```

2. If the user provided a project title or principle, create `design/.north-star.md`:
   ```markdown
   # [User's principle or title]

   [If the user provided a description, include it here. Otherwise leave blank for the Understand phase to fill in.]
   ```

   If no title/principle was provided, do NOT create `.north-star.md` — the Understand phase will create it through discussion.

3. Do NOT create `design/.context.md` — the Understand phase's inspection sub-step creates this.

4. Run the initial build:
   ```bash
   uv run python -m principia.cli.manage --root design build
   ```

5. Generate initial PROGRESS.md and FOUNDATIONS.md:
   ```bash
   uv run python -m principia.cli.manage --root design status
   uv run python -m principia.cli.manage --root design assumptions
   ```

6. Add `design/.db/` to `.gitignore` if not already present.

7. Save default config to `design/.config.md`. This file controls **agent dispatch mode only** (internal = subagent, external = prompt file for copy/paste). It does NOT control workflow behavior -- that's in `config/orchestration.yaml`.
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
- All agents run as Claude Code subagents by default. To use external LLMs for any agent, edit `design/.config.md` and set it to `external` — the system will generate a self-contained prompt you can paste into any LLM. Note: external dispatch requires manual copy/paste, so it is incompatible with yolo mode.
- Autonomy mode (checkpoints vs yolo for overnight runs) is in `config/orchestration.yaml`
