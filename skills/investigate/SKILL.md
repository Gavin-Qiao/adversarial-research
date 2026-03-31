---
name: investigate
description: Run a full adversarial investigation. Takes a research question, uses the investigation state machine to drive each phase. Reports results. Use when the user wants comprehensive automated investigation.
argument-hint: "<research question>"
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
---

# Full Adversarial Investigation

Run a comprehensive investigation from question to verdict, driven by the investigation state machine.

## How It Works

The state machine (`manage.py investigate-next`) decides what phase you're in. You dispatch the appropriate agent, then call `investigate-next` again. Repeat until complete.

## Steps

1. **Initialize** (if not already done):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research build
   ```

2. **Get the current state**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research investigate-next
   ```

3. **Handle the state** based on the `action` field in the JSON output:

   - **`gather_context`**: Dispatch `@researcher` with a broad survey prompt: the research question + "comprehensive literature survey covering existing approaches, open problems, and key results". Save output to `research/context/distillation-<topic>.md`.

   - **`create_framework`**: Dispatch `@deep-thinker` with the research question + all distillation files listed in `distillations`. Tell it to produce a framework with a claim registry (see deep-thinker agent instructions). Save output to `research/framework.md`.

   - **`scaffold_cycles`**: The state includes a `claims` list. For each claim:
     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research scaffold cycle <claim-id>
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research scaffold unit investigation --parent cycles/<cycle-dir>
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research scaffold sub-unit primary --parent cycles/<cycle-dir>/unit-1-investigation
     ```
     Write the claim statement to the sub-unit's `frontier.md` and the falsification criterion to the unit's `frontier.md`.
     After scaffolding, run `manage.py build` to index the new files.

   - **`run_cycle`**: The state includes `cycle` and `sub_unit`. Dispatch `@conductor` with:
     - The sub-unit path
     - The claim from the sub-unit's frontier.md
     - A reference to `config/protocol.md`
     - The assembled context: `manage.py context <sub-unit-path>`

   - **`review_cycle`**: The state includes `cycle` and `sub_unit`. Dispatch `@reviewer` with: "The conductor has completed cycle `<cycle>`. Read the verdict at `<sub-unit>/judge/results/verdict.md` and update everything."

   - **`synthesize`**: Dispatch `@deep-thinker` with all cycle results and verdicts for cross-cycle synthesis. Save to `research/synthesis.md`. Tell it to omit the claim registry (synthesis mode, not framework mode).

   - **`complete`**: Report results. Read `research/synthesis.md` and present:
     - Final synthesis
     - List of settled/falsified/mixed claims
     - Recommendations for next steps
     Run `/adversarial-research:status` to update the frontier.

4. **After each dispatch**, run `manage.py investigate-next` again and go to step 3. Continue until `complete`.

## Claim Registry Verification

After `create_framework`, verify the claim registry parses correctly:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root research parse-framework
```
If this fails, the deep-thinker's output is missing the `# CLAIM_REGISTRY` YAML block. Read `research/framework.md` and manually extract claims, or re-dispatch the deep-thinker with explicit instructions to include the registry.

## Notes

- The conductor follows `config/protocol.md` for routing rules — modify that file to change the workflow.
- The conductor uses the same state machine as `/next` for main-line routing, plus side-channel dispatches for coder checks and researcher lookups.
- All dispatches are logged to the `dispatches` table. View with: `manage.py dispatch-log`
- A clean falsification is a valid, productive result.
