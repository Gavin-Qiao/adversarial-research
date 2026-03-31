# Adversarial Research Workflow

## Phases

A sub-unit investigation proceeds through four phases:

```
Pre-falsification → Falsification → Judgment → Recording
(thinker/refutor)    (coder)         (judge)    (reviewer)
```

### Phase 1: Pre-falsification (Debate)

The thinker and refutor alternate rounds. The thinker proposes, the refutor attacks.

```
Round 1:
  Thinker R1: proposes hypothesis
  Refutor R1: attacks it (rates severity: Fatal / Serious / Minor)

  If severity is Fatal or Serious AND round < max_rounds:
    → Round 2 (thinker must shift framework, not just patch)
  If severity is Minor or None:
    → Exit to Falsification phase
  If round = max_rounds:
    → Exit to Falsification phase (regardless of severity)

Round 2:
  Thinker R2: revised hypothesis from a different theoretical angle
  Refutor R2: attacks revision
  (same exit logic)

Round 3 (hard cap):
  Thinker R3: final proposal
  Refutor R3: final attack (refutor always gets the last word)
  → Exit to Falsification phase
```

The refutor always gets the final say before the coder. The max round limit and severity exit conditions are configurable in `config/orchestration.yaml`.

### Phase 2: Falsification (Empirical Testing)

The coder receives all debate context and runs experiments with synthetic data. The coder should pre-register analysis criteria (in prompt.md) before seeing results. Reports quantitative metrics with statistical rigor.

### Phase 3: Judgment

A structured brief is prepared summarizing:
- The claim (thinker's final hypothesis)
- Key disagreement between thinker and refutor
- Strongest argument for and against
- Empirical evidence and whether pre-registered criteria were met
- Unresolved points

The judge reads the brief (and can dig into individual files) and renders: SETTLED / FALSIFIED / MIXED.

### Phase 4: Recording

The reviewer updates frontmatter statuses, runs cascade invalidation if falsified, regenerates FRONTIER.md and ASSUMPTIONS.md, and writes a summary.

## State Machine

The orchestrator determines the next action by scanning what files exist in the sub-unit directory.

Each row below is a **contract** — tested automatically by `tests/test_workflow_contract.py`.
If code or docs change without updating the other, tests fail.

<!-- CONTRACT:STATE_TABLE_START -->
| ID | State | Action | Phase |
|----|-------|--------|-------|
| T1 | No thinker round-1 result | dispatch_thinker round 1 | pre-falsification |
| T2 | Thinker round 1 done, no refutor | dispatch_refutor round 1 | pre-falsification |
| T3 | Refutor done, severity fatal, round < max | dispatch_thinker round 2 | pre-falsification |
| T4 | Refutor done, severity serious, round < max | dispatch_thinker round 2 | pre-falsification |
| T5 | Refutor done, severity minor | dispatch_coder | falsification |
| T6 | Refutor done, severity none | dispatch_coder | falsification |
| T7 | Refutor done, severity unknown, default continue | dispatch_thinker round 2 | pre-falsification |
| T8 | Refutor done, round = max_rounds (3) | dispatch_coder | falsification |
| T9 | Coder done, no verdict | dispatch_judge | judgment |
| T10 | Verdict exists, reviewer not done | dispatch_reviewer | recording |
| T11 | Prompt exists without result | waiting | pre-falsification |
<!-- CONTRACT:STATE_TABLE_END -->

## Branching After Verdict

<!-- CONTRACT:VERDICT_TABLE_START -->
| ID | Verdict | Action | Cascade |
|----|---------|--------|---------|
| V1 | SETTLED | complete_settled | false |
| V2 | FALSIFIED | complete_falsified | true |
| V3 | MIXED | complete_mixed | false |
<!-- CONTRACT:VERDICT_TABLE_END -->

## External Agent Flow

For agents configured as external:
1. The orchestrator generates a self-contained prompt.md with all context embedded
2. The user pastes it into an external session (claude.ai, API, etc.)
3. The user saves the response as result.md
4. The orchestrator detects the file and continues

## Unit and Cycle Resolution

When all sub-units in a unit are resolved (no pending):
1. Dispatch deep-thinker for cross-unit synthesis
2. Dispatch judge for unit-level verdict
3. Dispatch reviewer to update unit frontier

When all units in a cycle are resolved:
1. Update cycle frontier
2. Decide whether to open next cycle or conclude

## Configurable vs Hardcoded

**Configurable** (via `config/orchestration.yaml`):
- Max debate rounds
- Severity keywords and exit conditions
- Post-verdict actions and messages
- Which severity levels continue debate vs exit

**Hardcoded** (in `scripts/orchestration.py`):
- Phase order: pre-falsification → falsification → judgment → recording
- Debate participants: thinker and refutor
- The state machine transition logic
- Context file ordering

To change the hardcoded behavior, modify `detect_state()` in `scripts/orchestration.py`.
