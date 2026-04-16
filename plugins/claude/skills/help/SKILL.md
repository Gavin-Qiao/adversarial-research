---
name: help
description: This skill should be used when the user asks "how do I start", "what should I do next", "help me with principia", or is new to the project and needs a walkthrough based on the current workspace state.
---

# Principia — adaptive help

Guide the user based on the current state of their principia workspace.

## Step 1: Check workspace state

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp paths --json`

Inspect the output to find the workspace root, the PROGRESS.md path, and the config path.

## Step 2: Check progress

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp status`

Read the regenerated PROGRESS.md (path from step 1) to see current phase and active claims.

## Step 3: Respond based on state

- If the workspace doesn't exist yet (paths exist but directories are empty): suggest `/principia:init`.
- If in Phase 1 (Understand): guide toward locking the north star.
- If in Phase 2 (Divide): suggest running `/principia:design` or `/principia:step` on the next unproved claim.
- If claims exist but no verdicts: suggest `/principia:step` to dispatch the next agent.
- If there are blockers or invalid claims: suggest `/principia:validate`.

Be concise. Do not list all possible commands — recommend the single most relevant next action.
