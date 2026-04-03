---
name: design
description: Run a full principia design process through 4 phases (Understand > Divide > Test > Synthesize). Takes an algorithm design principle, uses the investigation state machine to drive each phase. Use when the user wants comprehensive automated algorithm design from first principles.
argument-hint: "<algorithm design principle> [--quick]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
---

# Full Principia Design Process

Run a 4-phase design process from principle to algorithm.

```
Understand  ->  Divide  ->  Test  ->  Synthesize
```

## Quick Mode

If the user's input contains `--quick` or the question is a single focused claim:

1. **Understand**: Skip Research (no scout). Brief discussion (1-2 questions max). Inspection runs.
2. **Divide**: Scaffold single claim directly (skip synthesizer decomposition):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design scaffold claim <slugified-question>
   ```
3. **Test**: 1 debate round, then experimenter, then verdict.
4. **Synthesize**: Generate RESULTS.md directly.

Use `investigate-next --quick` throughout.

## Steps (Full Mode)

0. **Pre-check**: If `design/` directory does not exist, tell the user: "No design project found. Run `/principia:init` first to set up the project structure."

1. **Initialize** (if not already done):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design build
   ```

2. **Get the current state**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design investigate-next
   ```
   Print the `breadcrumb` field to show the user where they are.

3. **Handle the state** based on the `action` field:

### Phase 1: Understand

**Action: `understand`**

The state includes a `substeps` list of remaining sub-steps. Handle each in order:

**Sub-step: `discuss`** — Adaptive pushback on the user's principle.
- Read the user's principle (from the argument or existing context)
- Adapt to confidence level:
  - **Certain**: Challenge — "What about X? Have you considered Y?"
  - **Exploratory**: Collaborate — "Interesting. Let me check what exists..."
  - **Vague**: Focus — "Better how? Accuracy? Speed? Robustness?"
- May dispatch `@scout` to verify user's claims or map the space
- May dispatch `@deep-thinker` if hard mathematical relationships are involved
- Write refined principle to `design/.north-star.md`
- Report: `[Understand > Discussion] Refining principle...`

**Sub-step: `inspect`** — Scan codebase and prior sessions.
- Use Read/Glob/Grep/Bash directly (no agent dispatch):
  - Current codebase for relevant implementations
  - Prior principia sessions (`design/` directories from past runs)
  - Git history for related work
- Write findings to `design/.context.md`
- Report: `[Understand > Inspection] Scanning codebase...`

**Sub-step: `research`** — Deep literature review.
- Dispatch `@scout` with: principle + context + "comprehensive literature survey"
- Read scout output. Identify follow-up questions.
- Dispatch `@scout` again for follow-ups (iterative).
- May dispatch `@deep-thinker` if papers reveal hard theoretical questions.
- Save to `design/context/survey-<topic>.md` and `design/context/comparison-<topic>.md`
- Report: `[Understand > Research] Surveying literature...`

**Phase transition**: After all sub-steps complete, ask the user:
"Ready to decompose into testable claims, or want to research more?"
If user wants more research, dispatch `@scout` again. When user confirms, run `investigate-next` to get the next state.

### Phase 2: Divide

**Action: `divide`**
- Dispatch `@synthesizer` with all files in `context_files` from the state JSON
- Tell synthesizer to produce `blueprint.md` with a claim registry (3-7 claims)
- Verify registry parses:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design parse-framework
  ```
- If decomposition involves hard math, dispatch `@deep-thinker`, then re-dispatch `@synthesizer` with the analysis
- Report: `[Divide] Decomposing into testable claims...`

**Action: `scaffold`**
- For each claim in the `claims` list, scaffold:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design scaffold claim <claim-id>
  ```
- Write the claim statement to `claim.md`
- After scaffolding, run `manage.py build`
- For each claim, show the user: claim statement, maturity, dependencies, falsification criterion
- Ask: "Investigate deeper (spawn sub-investigation) or treat as atomic?"
- If deeper: spawn child principia (see Recursive Structure below)
- Report: `[Divide > Scaffold] Scaffolding N claims...`

**Action: `scaffold_quick`** (quick mode only)
- Scaffold a single claim directly from the principle:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design scaffold claim <slugified-principle> \
    --statement "<principle>" --falsification "<user-provided or auto-generated>"
  ```
- Write the principle as the claim statement
- Skip blueprint creation entirely
- Report: `[Divide > Quick Scaffold] Single claim created`

### Phase 3: Test

**Action: `test_claim`**
- The state includes `cycle` (claim name) and `sub_unit` (path)
- Read `.config.md` to check dispatch mode for the conductor
- If **internal**: Dispatch `@conductor` with the claim path, claim statement, and reference to `config/protocol.md`
- If **external**: Generate conductor prompt with `manage.py prompt <path>` and tell user to paste result
- Report: `[Test > <claim>] Dispatching @conductor`

**Action: `record_verdict`**
- Run post-verdict bookkeeping:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design post-verdict <path>
  ```
- Report the verdict to the user with breadcrumb
- Report: `[Test > <claim>] Verdict: <VERDICT> (confidence: <level>)`

**Handling non-terminal verdicts:**

When `investigate-next` returns a claim with `complete_partial` or `complete_inconclusive` action:
- Present the options from the state JSON's `suggestion.options` via AskUserQuestion:
  - **PARTIAL**: "Narrow the claim (add conditions)", "Gather more experimental evidence", "Accept partial result and move on"
  - **INCONCLUSIVE**: "Try a different approach", "Gather more evidence", "Defer and move to next claim"
- Based on user choice: create a narrowed claim (scaffold new claim), re-dispatch experimenter, or mark as accepted and continue.
- In YOLO mode: accept partial/inconclusive results and continue to next claim.

### Phase 4: Synthesize

**Action: `synthesize`**
- The state includes `completed_cycles` and `proven_claims`
- If proven claims exist:
  1. Dispatch `@synthesizer` with all verdicts, debate transcripts, experimental results, and north star
  2. Synthesizer produces `design/composition.md` (algorithm) and `design/synthesis.md` (cross-claim analysis)
  3. If conflicting verdicts need mathematical reconciliation, dispatch `@deep-thinker`, then re-dispatch `@synthesizer`
- If no proven claims:
  1. Dispatch `@synthesizer` to produce only `design/synthesis.md` (analysis of what was disproven and why)
- Generate RESULTS.md:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design results
  ```
- Read `design/RESULTS.md` and present the final design to the user
- Report: `[Synthesize] Composing final design from N proven claims...`

**Action: `complete`**
- Read and present `design/RESULTS.md`
- Report: `[Complete] Design process finished. See RESULTS.md.`

### Autonomy

Before transitioning between phases (Understand → Divide → Test → Synthesize), check autonomy config in `design/.config.md`:

- **checkpoints mode** (default): At each phase transition listed in `checkpoint_at`, pause and ask the user: "[Phase] complete. Continue to [next phase]?" Show a summary of what was accomplished.
- **yolo mode**: Report what happened at each phase transition but continue automatically without waiting for user input.

To change mode, edit `design/.config.md` and set Mode to `yolo`.

4. **After each action**, run `manage.py investigate-next` again and go to step 3. Continue until `complete`.

## Dispatch Mode

Read `design/.config.md` before each agent dispatch. For each agent:
- **internal**: Dispatch as Claude Code subagent via `@agent-name`
- **external**: Run `manage.py prompt <path>` to generate a self-contained prompt. Tell user: "Prompt written to `<path>`. Copy it to your preferred tool, then paste the result back."

When user pastes a result for external dispatch:
1. Validate with: `manage.py validate-paste --agent <name> --file <path>`
2. If valid: save to the correct `result_path` and continue
3. If invalid: tell the user what's wrong and ask to re-paste

## Recursive Structure

When a claim in the Divide phase is marked as complex (user chooses "investigate deeper"):
1. Create a child investigation: `design/claims/claim-N-name/design/`
2. Copy parent's `.north-star.md` and `.context.md` into the child `design/` directory
3. The child runs through all 4 phases independently
4. Child's verdict feeds back into parent's Test phase for that claim

## Progress Reporting

After each state transition, output the breadcrumb from the JSON state:
```
[Phase > Sub-location] What happened.
  Next: <next action>
  North star: "<principle>"
```

## Notes

- The conductor follows `config/protocol.md` for routing rules
- All dispatches are logged via `manage.py log-dispatch`
- A clean disproval is a valid, productive result
- Deep Thinker is available in ALL phases but only for specific mathematical/theoretical questions
- Scout and Experimenter are available in Understand and Test phases only
