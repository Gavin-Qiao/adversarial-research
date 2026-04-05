# Principia Init Redesign

## Goal

Redesign Principia's first-run experience so `/principia:init` feels like an active repository setup and problem-framing ritual rather than a passive folder bootstrap.

The new init flow should:

- inspect the current repository automatically
- create the Principia workspace if needed
- guide the user through a thorough discussion to lock the north star
- help transform a high-level philosophy, intuition, or frustration into concrete claim directions
- leave the repository in a ready-to-advance state instead of a confusing partial setup

## Core Decisions

### Workspace Root

`principia/` becomes the only supported investigation root.

- new workspaces live under `principia/`
- defaults, docs, skills, hooks, and tests must stop pointing at `design/`
- this is a hard migration in product terms: future user-facing paths should talk only about `principia/`

If an older repository still has `design/` and not `principia/`, the product may offer a one-time migration action, but ongoing behavior should not preserve a dual-root mental model.

### Init Is One-Time and Human-Guided

`/principia:init` is run once per repository and stays human-guided regardless of autonomy mode.

- YOLO mode does not make init autonomous
- init can collect workflow autonomy preferences for later phases
- init must never auto-lock the north star without explicit user confirmation

### Init Owns the Understand/Discuss Phase

For Codex, `/principia:init` should own the entire first `understand > discuss` experience instead of dumping the user into raw workflow state.

That means init is responsible for:

- repository inspection
- workspace scaffolding
- autonomy and sidecar preference setup
- the deep discussion used to define the north star
- drafting initial claim candidates

## Problem Statement

The current Codex flow is structurally correct but poor product UX:

1. `/principia:init` creates folders, and optionally writes `.north-star.md` only if the user passes a title inline.
2. The next workflow state becomes `Understand > Discuss`.
3. The user is told a north star is missing, but there is no active Codex-native discussion flow that helps them produce one.

This makes the first command feel broken rather than intelligent.

## Desired User Experience

A new user in a real repository should experience Principia like this:

1. Run `/principia:init`.
2. Principia inspects the current repository and explains what it found.
3. Principia sets up `principia/` automatically if it does not exist.
4. Principia asks a small configuration block near the beginning:
   - later workflow autonomy preference
   - default sidecar behavior and dispatch style
5. Principia conducts a thorough back-and-forth discussion about the real problem in this repository.
6. When useful, Principia asks whether to bring in a sidecar such as a deep thinker, researcher, or coder.
7. Principia proposes a refined north star and asks the user to explicitly lock it.
8. Principia drafts concrete claim directions tied to the repo problem and prepares the workspace for the next phase.

The user should leave init feeling aligned and ready, not blocked by missing files or unexplained workflow phases.

## Non-Goals

- Do not make init fully autonomous.
- Do not let YOLO mode skip north-star confirmation.
- Do not preserve `design/` as an equal supported root.
- Do not force the user to understand internal workflow phases before the product has framed the problem.
- Do not auto-dispatch sidecars without asking.

## Product Behavior

### 1. Repository Inspection

Init begins by inspecting the current repository before asking the user to define the problem.

The inspection should gather practical context such as:

- top-level project shape
- build and test tooling
- primary runtime or language
- obvious subsystems or packages
- existing docs like `README.md`, `AGENTS.md`, and other repo guidance
- obvious places where the repo's current problem space appears

This inspection should be summarized for the user and persisted to `principia/.context.md`.

The purpose is not exhaustive static analysis. It is to give the discussion grounding in the actual codebase so the north star is about this repository, not abstract theory in a vacuum.

### 2. Workspace Scaffolding

If `principia/` does not exist, init creates at least:

```text
principia/
principia/claims/
principia/context/assumptions/
principia/.db/
principia/.config.md
```

If `principia/` already exists, init should detect that the repo has already been initialized and shift into an inspection/status/re-entry path rather than silently re-bootstrap.

### 3. Early Setup Block

Near the beginning, init asks the user to configure the repo-local operating posture for later work.

This setup block should cover:

- workflow autonomy preference for post-init phases
- sidecar defaults
- optional dispatch preferences for those sidecars

This block exists early because init is the right moment to define how Principia should collaborate on this repository.

#### YOLO Scope

YOLO configuration gathered during init affects later workflow execution only.

It does **not** change init's own requirement for:

- explicit sidecar approval
- explicit north-star confirmation
- a user-heavy discussion phase

### 4. Thorough Discussion Phase

Init must conduct a thorough discussion, not a short intake.

The goal of the discussion is to convert:

- a philosophy
- an intuition
- a repo frustration
- a product ambition
- a research direction

into a north star that is specific enough to drive decomposition into claims.

The discussion should continue until the user and Principia converge on:

- the actual repository problem being solved
- the success condition
- the mechanism or design intuition
- the key constraints or non-goals
- what could falsify the direction

The discussion is the most user-heavy phase in the workflow.

### 5. Sidecar Participation

Init may suggest sidecars when they would materially improve the discussion.

Examples:

- deep thinker for difficult conceptual or theoretical structure
- researcher for prior art or external context
- coder for feasibility checks against the current repository

But init must always ask before dispatching them.

At each sidecar-worthy moment, the user can:

- approve a one-off sidecar dispatch
- decline and continue the conversation directly
- revise their stored sidecar/autonomy preferences

This keeps init active without becoming over-automated.

### 6. North Star Lock

`principia/.north-star.md` is written only after explicit user confirmation.

Principia should propose a refined north star in repo-specific language and ask for a clear lock decision.

The north star should encode:

- the repository problem or opportunity
- the core design intuition
- the intended outcome
- enough specificity that the next phase can produce falsifiable claims

### 7. Initial Claims

After the north star is locked, init should draft a first set of claim candidates tied to the repository.

The output should be concrete enough to support the next workflow phase.

Depending on implementation complexity, init may either:

- write draft claims immediately, or
- persist claim candidates plus a ready-to-run next step

The important product property is that the user leaves init with a meaningful forward path, not just a folder tree.

## Configuration Model

`principia/.config.md` should evolve from a narrow agent-dispatch file into the repo-local Principia collaboration config.

At minimum it should be able to represent:

- workflow autonomy preference for post-init phases
- sidecar defaults
- sidecar dispatch preferences
- existing agent dispatch mode where still relevant

The exact storage format can remain lightweight and human-editable.

## Command Behavior Changes

### `/principia:init`

Becomes the canonical first-run ritual.

Responsibilities:

- detect or create `principia/`
- inspect the repo
- write initial context
- collect preferences
- conduct and manage the north-star discussion
- ask before sidecar dispatches
- lock the north star explicitly
- prepare initial claims or claim directions

### `/principia:status`

Should reflect whether the repo is:

- not initialized
- initialized but discussion in progress
- north star drafted but not locked
- north star locked and ready for claim work
- actively progressing through later phases

This command should expose meaningful user-facing state, not only raw internal phase names.

### `/principia:step`

If init has not completed north-star lock, `step` should continue the active discussion flow rather than merely surfacing an abstract `understand` phase.

After init is complete, `step` can resume its normal role as the workflow driver.

## Migration Impact

This is a hard migration to `principia/`.

The following surfaces must be updated:

- CLI defaults
- Codex skills
- Claude skills
- hooks
- docs
- tests
- any agent instructions or prompts that hard-code `design/`

User-facing documentation should stop teaching `design/` entirely.

## Acceptance Criteria

The redesign is successful when all of the following are true:

- A new user can run `/principia:init` in a repo with no existing workspace and be guided through setup without hitting a missing-north-star dead end.
- The created workspace root is `principia/`, not `design/`.
- Init performs repository inspection automatically and persists the findings.
- Init collects autonomy and sidecar preferences near the beginning.
- Init conducts a thorough discussion before writing the north star.
- Init asks before using a sidecar.
- Init requires explicit north-star confirmation.
- Init ends with the repository ready for meaningful next-step work.

## Recommendation

Implement this as a Codex-first UX redesign with corresponding shared-engine and documentation changes.

The product should feel like an active collaborator that helps the user turn repo-specific intuition into a concrete, testable design direction, not a passive filesystem scaffold.
