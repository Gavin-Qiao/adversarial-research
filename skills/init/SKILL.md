---
name: init
description: Initialize a new adversarial research project. Use when the user wants to start a new research project, set up the research directory structure, or bootstrap the adversarial research system.
argument-hint: [project-title]
allowed-tools:
  - Bash
  - Write
  - AskUserQuestion
---

# Initialize Research Project

Bootstrap a new adversarial research project in the current working directory.

## Steps

1. Create the `research/` directory structure:
   ```
   research/
   ├── cycles/          # Research cycles (cycle-N/)
   ├── context/         # Knowledge distillations, assumptions
   │   └── assumptions/ # Tracked assumptions
   └── .db/             # SQLite database (auto-generated)
   ```

2. Run the initial build:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research build
   ```

3. Generate initial FRONTIER.md and ASSUMPTIONS.md:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research status
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research assumptions
   ```

4. If the user provided a project title, add it as context in `research/context/project.md` with appropriate frontmatter.

5. Add `research/.db/` to `.gitignore` if not already present.

6. **Ask agent dispatch preferences** using AskUserQuestion. First, offer recommended defaults:

   "Would you like to use recommended defaults for agent dispatch?
   - Researcher: **internal** (subagent)
   - Thinker: **internal** (subagent)
   - Refutor: **internal** (subagent)
   - Coder: **internal** (subagent)
   - Judge: internal (always)
   - Reviewer: internal (always)

   Or would you prefer to customize each agent individually?"

   If the user accepts defaults, skip to step 7 with all agents set to internal.

   If the user wants to customize, ask for each non-judge agent:

   **Researcher**:
   - **Internal (subagent)**: Use `@researcher` within Claude Code. Good for targeted lookups and quick surveys. (Recommended for focused questions like "has X been tried?")
   - **External (prompt only)**: Generate a self-contained prompt for a separate Claude session. Better for deep, comprehensive literature surveys where you want the full context window dedicated to research. (Recommended for cycle-level deep research and broad surveys)

   **Thinker**:
   - **Internal (subagent)**: Use `@thinker` within Claude Code. Good for quick iterations, stays in session context. (Recommended for focused sub-unit investigations)
   - **External (prompt only)**: Generate a self-contained prompt file that the user pastes into a separate Claude session (claude.ai, API, etc.). Better for deep thinking where you want maximum context window and no tool distractions. (Recommended for cycle-level deep thinking and open-ended exploration)

   **Refutor**:
   - **Internal (subagent)**: Use `@refutor` within Claude Code. Good for rapid attack-response cycles. (Recommended for most cases)
   - **External (prompt only)**: Generate a prompt for external dispatch. Better when the refutor needs to reason deeply without session constraints. (Recommended for foundational assumption attacks)

   **Coder**:
   - **Internal (subagent)**: Use `@coder` within Claude Code. Has full codebase access, can write and run experiments directly. (Recommended for all cases — the coder needs tool access)
   - **External (prompt only)**: Generate a prompt. Rarely useful since the coder needs to execute code. Only use if experiments will be run manually.

   Present this as 4 separate questions. The judge and reviewer are always internal (they need file access).

7. Save the preferences to `research/.config.md`:
   ```markdown
   # Research Configuration

   ## Agent Dispatch Preferences
   - Researcher: internal | external
   - Thinker: internal | external
   - Refutor: internal | external
   - Coder: internal | external
   - Judge: internal (always)
   - Reviewer: internal (always)
   ```

## After initialization

Inform the user:
- Use `/adversarial-research:new` to create research files
- Use `/adversarial-research:status` to see the frontier
- For **internal** agents: use `@researcher`, `@thinker`, `@refutor`, `@coder`, `@judge`, `@reviewer`
- For **external** agents: the system will generate self-contained prompt files at `<role>/round-N/prompt.md` that can be pasted into a separate Claude session. Save the response back as `result.md`.
- After each verdict, use `@reviewer` to record outcomes and update the frontier
- These preferences can be changed anytime by editing `research/.config.md`
