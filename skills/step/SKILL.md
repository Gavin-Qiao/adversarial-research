---
name: step
description: Advance the design workflow by one step. Determines what comes next in the current sub-unit and dispatches the appropriate agent. Run without arguments to auto-detect the active sub-unit. Use when the user asks "what's next", wants to continue the design process, or after pasting external agent results.
argument-hint: [sub-unit-path]
allowed-tools:
  - Bash
  - Read
  - Glob
  - Agent
  - Write
  - AskUserQuestion
---

# Advance Design Workflow

Determine the next step and dispatch the appropriate agent.

## Steps

1. **Get state** by running:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design next $ARGUMENTS
   ```
   If no argument provided, the command auto-detects the active sub-unit.
   Parse the JSON output.

2. **Handle the state**:

   - **`waiting`**: Tell the user what file is missing: "Waiting for `{waiting_for}` -- paste the external result into `{result_path}` and run `/step` again."

   - **`dispatch_architect`**: Get the assembled context:
     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design context <sub_unit>
     ```
     If `dispatch_mode` is `internal`: Dispatch `@architect` with the context as the prompt. Save the result to `result_path`.
     If `dispatch_mode` is `external`: Run `manage.py prompt <sub_unit>` and tell the user where the prompt file was written.

   - **`dispatch_adversary`**: Same pattern as architect. Get context, dispatch `@adversary` or generate external prompt.

   - **`dispatch_experimenter`**: Get context, dispatch `@experimenter` or generate external prompt.

   - **`dispatch_arbiter`**: This is the ONE step that needs LLM preparation. Before dispatching:
     1. Read all context files listed in the state JSON
     2. Prepare a **structured arbiter brief** summarizing:
        - The claim (architect's final design proposal, 2-3 sentences)
        - Key disagreement between architect and adversary
        - Strongest argument FOR the claim
        - Strongest argument AGAINST the claim
        - Empirical evidence and whether pre-registered criteria were met
        - Unresolved points
     3. Write the brief to `<sub_unit>/arbiter/brief.md`
     4. Dispatch `@arbiter` with: "Read the brief at `<path>`, then read individual evidence files if you need more detail."
     5. Save the verdict to `result_path`

   - **`post_verdict`**: Run automated post-verdict bookkeeping:
     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" --root design post-verdict <sub_unit>
     ```
     Parse the JSON output and report the verdict and changes to the user. Then run `manage.py next <sub_unit>` to advance.

   - **`dispatch_reviewer`** (only when `auto_review: false` in orchestration.yaml): Run `manage.py post-verdict <sub_unit>` to apply post-verdict bookkeeping.

   - **`complete_proven`**: Report: "Sub-unit proven." Show the suggestion from state JSON.
   - **`complete_disproven`**: Report: "Design proposal disproven. Cascade applied." Show suggestions.
   - **`complete_partial`**: Report: "Verdict partial -- claim partially true under some conditions." Use AskUserQuestion to present the options from state JSON and let the user choose.
   - **`complete_inconclusive`**: Report: "Verdict inconclusive -- insufficient evidence either way." Use AskUserQuestion to present the options from state JSON and let the user choose.

   - **`severity: unknown`** in state: Read the adversary's result file yourself and assess: does the attack represent a fatal flaw, a serious concern, or a minor issue? Then decide whether to continue the debate (dispatch architect) or proceed to experimenter.

   - **`error` or `unknown`**: Tell the user the state couldn't be determined and ask what they want to do.

3. **After dispatching an internal agent**: Once the agent returns its result, save it to `result_path`. Then run `manage.py next <sub_unit>` again to check if there's an immediate next step (e.g., post-verdict after arbiter). If there is, continue dispatching. If the state is `complete_*` or `waiting`, stop and report.

## Conductor Mode

If a conductor is running the cycle, you may see files appearing from the conductor's subagent dispatches. The state machine still works -- it reads the files the conductor wrote. If the conductor was interrupted, `/step` picks up from the last saved file.

To run a full cycle with the conductor instead of step-by-step:
```
@conductor "Run cycle on [claim] following config/protocol.md"
```

## Important

- For rounds 2+, include in the architect's prompt: "You MUST shift theoretical framework, not just patch your previous proposal."
- For the adversary, include adversarial priming: "Before reading the proposal, identify common failure modes in this domain."
- Always tell the user what phase they're in (debate, experiment, verdict, recording, complete).
- The orchestration rules are in `config/orchestration.yaml` -- users can modify round limits, severity keywords, and post-verdict behavior there.
