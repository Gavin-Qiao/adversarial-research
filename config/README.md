# Orchestration Configuration

`orchestration.yaml` controls how the principia design workflow behaves. Changes take effect on the next `/principia:step` or `/principia:design` call.

## Fields

### `debate_loop`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sequence` | list | `[architect, adversary]` | Order within each round. Architect proposes, adversary attacks. |
| `max_rounds` | int | `3` | Hard cap on debate rounds. After this many rounds, proceed to experimenter regardless of severity. |
| `final_say` | string | `adversary` | Who gets the last word before the experiment phase. |

### `roles`

Each entry defines a role in the pipeline:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Role name (must match an agent file in `agents/`) |
| `type` | string | `debate`, `empirical`, or `verdict` |
| `max_rounds` | int | Max rounds for this role |
| `output_dir` | string | Directory pattern (`round-{round}` or `results`) |
| `files` | list | Expected files (`[prompt.md, result.md]` or `[output.md]`) |
| `exit_condition` | dict | (adversary only) Severity-based exit rules |

#### `exit_condition` (adversary)

| Field | Type | Description |
|-------|------|-------------|
| `field` | string | The field name to look for in the adversary's output (default: `Severity`) |
| `continue_on` | list | Severity values that continue the debate loop (default: `[fatal, serious]`) |
| `exit_on` | list | Severity values that exit to experimenter (default: `[minor, none]`) |
| `unknown` | string | What to do when severity can't be parsed: `continue` or `exit` (default: `continue`) |

### `phases`

Maps phase names to their roles. Informational — used for display, not for logic.

### `post_verdict`

Defines what happens after each verdict type:

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | `complete` (end cycle) or `prompt_user` (ask user for next step) |
| `cascade` | bool | Whether to run impact cascade (only for DISPROVEN) |
| `message` | string | Displayed to the user |
| `options` | list | (PARTIAL/INCONCLUSIVE) Options presented to the user |

### `severity_keywords`

Fallback keyword detection when the adversary's output doesn't have a structured `Severity:` field. Maps severity levels to lists of phrases to search for in the text.

## Common modifications

**Speed up: skip the debate**
```yaml
debate_loop:
  max_rounds: 1
```
One round of architect + adversary, then straight to experimenter.

**Disable adversarial review entirely**

Set `max_rounds: 0` in debate_loop. The state machine will skip directly to experimenter after the architect.

**Change severity sensitivity**

To make the adversary more likely to exit early (proceed to experimenter):
```yaml
exit_condition:
  continue_on: [fatal]             # only fatal continues
  exit_on: [serious, minor, none]  # serious now exits too
```

**Auto-resolve PARTIAL verdicts**

```yaml
post_verdict:
  PARTIAL:
    action: complete    # was: prompt_user
    message: "Verdict partial. Recorded as-is."
```

## Conductor and orchestration.yaml

The conductor agent is not listed in `orchestration.yaml` because it operates at a different level. The roles in the YAML (architect, adversary, experimenter, arbiter) are the agents that get dispatched within a cycle. The conductor is the meta-agent that dispatches them.

The conductor reads `orchestration.yaml` to understand parameters (max_rounds, severity keywords, post-verdict behavior) but follows `config/protocol.md` for routing rules. When using `/principia:step` (without the conductor), the state machine in `orchestration.py` reads the same YAML.

## What you CANNOT change via YAML

- The phase order (debate → experiment → verdict)
- Which roles are in the debate loop (always architect + adversary)
- The state machine transition logic
- Context file ordering

To change these, edit `scripts/orchestration.py` → `detect_state()`.
