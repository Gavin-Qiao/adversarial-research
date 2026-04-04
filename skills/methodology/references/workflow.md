# Principia Design Workflow

## Phases

A claim investigation proceeds through four phases:

```
Dialectic       -> Refutation    -> Judgment  -> Recording
(architect/adversary) (experimenter)  (arbiter)   (post-verdict)
```

### Phase 1: Dialectic (Debate)

The architect and adversary alternate rounds. The architect proposes, the adversary attacks.

```
Round 1:
  Architect R1: proposes design solution
  Adversary R1: attacks it (rates severity: Fatal / Serious / Minor)

  If severity is Fatal or Serious AND round < max_rounds:
    -> Round 2 (architect must shift framework, not just patch)
  If severity is Minor or None:
    -> Exit to Refutation phase
  If round = max_rounds:
    -> Exit to Refutation phase (regardless of severity)

Round 2:
  Architect R2: revised proposal from a different theoretical angle
  Adversary R2: attacks revision
  (same exit logic)

Round 3 (hard cap):
  Architect R3: final proposal
  Adversary R3: final attack (adversary always gets the last word)
  -> Exit to Refutation phase
```

The adversary always gets the final say before the experimenter. The max round limit and severity exit conditions are configurable in `config/orchestration.yaml`.

### Phase 2: Refutation (Empirical Testing)

The experimenter receives all debate context and runs experiments with synthetic data. The experimenter should pre-register analysis criteria (in prompt.md) before seeing results. Reports quantitative metrics with statistical rigor.

### Phase 3: Judgment

A structured brief is prepared summarizing:
- The claim (architect's final design proposal)
- Key disagreement between architect and adversary
- Strongest argument for and against
- Empirical evidence and whether pre-registered criteria were met
- Unresolved points

The arbiter reads the brief (and can dig into individual files) and renders: PROVEN / DISPROVEN / PARTIAL / INCONCLUSIVE.

### Phase 4: Recording

The post-verdict step updates frontmatter statuses, runs cascade invalidation if disproven, regenerates PROGRESS.md and FOUNDATIONS.md, and writes a summary.

## State Machine

The conductor determines the next action by scanning what files exist in the claim directory.

Each row below is a **contract** -- tested automatically by `tests/test_workflow_contract.py`.
If code or docs change without updating the other, tests fail.

<!-- CONTRACT:STATE_TABLE_START -->
| ID | State | Action | Phase |
|----|-------|--------|-------|
| T1 | No architect round-1 result | dispatch_architect round 1 | debate |
| T2 | Architect round 1 done, no adversary | dispatch_adversary round 1 | debate |
| T3 | Adversary done, severity fatal, round < max | dispatch_architect round 2 | debate |
| T4 | Adversary done, severity serious, round < max | dispatch_architect round 2 | debate |
| T5 | Adversary done, severity minor | dispatch_experimenter | experiment |
| T6 | Adversary done, severity none | dispatch_experimenter | experiment |
| T7 | Adversary done, severity unknown, default continue | dispatch_architect round 2 | debate |
| T8 | Adversary done, round = max_rounds (3) | dispatch_experimenter | experiment |
| T9 | Experimenter done, no verdict | dispatch_arbiter | verdict |
| T10 | Verdict exists, post-verdict not done, auto_review true | post_verdict | recording |
| T10B | Verdict exists, post-verdict not done, auto_review false | dispatch_reviewer | recording   |
| T11 | Prompt exists without result | waiting | debate |
<!-- CONTRACT:STATE_TABLE_END -->

## Branching After Verdict

<!-- CONTRACT:VERDICT_TABLE_START -->
| ID | Verdict | Action | Cascade |
|----|---------|--------|---------|
| V1 | PROVEN | complete_proven | false |
| V2 | DISPROVEN | complete_disproven | true |
| V3 | PARTIAL | complete_partial | false |
| V4 | INCONCLUSIVE | complete_inconclusive | false |
<!-- CONTRACT:VERDICT_TABLE_END -->

## External Agent Flow

For agents configured as external:
1. The conductor generates a self-contained prompt.md with all context embedded
2. The user pastes it into an external session (claude.ai, API, etc.)
3. The user saves the response as result.md
4. The conductor detects the file and continues

## Configurable vs Hardcoded

**Configurable** (via `config/orchestration.yaml`):
- Max debate rounds
- Severity keywords and exit conditions
- Post-verdict actions and messages
- Which severity levels continue debate vs exit

**Hardcoded** (in `scripts/orchestration.py`):
- Phase order: dialectic -> refutation -> judgment -> recording
- Debate participants: architect and adversary
- The state machine transition logic
- Context file ordering

To change the hardcoded behavior, modify `detect_state()` in `scripts/orchestration.py`.

## Investigation-Level State Table

<!-- CONTRACT:INVESTIGATION_TABLE_START -->
| ID | Condition | Expected Action | Expected Phase |
|----|-----------|----------------|----------------|
| I1 | No .north-star.md | understand | understand |
| I2 | .north-star.md exists, no .context.md | understand | understand |
| I3 | .north-star.md + .context.md, no survey-*.md | understand | understand |
| I3Q | .north-star.md + .context.md, no survey-*.md, quick=True | scaffold_quick | divide |
| I4 | .north-star.md + .context.md + survey-*.md, no blueprint.md | divide | divide |
| I5 | blueprint.md exists, no claim dirs | scaffold | divide |
| I6 | Claims scaffolded, no architect result | test_claim | test |
| I7 | Claim has verdict, no post-verdict | record_verdict | test |
| I8 | All claims complete, no synthesis.md | synthesize | synthesize |
| I9 | synthesis.md exists | complete | complete |
<!-- CONTRACT:INVESTIGATION_TABLE_END -->
