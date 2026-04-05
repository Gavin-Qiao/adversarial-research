---
name: help
description: Show an overview of what Principia can do and how to get started. Adapts to the current project state. Use when the user asks for help, asks what commands are available, or seems unsure how to use the plugin.
allowed-tools:
  - Bash
  - Read
---

# Principia Help

Adapt the help output to the user's current project state.

## Step 1: Detect State

Check the current project:

```bash
if [ -d design ]; then
  uv run python -m principia.cli.manage --root design investigate-next 2>/dev/null
  uv run python -m principia.cli.manage --root design autonomy-config 2>/dev/null
fi
```

Also check if `design/.config.md` exists and whether any agents are set to `external`.

## Step 2: Present Help

Based on what you found, present ONE of these variants:

### If no `design/` directory exists:

> **Principia** turns a philosophical principle into a working algorithm through adversarial testing.
>
> To get started:
> ```
> /principia:init "Your project title"
> /principia:design "Your principle or insight here"
> ```
>
> This runs 4 phases: **Understand** (refine + research) > **Divide** (decompose into claims) > **Test** (debate + experiment per claim) > **Synthesize** (compose surviving theory).
>
> Add `--quick` for a fast single-claim investigation.

Then show the full commands table and agents list from the reference section below.

### If `design/` exists and investigation is active:

Show a **status-first** response:

1. **Where you are**: Read the `breadcrumb` and `action` from `investigate-next` output. Tell the user: "You're in **[phase]**. Next action: **[action]**."
2. **How to continue**: Based on the action:
   - `understand` → "Run `/principia:design` to continue, or `/principia:step` for manual control."
   - `divide` / `scaffold` → "Run `/principia:step` to scaffold claims, or `/principia:design` to continue automatically."
   - `scaffold_quick` → "Quick mode: scaffolding a single claim. Run `/principia:design` to continue."
   - `test_claim` → "Run `/principia:step` to test the next claim, or `/principia:design` to run all remaining claims."
   - `record_verdict` → "A claim has been tested. Run `/principia:step` to record the verdict, or `/principia:design` to continue."
   - `complete_partial` → "A claim was partially proven. Run `/principia:step` to decide: narrow the claim, gather more evidence, or accept and move on."
   - `complete_inconclusive` → "A claim was inconclusive. Run `/principia:step` to decide: try a different approach, gather more evidence, or defer."
   - `synthesize` → "All claims tested. Run `/principia:step` to synthesize, or `/principia:design` to finish automatically."
   - `complete` → "Investigation complete! Run `/principia:status` to see results, or read `design/RESULTS.md`."
3. **Current config**: Report autonomy mode (checkpoints/yolo) and whether any agents are external.
4. **Quick reference**: Show the commands table below.

### If `design/` exists but investigation is complete:

> Your investigation is **complete**. See `design/RESULTS.md` for the full summary.
>
> To start a new investigation, remove or rename the `design/` directory and run `/principia:init`.

Then show the commands table.

## Reference (always available)

### Commands

| Command | What it does |
|---------|-------------|
| `/principia:init [title]` | Set up a new design project |
| `/principia:design "<principle>"` | Full pipeline: principle to algorithm |
| `/principia:design "<principle>" --quick` | Quick mode: 1 round, 1 claim, fast results |
| `/principia:step` | Advance one step manually |
| `/principia:status` | Show current progress and blockers |
| `/principia:impact <id>` | Preview: what breaks if this claim is disproven? |
| `/principia:query "<sql>"` | Query the evidence database |
| `/principia:methodology` | Reference: how the methodology works |
| `/principia:help` | This guide |

### Agents

| Agent | Role | Phases |
|-------|------|--------|
| **@architect** | Proposes designs (no codebase access) | Test |
| **@adversary** | Finds flaws and counterexamples (no codebase access) | Test |
| **@experimenter** | Tests claims with code and data | Test |
| **@arbiter** | Evaluates evidence, renders verdict | Test |
| **@conductor** | Orchestrates full claim cycles | Test |
| **@synthesizer** | Decomposes principles and unifies findings | Divide, Synthesize |
| **@scout** | Surveys prior art and literature | Understand, Test |
| **@deep-thinker** | Hard math/theory reasoning | Any phase |

### Modes

| Mode | Behavior | Config |
|------|----------|--------|
| **Checkpoints** (default) | Pauses between phases for your input | `autonomy.mode: checkpoints` |
| **Yolo** | Fully automated, for overnight runs | `autonomy.mode: yolo` |

Autonomy is configured in `config/orchestration.yaml`. Agent dispatch mode (internal vs external) is in `design/.config.md`.
