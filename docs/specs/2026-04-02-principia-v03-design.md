# Principia v0.3 Design Spec (Revised)

## Problem

Principia v0.2 has a rigid linear pipeline that doesn't match how real research works. Real research has a discussion phase, inspection of existing work, deep literature research, scout/experimenter available at any moment, deep thinking for hard problems, recursive decomposition, and support for external tools.

## Scope & Effort

This is a **significant restructure**, not a minor evolution. Honest estimate:

| Work | Estimate |
|------|----------|
| Investigation-level state machine redesign (12 new actions) | 1 week |
| Per-claim state machine changes (side-channel awareness) | 3-4 days |
| Understand phase skill orchestration | 2-3 days |
| Deep Thinker agent + dispatch rubric | 1-2 days |
| Prompt mode (paste-into-chat) workflow | 2-3 days |
| Recursive investigation framework | 3-4 days |
| Breadcrumb UX + quick mode | 1-2 days |
| Tests, integration, documentation | 1 week |
| **Total** | **~4 weeks** |

---

## Design

### Four Phases

```
Understand  ->  Divide  ->  Test  ->  Synthesize
```

**Understand**: Clarify the principle (adaptive pushback), scan codebase + prior sessions, deep literature research.

**Divide**: Decompose into testable claims. Spawn child investigations for complex claims. Pure thinking -- no research or experiments.

**Test**: Per claim, debate (architect vs adversary) with side-channel validation (experimenter). Conductor orchestrates.

**Synthesize**: Compose surviving claims into a coherent algorithm design. Pure thinking.

### Three Ambient Services

Ambient services are never the primary agent. They are invoked by the orchestrator (skill or conductor) when the primary agent's work needs supplemental input.

| Service | Purpose | Available in | Triggered by |
|---------|---------|-------------|-------------|
| **Scout** | Literature, prior art, fact-checking | Understand, Test | Skill (Understand), Conductor (Test) |
| **Experimenter** | Empirical validation, code | Understand, Test | Skill (Understand), Conductor (Test) |
| **Deep Thinker** | Hard mathematical/theoretical reasoning | All four phases | Skill (Understand, Divide, Synthesize), Conductor (Test) |

**Deep Thinker is a specialist.** It enlightens; it does not produce final artifacts. Its output feeds back into the invoking agent's work. See "Deep Thinker Dispatch Rubric" below for when to invoke it vs. normal reasoning.

Divide and Synthesize: no scout, no experimenter. Deep thinker available for hard problems only.

### Dispatch Modes

Every agent dispatch supports two modes:

- **Execution mode (internal)**: Dispatched as Claude Code subagent.
- **Prompt mode (external)**: Principia generates a self-contained prompt (all context embedded, no file path references). User takes it to their preferred tool. User pastes result into chat. Principia validates format and saves to the correct file.

Configured per-agent in `design/.config.md`:
```markdown
## Agent Dispatch Preferences
- Scout: external (Gemini Deep Research)
- Architect: internal
- Adversary: external (different model for diversity)
- Experimenter: internal
- Deep Thinker: external (Claude extended thinking)
- Synthesizer: internal
```

**Prompt mode validation**: When user pastes a result into chat, the skill checks:
1. Does the result contain the expected output sections for this agent? (e.g., adversary must have "Severity:")
2. Is it non-empty and not truncated? (minimum length check)
3. If validation fails: tell user what's wrong and ask to re-paste.

**External tool constraints**: External prompts include a "Constraints" section that states what the agent should NOT do (e.g., architect prompt says "Do NOT reference specific codebase files or implementations"). This is instruction-based, not tool-enforced -- the same limitation as internal dispatch (agents follow instructions, not hard barriers).

### Recursive Structure

Any claim in the Divide phase can spawn a child principia investigation.

```
Root principia: "topology-preserving clustering"
  design/
  ├── .north-star.md          # Refined principle from Discussion
  ├── .context.md             # Inspection findings + key decisions
  ├── context/                # Research outputs
  ├── blueprint.md            # Division output
  └── claims/
      ├── claim-1-homology/   # Normal claim (atomic)
      │   ├── architect/
      │   ├── adversary/
      │   └── ...
      └── claim-2-vietoris/   # Complex claim (spawns sub-investigation)
          ├── claim.md
          └── design/         # Child principia
              ├── .north-star.md   # Inherited + claim-specific focus
              ├── .context.md      # Inherited + claim-specific
              └── claims/          # Sub-claims of claim-2
```

**Context inheritance (v0.3 -- snapshot-based):**
- Child inherits a snapshot of parent's `.north-star.md` and `.context.md` at spawn time
- Child's Understand phase is pre-filled with parent context but can be expanded
- No live propagation. If parent context changes after spawn, child's copy is stale.
- Verdict cascade (disproven -> weakened) works across parent/child via the existing mechanism.
- User is always asked before spawning, with context: claim statement, estimated complexity (number of likely sub-claims), what gets inherited, and note that they can treat it as atomic instead.

**Deferred to v0.4**: Live context/north-star cascade across parent/child investigations.

---

## Phase Details

### Understand Phase

Orchestrator: **the skill**. This phase is **skill-managed sequencing** -- the state machine returns a single `understand` action, and the skill manages the three sub-activities internally without state machine involvement.

**State machine**: `detect_investigation_state` returns:
```json
{"action": "understand", "phase": "understand", "substeps": ["discuss", "inspect", "research"]}
```

The skill tracks which sub-steps are complete by checking for output files:
- `.north-star.md` exists -> discussion done
- `.context.md` exists -> inspection done
- `context/survey-*.md` exists -> research done (at least one pass)

**1. Discussion (adaptive pushback)**

The skill runs this interactively:
- Reads the user's principle
- Adapts to confidence: certain -> challenge ("What about X? Have you considered Y?"), exploratory -> collaborate ("Interesting. Let me check what exists..."), vague -> focus ("Better how? Accuracy? Speed? Robustness?")
- May dispatch **@scout** to verify user's claims or map the space
- May dispatch **@deep-thinker** if hard mathematical relationships involved
- Outputs `.north-star.md`

**2. Inspection**

The skill scans directly (Read/Glob/Grep/Bash):
- Current codebase for relevant implementations
- Prior principia sessions (`design/` directories from past runs)
- Git history for related work
- Outputs `.context.md`

**3. Research**

The skill dispatches **@scout** for deep literature review. Iterative: skill reads scout output, identifies follow-up questions, dispatches scout again. May dispatch **@deep-thinker** if papers reveal hard theoretical questions.
- Outputs `context/survey-*.md` and `context/comparison-*.md`

**Phase transition**: Skill asks user "Ready to decompose, or want to research more?" User controls when to move to Divide.

### Divide Phase

Orchestrator: **the skill**. Primary agent: **@synthesizer**.

1. Skill dispatches **@synthesizer** with: north star + context + research outputs
2. Synthesizer produces `blueprint.md` with claim registry (3-7 claims, each with statement, maturity, falsification criterion, dependencies)
3. If decomposition involves hard math, skill dispatches **@deep-thinker**, feeds result back to second @synthesizer dispatch
4. For each claim, skill shows user: claim statement, maturity, dependencies, estimated complexity. Asks: "Investigate deeper or treat as atomic?"
5. If deeper: spawn child principia with inherited context

**State machine**: Returns `divide` then `scaffold` actions (same as current `create_blueprint` + `scaffold_cycles`).

### Test Phase

Orchestrator: **@conductor** (dispatched by the skill for each claim).

**Per-claim state machine changes**: The core debate loop (`detect_state`) stays sequential: architect -> adversary -> [severity check] -> continue or exit -> experimenter -> arbiter -> verdict. This does NOT change.

**Side-channel dispatches** (experimenter, scout, deep-thinker mid-debate) are managed by the conductor outside the state machine. The conductor:
1. Calls `manage.py next` to get the main-line action
2. Dispatches the main-line agent (architect or adversary)
3. Reads the result, decides if a side-channel is needed
4. If yes: dispatches side-channel agent, saves to `check-N.md` or `targeted-N.md` or `analysis-N.md`
5. Incorporates side-channel results into the NEXT main-line dispatch's prompt
6. Calls `manage.py next` again for the next main-line action

The state machine never sees side-channel files. It only tracks: architect rounds, adversary rounds, experimenter main result, arbiter verdict. This preserves backward compatibility.

**Conductor renders verdict directly** (see "Arbiter Resolution" below). After verdict, skill runs `manage.py post-verdict`.

### Synthesize Phase

Orchestrator: **the skill**. Primary agent: **@synthesizer**.

1. Skill dispatches **@synthesizer** with: all verdicts, debate transcripts, experimental results, north star
2. Synthesizer produces `composition.md` and `synthesis.md`
3. If conflicting verdicts need mathematical reconciliation, skill dispatches **@deep-thinker**, feeds result to second @synthesizer dispatch
4. Skill runs `manage.py results` to generate `RESULTS.md`

---

## Resolved Contradictions

### Arbiter Resolution

**Decision**: Conductor renders verdicts directly. The standalone @arbiter agent is kept for a specific use case: when the user runs `/principia:step` manually and wants an independent verdict evaluation (not conductor-authored). This is the `/principia:step` path only.

| Path | Who renders verdict |
|------|-------------------|
| `/principia:design` (automated) | Conductor (acting as arbiter) |
| `/principia:step` (manual) | Standalone @arbiter agent |

Conductor.md includes the full verdict rubric. Arbiter.md stays as a standalone agent for manual mode.

### Deep Thinker Dispatch Rubric

**Invoke Deep Thinker when** (concrete examples):
- "Is this claim actually two independent claims, or are they coupled through [mathematical relationship]?"
- "The adversary cites theorem X as a contradiction. Does theorem X actually apply given our assumptions?"
- "Papers A and B seem to contradict each other on [point]. What's the resolution?"
- "The synthesizer's decomposition assumes [property]. Is that property preserved under [operation]?"
- "The experimenter's results show unexpected behavior at [boundary]. What's the theoretical explanation?"

**Do NOT invoke Deep Thinker when:**
- The architect needs to propose a design (that's architect's job)
- The synthesizer needs to decompose claims (that's synthesizer's job, unless a specific mathematical question blocks it)
- Literature needs to be found (that's scout's job)
- Something needs empirical testing (that's experimenter's job)
- The conductor needs to decide next action (that's conductor's judgment)

**Rule of thumb**: If you can phrase the need as a specific mathematical/theoretical QUESTION with a definite answer, dispatch Deep Thinker. If it's a creative/strategic task, use the primary agent.

### Quick Mode in 4-Phase Model

`/principia:design "principle" --quick`:
1. **Understand**: Skip Research (no scout dispatch). Discussion is brief (1-2 clarifying questions max). Inspection still runs.
2. **Divide**: Scaffold a single claim directly from the principle (skip synthesizer decomposition).
3. **Test**: 1 debate round max, then experimenter, then verdict.
4. **Synthesize**: Generate RESULTS.md directly (skip composition/synthesis agents).

Quick mode is for rapid validation of a focused, well-understood claim. Not for broad principles that need decomposition.

---

## Breadcrumb UX

Every `/principia:step` and `/principia:status` shows:

```
[Understand > Discussion] Refining principle with user...
  Next: inspection (codebase scan)
  North star: "Topology-preserving clustering via persistent homology"
```

```
[Test > Claim 2/4 > Debate R1] Adversary attacked. Severity: Serious.
  Side-channel: experimenter testing sparse graphs...
  Next: architect round 2 (after side-channel completes)
  North star: "Topology-preserving clustering via persistent homology"
```

```
[Divide > Claim 3/5] Complex claim detected.
  Claim: "Vietoris-Rips complex is tractable at scale"
  Estimated sub-claims: 2-3
  Inherits: parent north star + context
  Next: asking user -- investigate deeper or treat as atomic?
```

For recursive investigations, breadcrumb shows depth:
```
[Test > Claim 2 > Sub-investigation > Claim 2.1 > Debate R1]
  Parent: "Vietoris-Rips tractability"
  North star (inherited): "Topology-preserving clustering..."
```

Side-channel dispatches appear inline (not as separate breadcrumb levels).

---

## User Recovery Actions

| Scenario | How to recover |
|----------|---------------|
| Skip a phase | "Skip Research" during Understand -> skill writes empty survey, moves to Divide. User can always say "I already know the literature." |
| Restart a phase | "Restart Divide" -> skill deletes blueprint.md and claim directories, re-dispatches synthesizer. User confirms first (destructive). |
| Change north star | Edit `.north-star.md` directly. Skill detects change on next `/principia:step` and warns: "North star changed. Re-run Understand phase? (Child investigations may be stale.)" |
| Add claim after Divide | "Add a new claim" -> skill runs `manage.py scaffold claim <name>`, adds to blueprint. State machine picks it up in next wave. |
| Bad paste in prompt mode | Skill validates and says: "This doesn't look like a scout result (missing 'Key Findings' section). Paste again or switch to internal dispatch?" |
| Child investigation invalidates parent | Verdict cascade handles this automatically (disproven -> dependents weakened). User sees in PROGRESS.md. |

---

## Agent Roster

| Agent | Role | Primary in | Ambient in | Codebase access |
|-------|------|-----------|-----------|----------------|
| **Scout** | Literature, prior art | Understand (research) | Understand, Test | Yes (Read/Glob/Grep + WebSearch) |
| **Architect** | Propose algorithm designs | Test (debate) | -- | No (WebSearch only) |
| **Adversary** | Attack designs, find flaws | Test (debate) | -- | No (WebSearch only) |
| **Experimenter** | Empirical validation | Test (validation) | Understand, Test | Yes (full: Read/Write/Edit/Bash) |
| **Arbiter** | Standalone verdict evaluation | Test (manual /step only) | -- | Read-only (Read/Glob/Grep) |
| **Synthesizer** | Decomposition + composition | Divide, Synthesize | -- | No (WebSearch only) |
| **Deep Thinker** | Hard math/theory reasoning | -- (always ambient) | All four phases | No (WebSearch only) |
| **Conductor** | Orchestrate Test phase + verdict | Test (orchestrator) | -- | Yes (Agent/Read/Write/Bash) |

**Deep Thinker output location**: `{claim}/deep-thinker/analysis-{N}.md` (side-channel). Does not produce final artifacts.

---

## State Machine Changes

### Investigation level (`detect_investigation_state`)

| New action | Phase | Replaces | Detection logic |
|-----------|-------|----------|----------------|
| `understand` | Understand | `gather_context` | No `.north-star.md` OR no `.context.md` OR no `context/survey-*.md` |
| `divide` | Divide | `create_blueprint` | North star + context exist, no `blueprint.md` |
| `scaffold` | Divide | `scaffold_cycles` | Blueprint exists, unscaffolded claims remain |
| `test_claim` | Test | `run_cycle` | Scaffolded claims need testing (wave-ordered) |
| `record_verdict` | Test | `review_cycle` | Claim needs post-verdict bookkeeping |
| `synthesize` | Synthesize | `compose` + `synthesize` | All claims tested, no `synthesis.md` |
| `complete` | (terminal) | `complete` | `synthesis.md` exists |

The skill manages Understand sub-steps (discussion/inspection/research) internally based on output file existence. No sub-step actions in state machine.

### Per-claim level (`detect_state`)

**No changes to the sequential state machine.** Transitions remain:
```
dispatch_architect -> dispatch_adversary -> [severity] -> dispatch_experimenter -> dispatch_arbiter -> post_verdict -> complete_*
```

Side-channel dispatches (mid-debate experimenter, scout, deep-thinker) are conductor-managed, outside the state machine. The state machine only tracks main-line files.

---

## Files to Modify

| File | Changes | Effort |
|------|---------|--------|
| `scripts/orchestration.py` | Replace investigation-level actions. Add `understand` detection logic. | Medium |
| `scripts/manage.py` | Breadcrumb formatting in `cmd_next`. Validation for paste-mode results. | Medium |
| `agents/deep-thinker.md` | NEW | Small |
| `agents/conductor.md` | Add verdict rubric (already done in v0.2 fixes). Clarify side-channel management. | Small |
| `agents/arbiter.md` | Clarify: standalone agent for manual /step mode only. | Small |
| `skills/design/SKILL.md` | Rewrite for 4-phase model with skill-managed Understand sequencing. | Large |
| `skills/step/SKILL.md` | Paste-into-chat workflow, breadcrumb output, prompt validation. | Medium |
| `skills/init/SKILL.md` | Create `.north-star.md` and `.context.md`. | Small |
| `config/orchestration.yaml` | Add quick-mode config. | Small |
| `README.md` | Rewrite workflow section. | Medium |

## What Stays the Same

- Per-claim state machine (`detect_state`) -- untouched
- Database schema (nodes, edges, ledger)
- Frontmatter format and YAML parser
- Cascade logic
- All existing Python utility functions
- Contract tests (state table still valid)
- Security tests, YAML parser tests, serializer tests

## Verification

1. All 337 existing tests still pass
2. New tests: understand detection, divide/scaffold, breadcrumb output, paste validation, quick mode
3. Contract tests: add new investigation-level contract table for understand/divide/synthesize transitions
4. End-to-end: full `/principia:design` through all 4 phases
5. Quick mode: `/principia:design "claim" --quick` completes in single cycle
6. Prompt mode: external dispatch, paste result, verify validation catches bad input
7. Recursive: spawn sub-investigation, verify context inheritance
