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
1. **Survey** the research landscape
2. **Decompose** your principle into testable claims
3. **Stress-test** each claim: debate (architect vs adversary) then experiment
4. **Render verdicts**: proven / disproven / partial / inconclusive
5. **Synthesize** surviving claims into a coherent design

## Commands

| Command | What it does |
|---------|-------------|
| `/principia:design "<principle>"` | Full pipeline: principle to algorithm |
| `/principia:step [path]` | Advance one step manually |
| `/principia:status` | Progress report |
| `/principia:init [title]` | Bootstrap a new project |
| `/principia:impact <id>` | Preview: what breaks if this claim fails? |
| `/principia:query "<sql>"` | Query the evidence database |
| `/principia:list [--type] [--status]` | Browse claims and evidence |

## Agents

| Agent | Model | Role |
|-------|-------|------|
| `@scout` | Sonnet | Surveys the landscape — prior work, relevant techniques |
| `@architect` | Opus | Proposes designs and hypotheses from context |
| `@adversary` | Opus | Stress-tests: finds flaws, counterexamples, edge cases |
| `@synthesizer` | Opus | Unifies findings across claims into coherent design |
| `@experimenter` | Sonnet | Tests empirically with code and synthetic data |
| `@arbiter` | Opus | Evaluates all evidence, renders verdict |
| `@conductor` | Opus | Orchestrates a full claim cycle autonomously |

The architect and adversary have no codebase access — isolated to prevent anchoring bias. The experimenter has full codebase access. The conductor orchestrates other agents as subagents.

## How It Works

```
/principia:design "Your philosophical principle here"

Phase 1: @scout surveys the landscape
Phase 2: @synthesizer decomposes into testable claims
Phase 3: For each claim (respecting dependencies):
         @architect proposes → @adversary attacks (1-3 rounds)
         → @experimenter tests empirically
         → @arbiter renders verdict
Phase 4: @synthesizer composes surviving claims into a design
```

After each verdict:
- **PROVEN**: Claim confirmed. Dependents can proceed.
- **DISPROVEN**: Hypothesis fails. Dependents are **weakened** with reduced confidence.
- **PARTIAL**: Holds under some conditions. Narrow or gather more evidence.
- **INCONCLUSIVE**: Not enough evidence. Try a different approach or defer.

The adversary always gets the last word before experiments. Anti-convergence protocols detect when agents agree too quickly and inject counter-evidence.

### Step-by-Step Mode

For manual control, use `/principia:step` to advance one agent at a time:

```
/principia:step     # dispatches architect round 1
/principia:step     # dispatches adversary round 1
/principia:step     # severity check → architect round 2 or experimenter
...                 # continue to verdict
```

## Configuration

Behavior is controlled by `config/orchestration.yaml`:

```yaml
debate_loop:
  max_rounds: 3          # cap on debate rounds
  final_say: adversary   # who gets last word

auto_review: true        # automated post-verdict bookkeeping

severity_keywords:
  fatal: ["fatal", "blocks the approach"]
  minor: ["minor", "worth noting"]
```

See `config/README.md` for the full reference.

## Directory Structure

```
design/
├── claims/                         # One directory per testable claim
│   └── claim-N-name/
│       ├── architect/round-K/      # Hypothesis proposals
│       ├── adversary/round-K/      # Stress-test attacks
│       ├── experimenter/results/   # Empirical tests
│       ├── arbiter/results/        # Verdicts
│       └── claim.md                # Claim statement + metadata
├── context/surveys/                # Background research
├── blueprint.md                    # Claim decomposition plan
├── synthesis.md                    # Cross-claim synthesis
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

## Development

```bash
uv venv && uv pip install pytest ruff mypy
uv run pytest tests/ -q     # 246 tests
uv run ruff check scripts/  # lint
```

## Requirements

- Python 3.10+ (stdlib only — no pip packages at runtime)
- Claude Code 2.0+

## License

MIT
