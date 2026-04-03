<div align="center">

# principia

**Turn a philosophical principle into a working algorithm through rigorous adversarial testing.**

[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](https://github.com/Gavin-Qiao/principia/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-370_passing-brightgreen.svg)]()
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-blueviolet.svg)](https://docs.anthropic.com/en/docs/claude-code)

You start with an insight. Principia decomposes it into testable claims, stress-tests each through structured debate and empirical experiments, and composes the surviving pieces into a design you can build on.

[Installation](#installation) | [Quick Start](#quick-start) | [How It Works](#how-it-works) | [Commands](#commands) | [Configuration](#configuration)

</div>

---

## Installation

```bash
claude plugin install principia
# or
claude --plugin-dir /path/to/principia
```

Requires **Python 3.10+** (stdlib only -- no pip packages at runtime) and **Claude Code 2.0+**.

## Quick Start

```
/principia:init "Topological Enrichment"
/principia:design "Persistent homology captures information that clustering
algorithms discard. An algorithm that preserves topological features during
hierarchical merging should produce more faithful cluster boundaries."
```

That's it. Principia runs four phases automatically:

1. **Understand** -- refine the principle, survey the research landscape
2. **Divide** -- decompose into testable claims with dependency ordering
3. **Test** -- debate (architect vs adversary), then experiment, then verdict -- per claim
4. **Synthesize** -- compose surviving claims into a coherent algorithm

Add `--quick` to skip research, limit debate to 1 round, and get results fast.

## How It Works

```
/principia:design "Your philosophical principle here"

Understand:  Discussion refines principle, @scout surveys the landscape
Divide:      @synthesizer decomposes into testable claims, scaffolds directories
Test:        For each claim (respecting dependency waves):
               @architect proposes  ->  @adversary attacks  (1-3 rounds)
               -> @experimenter tests empirically
               -> @arbiter renders verdict
Synthesize:  @synthesizer composes surviving claims into a unified algorithm
```

After each verdict:

| Verdict | Effect |
|---------|--------|
| **PROVEN** | Claim confirmed. Dependents can proceed. |
| **DISPROVEN** | Hypothesis fails. Dependents are **weakened** via cascade. |
| **PARTIAL** | Holds under conditions. Narrow or gather more evidence. |
| **INCONCLUSIVE** | Insufficient evidence. Try a different approach or defer. |

The adversary always gets the last word before experiments. Anti-convergence protocols detect when agents agree too quickly and inject counter-evidence.

### Walkthrough

<details>
<summary><b>Full walkthrough of a /principia:design run</b></summary>

#### Phase 1: Understand
```
[Phase 1/4] Understanding principle...
```
Discussion refines the principle into a north star. `@scout` searches for prior art. Outputs: `design/.north-star.md`, `design/.context.md`, `design/context/survey-<topic>.md`.

#### Phase 2: Divide
```
[Phase 2/4] Dividing into testable claims...
```
`@synthesizer` decomposes your principle into testable claims with dependency ordering and scaffolds claim directories. Output: `design/blueprint.md` with a claim registry, plus `design/claims/claim-N-name/` directories.

#### Phase 3: Test (repeated per claim)
```
[Phase 3/4] Testing claim: enrichment-preserves-topology
  Round 1: @architect proposes design
  Round 1: @adversary attacks (Severity: Serious)
  Round 2: @architect revises with new framework
  Round 2: @adversary attacks (Severity: Minor) -> exits debate
  @experimenter runs empirical test (AUROC: 0.92)
  Verdict: PROVEN (high confidence)

[Phase 3/4] Testing claim: bottleneck-ratio-bounds...
```

#### Phase 4: Synthesize
```
[Phase 4/4] Synthesizing final design...
[Complete] Design process finished. See design/RESULTS.md.
```

</details>

## Agents

| Agent | Model | Role |
|-------|-------|------|
| `@architect` | Opus | Proposes designs and hypotheses from context |
| `@adversary` | Opus | Stress-tests: finds flaws, counterexamples, edge cases |
| `@experimenter` | Sonnet | Tests empirically with code and synthetic data |
| `@arbiter` | Opus | Evaluates all evidence, renders verdict |
| `@conductor` | Opus | Orchestrates a full claim cycle autonomously |
| `@synthesizer` | Opus | Decomposes principles (Divide) and unifies findings (Synthesize) |
| `@scout` | Sonnet | Surveys the landscape -- prior work, relevant techniques |
| `@deep-thinker` | Opus | Hard math/theory reasoning, available across all four phases |

The architect and adversary have **no codebase access** -- isolated to prevent anchoring bias. The experimenter has full codebase access. The conductor orchestrates agents as subagents. The deep thinker is dispatched on demand for hard theoretical questions.

## Commands

### User commands

| Command | What it does |
|---------|-------------|
| `/principia:init [title]` | Bootstrap a new project with the `design/` directory structure |
| `/principia:design "<principle>" [--quick]` | Full pipeline: principle to algorithm |
| `/principia:step [path]` | Advance one step manually |
| `/principia:status` | Regenerate PROGRESS.md and show current state |
| `/principia:impact <id>` | Preview: what breaks if this claim is disproven? |
| `/principia:query "<sql>"` | Query the evidence database |

### Internal commands (used by agents and skills)

| Command | What it does |
|---------|-------------|
| `/principia:scaffold <level> <name>` | Create directory structure for a claim |
| `/principia:new <path>` | Create a design file with auto-generated frontmatter |
| `/principia:falsify <id> [--by <id>]` | Mark a claim as disproven and cascade to dependents |
| `/principia:settle <id>` | Mark a claim as proven |
| `/principia:validate` | Check design log integrity |
| `/principia:methodology` | Reference: the principia design methodology |

## Configuration

### Autonomy

By default, Principia pauses at each phase transition for confirmation. Set **yolo mode** to run fully automated:

```yaml
# config/orchestration.yaml
autonomy:
  mode: yolo               # checkpoints (default) | yolo
  checkpoint_at: [understand, divide, test, synthesize]
```

In **checkpoints** mode (default): pauses between phases, asks about claim complexity, prompts on non-terminal verdicts. In **yolo** mode: reports progress and continues automatically, treats all claims as atomic, accepts partial/inconclusive results.

### Workflow tuning: `config/orchestration.yaml`

Controls debate round limits, severity thresholds, and post-verdict actions.

```yaml
debate_loop:
  max_rounds: 3          # cap on debate rounds
  final_say: adversary   # who gets last word

severity_keywords:
  fatal: ["fatal", "blocks the approach"]
  minor: ["minor", "worth noting"]

auto_review: true        # automated post-verdict bookkeeping
```

See `config/README.md` for the full reference.

### Dispatch mode: `design/.config.md`

Created by `/principia:init`. Controls agent dispatch mode per project:

- **internal** (default): agents run as Claude Code subagents
- **external**: system generates a self-contained prompt you can paste into any LLM

## State Machine Reference

<details>
<summary><b>Investigation-level transitions</b></summary>

```
understand -> divide -> scaffold -> test_claim/record_verdict -> synthesize -> complete
```

The `test_claim`/`record_verdict` loop repeats for each claim, respecting dependency waves.

</details>

<details>
<summary><b>Claim-level transitions</b></summary>

```
dispatch_architect(1) -> dispatch_adversary(1)
  -> [fatal/serious] dispatch_architect(2) -> dispatch_adversary(2) -> ...
  -> [minor/none OR max_rounds] dispatch_experimenter
    -> dispatch_arbiter -> post_verdict
      -> complete_{proven,disproven,partial,inconclusive}
```

| Field | Description |
|-------|-------------|
| `action` | `dispatch_architect`, `dispatch_adversary`, `dispatch_experimenter`, `dispatch_arbiter`, `post_verdict`, `complete_*`, `waiting`, `error` |
| `phase` | `debate`, `experiment`, `verdict`, `recording`, `complete` |
| `agent` | Which agent to dispatch |
| `round` | Current debate round number |
| `context_files` | Files to include in the agent's prompt |
| `result_path` | Where to save the agent's output |
| `dispatch_mode` | `internal` (subagent) or `external` (prompt file) |

</details>

### Step-by-Step Mode

For manual control, use `/principia:step` to advance one agent at a time:

```
/principia:step     # dispatches architect round 1
/principia:step     # dispatches adversary round 1
/principia:step     # severity check -> architect round 2 or experimenter
...                 # continue to verdict
```

## Directory Structure

```
design/
├── .north-star.md                  # Refined principle
├── .context.md                     # Inspection findings
├── claims/                         # One directory per testable claim
│   └── claim-N-name/
│       ├── architect/round-K/      # Hypothesis proposals
│       ├── adversary/round-K/      # Stress-test attacks
│       ├── experimenter/results/   # Empirical tests
│       ├── arbiter/results/        # Verdicts
│       └── claim.md                # Claim statement + metadata
├── context/                        # Research outputs
├── blueprint.md                    # Claim decomposition plan
├── composition.md                  # Synthesized algorithm
├── synthesis.md                    # Cross-claim analysis
├── RESULTS.md                      # Final summary
├── PROGRESS.md                     # Auto-generated progress
└── FOUNDATIONS.md                   # Tracked assumptions
```

## Frontmatter Schema

```yaml
---
id: <auto-derived from path>
type: claim | assumption | evidence | reference | verdict | question
status: pending | active | proven | disproven | partial | weakened | inconclusive
date: YYYY-MM-DD
depends_on: [claim-id, ...]
assumes: [assumption-id, ...]
maturity: theorem-backed | supported | conjecture | experiment
confidence: high | moderate | low
---
```

## Glossary

| Term | Definition |
|------|-----------|
| **Claim** | A testable assertion decomposed from the user's principle. Each gets its own adversarial cycle. |
| **Blueprint** | The synthesizer's decomposition of a principle into claims with dependency ordering. |
| **Verdict** | The outcome of an adversarial cycle: PROVEN, DISPROVEN, PARTIAL, or INCONCLUSIVE. |
| **Cascade** | When a claim is disproven, dependents have their confidence reduced automatically. |
| **Wave** | A set of claims with no mutual dependencies that can be investigated in parallel. |
| **Severity** | The adversary's rating: Fatal, Serious, Minor, or None. Determines debate continuation. |
| **Maturity** | Claim establishment level: theorem-backed, supported, conjecture, or experiment. |
| **Falsification** | Pre-registered criterion that would disprove a claim. Written by the synthesizer. |
| **Anti-convergence** | Protocol to detect and prevent agents from agreeing too quickly. |

## Development

```bash
uv sync --dev                          # install dev dependencies
uv run python -m pytest tests/ -q      # 370 tests
uv run ruff check scripts/ tests/      # lint
uv run python -m mypy scripts/         # type check
```

## License

MIT
