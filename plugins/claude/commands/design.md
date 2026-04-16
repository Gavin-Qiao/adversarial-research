---
description: Run the full 4-phase principia design pipeline (Understand → Divide → Test → Synthesize) from a principle.
argument-hint: "\"<principle>\" [--quick]"
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
   ${CLAUDE_PLUGIN_ROOT}/scripts/pp scaffold claim <slugified-question>
   ```
3. **Test**: 1 debate round, then experimenter, then verdict.
4. **Synthesize**: Generate RESULTS.md directly.

Use `investigate-next --quick` throughout.

## Steps (Full Mode)

0. **Pre-check**: If no principia workspace exists, tell the user: "No Principia project found. Run `/principia:init` first to set up the project structure."

1. **Initialize** (if not already done):
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/pp build
   ```

2. **Get the current state**:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/pp investigate-next
   ```
   Print the `breadcrumb` field to show the user where they are.

3. **Handle the state** based on the `action` field:

### Phase 1: Understand

**Action: `understand`**

The state includes a `substeps` list of remaining sub-steps. Handle each in order:

**Sub-step: `discuss`** — Interactive refinement of the user's principle.
- Read the user's principle (from the argument or existing context)
- **Keep discussing until the principle is specific enough to decompose into testable claims.** Do not write `.north-star.md` until you have a clear, falsifiable direction.
- Adapt to confidence level:
  - **Certain**: Challenge — "What about X? Have you considered Y?"
  - **Exploratory**: Collaborate — "Interesting. Let me check what exists..."
  - **Vague**: Focus — ask pointed questions: "What property are you trying to preserve?", "What would convince you this doesn't work?", "What's the mechanism — why should this be true?"
- A principle is ready when it identifies: a **mechanism** (how/why it works), a **context** (where it applies), and a **direction that could be wrong** (falsifiable).
- May dispatch `@scout` to verify user's claims or map the space
- May dispatch `@deep-thinker` if hard mathematical relationships are involved
- Write refined principle to `principia/.north-star.md`
- Report: `[Understand > Discussion] Refining principle...`

**Sub-step: `inspect`** — Scan codebase and prior sessions.
- Use Read/Glob/Grep/Bash directly (no agent dispatch):
  - Current codebase for relevant implementations
  - Prior principia sessions (`principia/` directories from past runs)
  - Git history for related work
- Write findings to `principia/.context.md`
- Report: `[Understand > Inspection] Scanning codebase...`

**Sub-step: `research`** — Deep literature review.
- Dispatch `@scout` with: principle + context + "comprehensive literature survey"
- Read scout output. Identify follow-up questions.
- Dispatch `@scout` again for follow-ups (iterative).
- May dispatch `@deep-thinker` if papers reveal hard theoretical questions.
- Save to `principia/context/survey-<topic>.md` and `principia/context/comparison-<topic>.md`
- Report: `[Understand > Research] Surveying literature...`

**Phase transition**: After all sub-steps complete:
- **Checkpoints mode**: Ask the user: "Ready to decompose into testable claims, or want to research more?" If user wants more research, dispatch `@scout` again.
- **Yolo mode**: Report "[Understand] Complete. Proceeding to Divide." and continue automatically.

When ready, run `${CLAUDE_PLUGIN_ROOT}/scripts/pp investigate-next` to get the next state.

### Phase 2: Divide

**Action: `divide`**
- Dispatch `@synthesizer` with all files in `context_files` from the state JSON
- Tell synthesizer to produce `blueprint.md` with a claim registry (3-7 claims)
- Verify registry parses:
  ```bash
  ${CLAUDE_PLUGIN_ROOT}/scripts/pp parse-framework
  ```
- If decomposition involves hard math, dispatch `@deep-thinker`, then re-dispatch `@synthesizer` with the analysis
- Report: `[Divide] Decomposing into testable claims...`

**Action: `scaffold`**
- For each claim in the `claims` list, scaffold:
  ```bash
  ${CLAUDE_PLUGIN_ROOT}/scripts/pp scaffold claim <claim-id>
  ```
- Write the claim statement to `claim.md`
- After scaffolding, run `${CLAUDE_PLUGIN_ROOT}/scripts/pp build`
- For each claim, show the user: claim statement, maturity, dependencies, falsification criterion
- **Checkpoints mode**: Ask: "Investigate deeper (spawn sub-investigation) or treat as atomic?"
  - If deeper: spawn child principia (see Recursive Structure below)
- **Yolo mode**: Treat all claims as atomic automatically. Report "[Divide > Scaffold] Treating N claims as atomic."
- Report: `[Divide > Scaffold] Scaffolding N claims...`

**Action: `scaffold_quick`** (quick mode only)
- Scaffold a single claim directly from the principle:
  ```bash
  ${CLAUDE_PLUGIN_ROOT}/scripts/pp scaffold claim <slugified-principle> \
    --statement "<principle>" --falsification "<user-provided or auto-generated>"
  ```
- Write the principle as the claim statement
- Skip blueprint creation entirely
- Report: `[Divide > Quick Scaffold] Single claim created`

### Phase 3: Test

**Claim iteration loop**: `investigate-next` returns one claim at a time. After each claim completes, call `investigate-next` again. Repeat until the action is no longer `test_claim` or `record_verdict`.

**Action: `test_claim`**
- The state includes `cycle` (claim name) and `sub_unit` (claim path)
- Get config path via `${CLAUDE_PLUGIN_ROOT}/scripts/pp paths --json` and read the `config` field to check dispatch mode for the conductor
- If **internal**: Dispatch `@conductor` with the claim path, claim statement, and reference to `config/protocol.md`
- If **external**: Generate conductor prompt with `${CLAUDE_PLUGIN_ROOT}/scripts/pp prompt <path>` and tell user to paste result
- After conductor completes, call `${CLAUDE_PLUGIN_ROOT}/scripts/pp investigate-next` again (it will return `record_verdict`)
- Report: `[Test > <claim>] Dispatching @conductor`

**Action: `record_verdict`**
- Run post-verdict bookkeeping:
  ```bash
  ${CLAUDE_PLUGIN_ROOT}/scripts/pp post-verdict <path>
  ```
- Report the verdict to the user with breadcrumb
- Call `${CLAUDE_PLUGIN_ROOT}/scripts/pp investigate-next` again — if more claims remain, it returns the next `test_claim`
- **Continue the loop** until `investigate-next` returns `synthesize` or `complete`
- Report: `[Test > <claim>] Verdict: <VERDICT> (confidence: <level>)`

**Handling non-terminal verdicts:**

When `investigate-next` returns a claim with `complete_partial` or `complete_inconclusive` action:
- **Checkpoints mode**: Present the options from the state JSON's `suggestion.options` via AskUserQuestion:
  - **PARTIAL**: "Narrow the claim (add conditions)", "Gather more experimental evidence", "Accept partial result and move on"
  - **INCONCLUSIVE**: "Try a different approach", "Gather more evidence", "Defer and move to next claim"
  - Based on user choice: create a narrowed claim (scaffold new claim), re-dispatch experimenter, or mark as accepted and continue.
- **Yolo mode**: Accept partial/inconclusive results automatically. Report the verdict and continue to next claim.

### Phase 4: Synthesize

**Action: `synthesize`**
- The state includes `completed_cycles` and `proven_claims`
- If proven claims exist:
  1. Dispatch `@synthesizer` with all verdicts, debate transcripts, experimental results, and north star
  2. Synthesizer produces `principia/composition.md` (algorithm) and `principia/synthesis.md` (cross-claim analysis)
  3. If conflicting verdicts need mathematical reconciliation, dispatch `@deep-thinker`, then re-dispatch `@synthesizer`
- **Quick mode**: Dispatch `@synthesizer` to produce only `principia/synthesis.md` (skip `composition.md`)
- If no proven claims:
  1. Dispatch `@synthesizer` to produce only `principia/synthesis.md` (analysis of what was disproven and why)
- Generate RESULTS.md:
  ```bash
  ${CLAUDE_PLUGIN_ROOT}/scripts/pp results
  ```
- Read `principia/RESULTS.md` and present the final design to the user
- Report: `[Synthesize] Composing final design from N proven claims...`

**Action: `complete`**
- Read and present `principia/RESULTS.md`
- Report: `[Complete] Design process finished. See RESULTS.md.`

### Autonomy

At the start of the design process, check the autonomy mode:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/pp autonomy-config
```
This returns JSON: `{"mode": "checkpoints", "checkpoint_at": [...]}`. Cache the result for the session.

- **checkpoints** (default): At each phase transition listed in `checkpoint_at`, pause and ask the user: "[Phase] complete. Continue to [next phase]?" Show a summary of what was accomplished. Also ask for user input on claim complexity and non-terminal verdicts.
- **yolo**: Report what happened at each phase transition but continue automatically without waiting for user input. Treat all claims as atomic. Accept partial/inconclusive verdicts and move on.

Throughout this command, actions marked "Checkpoints mode" or "Yolo mode" depend on this setting. To change mode, edit `config/orchestration.yaml` and set `autonomy.mode` to `yolo`.

4. **After each action**, run `${CLAUDE_PLUGIN_ROOT}/scripts/pp investigate-next` again and go to step 3. Continue until `complete`.

## Dispatch Mode

Get the config file path via `${CLAUDE_PLUGIN_ROOT}/scripts/pp paths --json` (use the `config` field) and read it before each agent dispatch. For each agent:
- **internal**: Dispatch as Claude Code subagent via `@agent-name`
- **external**: Run `${CLAUDE_PLUGIN_ROOT}/scripts/pp prompt <path>` to generate a self-contained prompt. Tell user: "Prompt written to `<path>`. Copy it to your preferred tool, then paste the result back."

When user pastes a result for external dispatch:
1. Validate with: `${CLAUDE_PLUGIN_ROOT}/scripts/pp validate-paste --agent <name> --file <path>`
2. If valid: save to the correct `result_path` and continue
3. If invalid: tell the user what's wrong and ask to re-paste

## Recursive Structure

When a claim in the Divide phase is marked as complex (user chooses "investigate deeper"):
1. Create a child investigation: `principia/claims/claim-N-name/principia/`
2. Copy parent's `.north-star.md` and `.context.md` into the child `principia/` directory
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
- All dispatches are logged via `${CLAUDE_PLUGIN_ROOT}/scripts/pp log-dispatch`
- A clean disproval is a valid, productive result
- Deep Thinker is available in ALL phases but only for specific mathematical/theoretical questions
- Scout and Experimenter are available in Understand and Test phases only
