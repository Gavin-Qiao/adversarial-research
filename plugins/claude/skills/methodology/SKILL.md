---
name: methodology
description: This skill should be used when the user asks about the principia methodology — "how does this work", "why four phases", "what's the philosophy", "what are the roles" — and wants an explanation grounded in the current orchestration config.
---

# Principia — methodology reference

Explain the principia design methodology using live data from the current orchestration config.

## Step 1: Fetch the current phase list

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp phases --json`

Parse the output to get the phase names and their roles.

## Step 2: Fetch the role registry

Run: !`${CLAUDE_PLUGIN_ROOT}/scripts/pp roles --json`

Parse the output to get the role names and their phases.

## Step 3: Explain the methodology

Present the methodology to the user:

1. **The four phases**: list each phase name from `pp phases`, one line each with its role sequence.
2. **The role registry**: list each role from `pp roles` with its purpose and the phase it belongs to.
3. **The adversarial design principle**: briefly explain why architect+adversary debate, why empirical experiment, why post-verdict cascade.

Adjust if the config shows a different number of phases or roles than described — trust the live data, not a fixed narrative.
