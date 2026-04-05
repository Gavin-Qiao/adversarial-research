---
name: step
description: Advance the design workflow by one step. Determines what comes next and dispatches the appropriate agent. Run without arguments to auto-detect. Supports paste-into-chat for external agent results. Use when the user asks "what's next", wants to continue, or after pasting external results.
argument-hint: [claim-path]
allowed-tools:
  - Bash
  - Read
  - Glob
  - Agent
  - Write
  - AskUserQuestion
---

# Advance Design Workflow

Determine the next step and dispatch the appropriate agent. Supports both internal dispatch and paste-into-chat for external tools.

## Steps

0. **Pre-check**: If `design/` directory does not exist, tell the user: "No design project found. Run `/principia:init` first to set up the project structure."

1. **Determine scope**: If arguments reference a specific claim path, use per-claim mode. Otherwise, use investigation-level mode.

   **Investigation-level** (no specific claim):
   ```bash
   uv run python -m principia.cli.manage --root design investigate-next
   ```
   Print the `breadcrumb` from the JSON output. Handle the action per the design skill's phase documentation (understand sub-steps, divide, test, synthesize).

   **Per-claim** (specific claim path provided):
   ```bash
   uv run python -m principia.cli.manage --root design next $ARGUMENTS
   ```
   Parse the JSON output and handle the per-claim state:

2. **Handle per-claim states**:

   - **`waiting`**: Tell the user what file is missing: "Waiting for `{waiting_for}` — paste the external result and run `/step` again."

   - **`dispatch_architect`**: Get context:
     ```bash
     uv run python -m principia.cli.manage --root design context <claim-path>
     ```
     Check `dispatch_mode`:
     - **internal**: Dispatch `@architect` with the context. Save result to `result_path`.
     - **external**: Run `uv run python -m principia.cli.manage --root design prompt <claim-path>` and tell user where the prompt file was written. Tell user to paste the result back.

   - **`dispatch_adversary`**: Same as architect. For rounds 2+, the context automatically includes previous attacks.

   - **`dispatch_experimenter`**: Same dispatch pattern. Context includes the falsification criterion from `claim.md`.

   - **`dispatch_arbiter`**: In `/step` mode, this dispatches the standalone @arbiter (not the conductor). Before dispatching:
     1. Read all context files from state JSON
     2. Prepare a structured arbiter brief:
        - The claim (architect's final design, 2-3 sentences)
        - Key disagreement between architect and adversary
        - Strongest argument FOR and AGAINST
        - Empirical evidence and pre-registered criteria status
        - Unresolved points
     3. Write brief to `<claim-path>/arbiter/brief.md`
     4. Dispatch `@arbiter` with: "Read the brief at `<path>`, then read individual evidence files if needed."
     5. Save verdict to `result_path`

   - **`dispatch_reviewer`** (only when `auto_review: false` in orchestration.yaml): The system expects manual review before post-verdict bookkeeping. Review the verdict at `<claim-path>/arbiter/results/verdict.md`, then run post-verdict manually:
     ```bash
     uv run python -m principia.cli.manage --root design post-verdict <claim-path>
     ```

   - **`post_verdict`**: Run bookkeeping:
     ```bash
     uv run python -m principia.cli.manage --root design post-verdict <claim-path>
     ```

   - **`complete_proven`**: Report: "Claim proven (confidence: X)." Show suggestion.
   - **`complete_disproven`**: Report: "Claim disproven. Cascade applied." Show what was weakened.
   - **`complete_partial`** / **`complete_inconclusive`**: Check autonomy mode:
     ```bash
     uv run python -m principia.cli.manage --root design autonomy-config
     ```
     - **Checkpoints mode**: Present options from state JSON via AskUserQuestion.
     - **Yolo mode**: Accept the result automatically. Report the verdict and continue.

   - **`severity: unknown`**: Read adversary's result yourself and assess severity. Decide whether to continue debate or proceed to experimenter.

   - **`error`**: Tell user and ask what they want to do.

3. **After dispatch**: Save result to `result_path`. Run `uv run python -m principia.cli.manage --root design next <claim-path>` again. If there's an immediate next step, continue. If `complete_*` or `waiting`, stop and report.

## Handling Pasted Results

When the user pastes text that looks like an agent result (contains sections like "Severity:", "Verdict:", "Key Findings:", etc.):

1. Determine which agent the paste is for (check what the current `waiting` state expects, or ask)
2. Save paste to a temp file
3. Validate:
   ```bash
   uv run python -m principia.cli.manage --root design validate-paste --agent <name> --file <temp-path>
   ```
4. If valid: copy to the correct `result_path` and continue workflow
5. If invalid: report what's wrong — "This doesn't look like a valid {agent} result. Missing: {sections}. Please re-paste or switch to internal dispatch."

## Breadcrumb Output

Always show the user where they are. For investigation-level states, use the `breadcrumb` from `investigate-next`. For per-claim states, format:

```
[Test > <claim-name> > Debate R<N>] <action description>
  Next: <what comes after this>
  North star: "<principle>"
```

## Important

- For rounds 2+: include "You MUST shift theoretical framework, not just patch" in architect prompt
- For adversary: include adversarial priming and previous attacks
- Always tell the user what phase they're in
- The conductor uses `config/protocol.md` for routing; `/step` mode follows the state machine directly
