---
name: init
description: Initialize Principia for this repository by inspecting the project, scaffolding a principia workspace, collecting preferences, and guiding the user to a locked north star.
---

# Init

`/principia:init` is a one-time repository setup ritual. It should be active and discussion-heavy, not a passive folder bootstrap.

## Principles

- Treat `principia/` as the only supported workspace root.
- If legacy `design/` exists and `principia/` does not, move the workspace to `principia/` before continuing.
- Always inspect the current repository before trying to define the north star.
- Ask about autonomy and sidecar preferences near the beginning.
- Conduct a thorough discussion until the north star is explicitly locked.
- Ask before dispatching a sidecar such as a deep thinker, researcher, or coder.
- Do not let YOLO mode make init autonomous.

## Workspace setup

If `principia/` is missing, create:

```text
principia/
principia/claims/
principia/context/assumptions/
principia/.db/
```

Also ensure `principia/.config.md` exists. Use a human-editable markdown shape like:

```markdown
# Principia Configuration

## Agent Dispatch Preferences
- Scout: internal
- Architect: internal
- Adversary: internal
- Experimenter: internal
- Arbiter: internal
- Synthesizer: internal
- Deep Thinker: internal

## Workflow Preferences
- Workflow Autonomy: checkpoints

## Sidecar Preferences
- Deep Thinker Sidecar: ask
- Researcher Sidecar: ask
- Coder Sidecar: ask
```

## Repository inspection

Before locking the north star, inspect the current repo and summarize:

- top-level structure
- build/test tooling
- runtime/language
- obvious subsystems
- relevant docs such as `README.md` and `AGENTS.md`
- the likely problem surface this repo is trying to solve

Write the repo-grounded summary to `principia/.context.md`.

## Early setup questions

Near the beginning, ask the user to confirm or revise:

- the later workflow autonomy mode (`checkpoints` or `yolo`)
- default sidecar behavior (`ask`, `auto`, `off`)
- whether any sidecar should prefer deeper conceptual reasoning, research, or implementation feasibility checks

Persist those preferences in `principia/.config.md`.

## Discussion phase

Then stay in a thorough discussion until the north star is actually ready.

The discussion should uncover:

- what problem in this repo the user is trying to solve
- what success looks like
- the underlying intuition or philosophy
- important constraints or non-goals
- what could falsify the direction

If a sidecar would help, ask first. The user may approve a one-off dispatch or revise preferences before continuing.

Only after explicit user confirmation should you write `principia/.north-star.md`.

## Exit state

After the north star is locked:

- draft 3-5 concrete claim directions tied to the repository
- scaffold claim directories if the user is ready
- otherwise leave a clear next-step summary tied to the dashboard state

Finally verify the workspace is wired:

```bash
uv run python -m principia.cli.codex_runner --root principia build
uv run python -m principia.cli.codex_runner --root principia dashboard
```

In Codex, report the JSON summary and tell the user whether initialization is still in discussion, ready for claims, or ready for the ongoing workflow.
