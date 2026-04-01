---
name: design
description: Run a full principia design process. Takes an algorithm design question, uses the design state machine to drive each phase. Reports results. Use when the user wants comprehensive automated algorithm design from first principles.
argument-hint: "<algorithm design question> [--quick]"
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

Run a comprehensive design process from principle to algorithm, driven by the state machine.

## Quick Mode

If the user's input contains `--quick` or the question is a single focused claim:

1. Skip scout survey and synthesizer blueprint phases
2. Scaffold a single claim directly:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design scaffold claim <slugified-question>
   ```
3. Write the user's question as the claim statement into `claim.md`
4. Use `investigate-next --quick` (limits to 1 debate round)
5. Proceed directly to verdict, then generate RESULTS.md

## Steps (Full Mode)

1. **Initialize** (if not already done):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design build
   ```

2. **Get the current state**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design investigate-next
   ```

3. **Handle the state** based on the `action` field in the JSON output:

   - **`gather_context`**: Dispatch `@scout` with a broad survey prompt: the design principle + "comprehensive literature survey covering existing algorithms, open problems, and key results". Save output to `design/context/survey-<topic>.md`.
     Report: `[Phase 1/6] Surveying landscape...`

   - **`create_blueprint`**: Dispatch `@synthesizer` with the design principle + all survey files listed in `distillations`. Tell it to produce a blueprint with a claim registry (see synthesizer agent instructions). Save output to `design/blueprint.md`.
     Report: `[Phase 2/6] Creating blueprint...`

   - **`scaffold_cycles`**: The state includes a `claims` list. For each claim, scaffold using the flat hierarchy:
     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design scaffold claim <claim-id>
     ```
     Write the claim statement to `claim.md`. After scaffolding, run `manage.py build`.
     Report: `[Phase 3/6] Scaffolding N claims...`

   - **`run_cycle`**: The state includes `cycle` and `sub_unit`. Dispatch `@conductor` with:
     - The claim path
     - The claim statement from claim.md (or frontier.md)
     - A reference to `config/protocol.md`
     - The assembled context: `manage.py context <path>`
     Report: `[Phase 4/6] Testing claim: <name> — dispatching @conductor`

   - **`review_cycle`**: Run automated post-verdict bookkeeping:
     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design post-verdict <path>
     ```
     Report: `[Phase 4/6] Recording verdict for <name>`

   - **`compose`**: The state includes `proven_claims`. Dispatch `@experimenter` with all proven claim artifacts. Tell it to compose them into a single cohesive algorithm. Save to `design/composition.md`.
     Report: `[Phase 5/6] Composing algorithm from N proven claims...`

   - **`synthesize`**: Dispatch `@synthesizer` with all cycle results and verdicts for cross-claim synthesis. Save to `design/synthesis.md`. Tell it to omit the claim registry (synthesis mode, not blueprint mode).
     Report: `[Phase 6/6] Synthesizing final design...`

   - **`complete`**: Generate RESULTS.md and report:
     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design results
     ```
     Read `design/RESULTS.md` and present the final design to the user.

4. **After each dispatch**, run `manage.py investigate-next` again and go to step 3. Continue until `complete`.

## Progress Reporting

After each state transition, output a progress line to the user:
- `[Phase N/6] <phase_name>: <description>`
- `[Claim M/K] <claim_name>: <action>`
- `[Verdict] <claim>: PROVEN / DISPROVEN / PARTIAL (confidence)`
- `[Complete] Design process finished. See RESULTS.md.`

## Claim Registry Verification

After `create_blueprint`, verify the claim registry parses correctly:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design parse-framework
```
If this fails, the synthesizer's output is missing the `# CLAIM_REGISTRY` YAML block. Read `design/blueprint.md` and manually extract claims, or re-dispatch the synthesizer with explicit instructions to include the registry.

## Notes

- The conductor follows `config/protocol.md` for routing rules.
- All dispatches are logged. View with: `manage.py dispatch-log`
- A clean disproval is a valid, productive result.
