# principia

Turn a philosophical principle into a working algorithm through rigorous adversarial testing.

You start with an insight. Principia decomposes it into testable claims, stress-tests each through structured debate and empirical experiments, and composes the surviving pieces into a design you can build on.

## Installation

```bash
claude plugin install principia
# or
claude --plugin-dir /path/to/principia
```

## Quick Start

```
/principia:init "Topological Enrichment"
/principia:design "Persistent homology captures information that clustering
algorithms discard. An algorithm that preserves topological features during
hierarchical merging should produce more faithful cluster boundaries."
```

That's it. Principia will:
1. **Understand** the principle and research landscape
2. **Divide** your principle into testable claims
3. **Test** each claim: debate (architect vs adversary) then experiment, render verdicts
4. **Synthesize** surviving claims into a coherent design

## Walkthrough

Here's what a `/principia:design` run looks like end-to-end:

### Phase 1: Understand
```
[Phase 1/4] Understanding principle...
```
Discussion refines the principle into a north star. @scout searches for prior art. Outputs: `design/.north-star.md`, `design/.context.md`, `design/context/survey-<topic>.md`.

### Phase 2: Divide
```
[Phase 2/4] Dividing into testable claims...
```
@synthesizer decomposes your principle into testable claims with dependency ordering and scaffolds claim directories. Output: `design/blueprint.md` containing a claim registry, plus `design/claims/claim-N-name/` directories.

### Phase 3: Test (repeated per claim)
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

### Phase 4: Synthesize
```
[Phase 4/4] Synthesizing final design...
[Complete] Design process finished. See design/RESULTS.md.
```

Use `--quick` to skip research, run a brief discussion, 1 debate round per claim, and generate RESULTS.md directly.

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

### Internal commands (used by agents and other skills)

| Command | What it does |
|---------|-------------|
| `/principia:scaffold <level> <name>` | Create directory structure for a claim |
| `/principia:new <path>` | Create a design file with auto-generated frontmatter |
| `/principia:falsify <id> [--by <id>]` | Mark a claim as disproven and cascade to dependents |
| `/principia:settle <id>` | Mark a claim as proven |
| `/principia:validate` | Check design log integrity |
| `/principia:methodology` | Reference: the principia design methodology |

## Agents

| Agent | Model | Role |
|-------|-------|------|
| `@scout` | Sonnet | Surveys the landscape -- prior work, relevant techniques |
| `@architect` | Opus | Proposes designs and hypotheses from context |
| `@adversary` | Opus | Stress-tests: finds flaws, counterexamples, edge cases |
| `@synthesizer` | Opus | Unifies findings across claims into coherent design |
| `@experimenter` | Sonnet | Tests empirically with code and synthetic data |
| `@arbiter` | Opus | Evaluates all evidence, renders verdict |
| `@conductor` | Opus | Orchestrates a full claim cycle autonomously |
| `@deep-thinker` | opus | Hard math/theory reasoning across all four phases |

The architect and adversary have no codebase access -- isolated to prevent anchoring bias. The experimenter has full codebase access. The conductor orchestrates other agents as subagents. The deep thinker is dispatched on demand (like any other agent, available in all phases) with WebSearch and WebFetch.

## How It Works

```
/principia:design "Your philosophical principle here"

Understand: Discussion refines principle, @scout surveys the landscape
Divide:     @synthesizer decomposes into testable claims, scaffolds directories
Test:       For each claim (respecting dependencies):
            @architect proposes -> @adversary attacks (1-3 rounds)
            -> @experimenter tests empirically
            -> @arbiter renders verdict
Synthesize: @synthesizer composes surviving claims into a design
```

After each verdict:
- **PROVEN**: Claim confirmed. Dependents can proceed.
- **DISPROVEN**: Hypothesis fails. Dependents are **weakened** with reduced confidence.
- **PARTIAL**: Holds under some conditions. Narrow or gather more evidence.
- **INCONCLUSIVE**: Not enough evidence. Try a different approach or defer.

The adversary always gets the last word before experiments. Anti-convergence protocols detect when agents agree too quickly and inject counter-evidence.

### State Machine Reference

Investigation-level actions (managed by orchestration.py):

```
understand → divide → scaffold → test_claim/record_verdict → synthesize → complete
```

Claim-level actions (`/principia:step` calls `manage.py next <path>`):

| Field | Description |
|-------|-------------|
| `action` | What to do next: `dispatch_architect`, `dispatch_adversary`, `dispatch_experimenter`, `dispatch_arbiter`, `post_verdict`, `complete_proven`, `complete_disproven`, `complete_partial`, `complete_inconclusive`, `waiting`, `error` |
| `phase` | Current phase: `debate`, `experiment`, `verdict`, `recording`, `complete` |
| `agent` | Which agent to dispatch (present for `dispatch_*` actions) |
| `round` | Current debate round number |
| `context_files` | Files to include in the agent's prompt |
| `result_path` | Where to save the agent's output |
| `dispatch_mode` | `internal` (subagent) or `external` (prompt file) |

Claim-level transitions:

```
dispatch_architect(1) -> dispatch_adversary(1)
  -> [fatal/serious] dispatch_architect(2) -> dispatch_adversary(2) -> ...
  -> [minor/none OR max_rounds] dispatch_experimenter
    -> dispatch_arbiter -> post_verdict
      -> complete_{proven,disproven,partial,inconclusive}
```

### Step-by-Step Mode

For manual control, use `/principia:step` to advance one agent at a time:

```
/principia:step     # dispatches architect round 1
/principia:step     # dispatches adversary round 1
/principia:step     # severity check -> architect round 2 or experimenter
...                 # continue to verdict
```

## Configuration

### Plugin-level config: `config/orchestration.yaml`

Controls workflow behavior: debate round limits, severity thresholds, post-verdict actions. See `config/README.md` for the full reference.

```yaml
debate_loop:
  max_rounds: 3          # cap on debate rounds
  final_say: adversary   # who gets last word

auto_review: true        # automated post-verdict bookkeeping

severity_keywords:
  fatal: ["fatal", "blocks the approach"]
  minor: ["minor", "worth noting"]
```

### Project-level config: `design/.config.md`

Created by `/principia:init`. Controls only agent dispatch mode (internal vs external) per project. Does not affect workflow logic.

## Directory Structure

```
design/
├── .north-star.md                  # Refined principle from Discussion
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
├── PROGRESS.md                     # Auto-generated progress report
├── FOUNDATIONS.md                   # Tracked assumptions
└── TOOLKIT.md                      # Reusable experiment code
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
| **Blueprint** | The synthesizer's decomposition of a principle into claims with dependency ordering (`design/blueprint.md`). |
| **Verdict** | The outcome of an adversarial cycle: PROVEN, DISPROVEN, PARTIAL, or INCONCLUSIVE. |
| **Cascade** | When a claim is disproven, all claims that depend on it have their confidence reduced automatically. |
| **Wave** | A set of claims with no mutual dependencies that can be investigated in parallel. |
| **Severity** | The adversary's rating of an attack: Fatal, Serious, Minor, or None. Determines whether debate continues. |
| **Maturity** | How well-established a claim is before testing: theorem-backed, supported, conjecture, or experiment. |
| **Falsification** | The pre-registered criterion that would disprove a claim. Written by the synthesizer. |
| **Knowledge divergence** | Deliberately giving the architect and adversary different prior art to prevent premature agreement. |
| **Anti-convergence** | Protocol to detect and prevent agents from agreeing too quickly without substantive evidence. |

## Development

```bash
uv venv && uv pip install pytest ruff mypy
uv run python -m pytest tests/ -q     # 363 tests
uv run ruff check scripts/            # lint
uv run python -m mypy scripts/        # type check
```

## Requirements

- Python 3.10+ (stdlib only -- no pip packages at runtime)
- Claude Code 2.0+

## License

MIT
