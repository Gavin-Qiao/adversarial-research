# Orchestration Configuration

`orchestration.yaml` controls how the adversarial research workflow behaves. Changes take effect on the next `/next` or `/investigate` call.

## Fields

### `debate_loop`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sequence` | list | `[thinker, refutor]` | Order within each round. Thinker proposes, refutor attacks. |
| `max_rounds` | int | `3` | Hard cap on debate rounds. After this many rounds, proceed to coder regardless of severity. |
| `final_say` | string | `refutor` | Who gets the last word before the coder phase. |

### `roles`

Each entry defines a role in the pipeline:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Role name (must match an agent file in `agents/`) |
| `type` | string | `debate`, `empirical`, `verdict`, or `bookkeeper` |
| `max_rounds` | int | Max rounds for this role |
| `output_dir` | string | Directory pattern (`round-{round}` or `results`) |
| `files` | list | Expected files (`[prompt.md, result.md]` or `[output.md]`) |
| `exit_condition` | dict | (refutor only) Severity-based exit rules |

#### `exit_condition` (refutor)

| Field | Type | Description |
|-------|------|-------------|
| `field` | string | The field name to look for in the refutor's output (default: `Severity`) |
| `continue_on` | list | Severity values that continue the debate loop (default: `[fatal, serious]`) |
| `exit_on` | list | Severity values that exit to coder (default: `[minor, none]`) |
| `unknown` | string | What to do when severity can't be parsed: `continue` or `exit` (default: `continue`) |

### `phases`

Maps phase names to their roles. Informational — used for display, not for logic.

### `post_verdict`

Defines what happens after each verdict type:

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | `complete` (end sub-unit) or `prompt_user` (ask user for next step) |
| `cascade` | bool | Whether to run falsification cascade (only for FALSIFIED) |
| `message` | string | Displayed to the user |
| `options` | list | (MIXED only) Options presented to the user |

### `severity_keywords`

Fallback keyword detection when the refutor's output doesn't have a structured `Severity:` field. Maps severity levels to lists of phrases to search for in the text.

## Common modifications

**Speed up: skip the debate**
```yaml
debate_loop:
  max_rounds: 1
```
One round of thinker + refutor, then straight to coder.

**Disable adversarial review entirely**

Set `max_rounds: 0` in debate_loop. The state machine will skip directly to coder after the thinker.

**Change severity sensitivity**

To make the refutor more likely to exit early (proceed to coder):
```yaml
exit_condition:
  continue_on: [fatal]        # only fatal continues
  exit_on: [serious, minor, none]  # serious now exits too
```

**Auto-resolve MIXED verdicts**

```yaml
post_verdict:
  MIXED:
    action: complete    # was: prompt_user
    message: "Verdict mixed. Recorded as-is."
```

**Add custom severity phrases**

```yaml
severity_keywords:
  fatal: ["fatal", "blocks the approach", "fundamentally flawed", "impossible"]
  serious: ["serious", "requires modification", "problematic"]
```

## Conductor and orchestration.yaml

The conductor agent is not listed in `orchestration.yaml` because it operates at a different level. The roles in the YAML (thinker, refutor, coder, judge, reviewer) are the agents that get dispatched within a cycle. The conductor is the meta-agent that dispatches them.

The conductor reads `orchestration.yaml` to understand parameters (max_rounds, severity keywords, post-verdict behavior) but follows `config/protocol.md` for routing rules. When using `/next` step-by-step (without the conductor), the state machine in `orchestration.py` reads the same YAML.

## What you CANNOT change via YAML

- The phase order (pre-falsification → falsification → judgment → recording)
- Which roles are in the debate loop (always thinker + refutor)
- The state machine transition logic
- Context file ordering

To change these, edit `scripts/orchestration.py` → `detect_state()`.
