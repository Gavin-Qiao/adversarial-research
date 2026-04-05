<div align="center">

# principia

**Turn a philosophical principle into a working algorithm through rigorous adversarial testing.**

[![Version](https://img.shields.io/badge/version-0.4.0a1-blue.svg)](https://github.com/Gavin-Qiao/principia/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-346_passing-brightgreen.svg)]()
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-blueviolet.svg)](https://docs.anthropic.com/en/docs/claude-code)

You start with an insight. Principia decomposes it into testable claims, stress-tests each through structured debate and empirical experiments, and composes the surviving pieces into a theory you can build on.

[Installation](#installation) | [Quick Start](#quick-start) | [How It Works](#how-it-works) | [Agents](#agents) | [Commands](#commands) | [Configuration](#configuration)

</div>

---

## Installation

Inside Claude Code:

```
/plugin marketplace add Gavin-Qiao/principia
/plugin install principia
```

Or for local development:

```bash
claude --plugin-dir /path/to/principia
```

Requires **Python 3.10+** (stdlib only -- no pip packages at runtime) and **Claude Code 2.0+**.

### Codex Harness

Codex can point at the repository-local harness scaffold in `harnesses/codex`. Task 4 adds the static plugin metadata and marketplace entry; Task 5 turns that scaffold into a functional workflow. Select the Principia plugin from this repo's marketplace metadata so harness selection stays tied to the checkout instead of a global install.

## Quick Start

```
/principia:init "Topological Enrichment"
/principia:design "Persistent homology captures information that clustering
algorithms discard. An algorithm that preserves topological features during
hierarchical merging should produce more faithful cluster boundaries."
```

That's it. Principia runs four phases automatically:

```mermaid
graph LR
    U["<b>1. Understand</b><br/>Refine principle<br/>Survey landscape"] --> D["<b>2. Divide</b><br/>Decompose into<br/>testable claims"]
    D --> T["<b>3. Test</b><br/>Debate + experiment<br/>per claim"]
    T --> S["<b>4. Synthesize</b><br/>Compose surviving<br/>claims into theory"]

    style U fill:#e8f4fd,stroke:#2196f3
    style D fill:#fff3e0,stroke:#ff9800
    style T fill:#fce4ec,stroke:#e91e63
    style S fill:#e8f5e9,stroke:#4caf50
```

Add `--quick` to skip research, limit debate to 1 round, and get results fast.

## How It Works

### The Investigation Pipeline

```mermaid
flowchart TD
    P["User's Principle"] --> U

    subgraph U ["Phase 1: Understand"]
        U1["Discuss & refine<br/><i>with user</i>"] --> U2["Inspect codebase"]
        U2 --> U3["<b>@scout</b> surveys literature"]
        U3 -.-> DT1["<b>@deep-thinker</b><br/><i>if hard math questions arise</i>"]
    end

    U --> D

    subgraph D ["Phase 2: Divide"]
        D1["<b>@synthesizer</b> decomposes<br/>principle into claims"] --> D2["Scaffold claim directories"]
        D2 --> D3["Dependency graph computed"]
        D1 -.-> DT2["<b>@deep-thinker</b><br/><i>if decomposition needs<br/>theoretical grounding</i>"]
    end

    D --> T

    subgraph T ["Phase 3: Test"]
        T1["For each claim<br/><i>(respecting dependency waves)</i>"]
        T1 --> DEBATE
        DEBATE --> EXP["<b>@experimenter</b><br/>runs empirical test"]
        EXP --> VERDICT["<b>@arbiter</b><br/>renders verdict"]
        VERDICT -->|"more claims"| T1
    end

    T --> S

    subgraph S ["Phase 4: Synthesize"]
        S1["<b>@synthesizer</b> composes<br/>composition.md + synthesis.md"]
        S1 --> S2["Generate RESULTS.md"]
        S1 -.-> DT3["<b>@deep-thinker</b><br/><i>if conflicting verdicts need<br/>mathematical reconciliation</i>"]
    end

    subgraph DEBATE ["Adversarial Debate (1-3+ rounds)"]
        A1["<b>@architect</b> proposes"] --> A2["<b>@adversary</b> attacks"]
        A2 -->|"fatal / serious"| A1
        A2 -->|"minor / none"| EXIT(("Exit"))
    end

    T -.-> SCO["<b>@scout</b><br/><i>mid-debate prior art<br/>if debate stalls</i>"]
```

### Per-Claim Debate Loop

Each claim goes through an adversarial cycle. The `@conductor` orchestrates the full loop and can extend debate rounds if the adversary is still finding serious flaws.

```mermaid
stateDiagram-v2
    [*] --> Architect_R1: dispatch

    state "Debate" as debate {
        Architect_R1: @architect proposes (Round 1)
        Adversary_R1: @adversary attacks (Round 1)
        Architect_RN: @architect revises (Round N)
        Adversary_RN: @adversary attacks (Round N)

        Architect_R1 --> Adversary_R1
        Adversary_R1 --> Architect_RN: fatal / serious
        Architect_RN --> Adversary_RN
        Adversary_RN --> Architect_RN: fatal / serious
    }

    Adversary_R1 --> Experimenter: minor / none
    Adversary_RN --> Experimenter: minor / none
    Adversary_RN --> Experimenter: max rounds hit

    Experimenter: @experimenter tests empirically
    Arbiter: @arbiter renders verdict

    Experimenter --> Arbiter
    Arbiter --> PROVEN
    Arbiter --> DISPROVEN
    Arbiter --> PARTIAL
    Arbiter --> INCONCLUSIVE

    PROVEN --> [*]
    DISPROVEN --> Cascade
    PARTIAL --> [*]
    INCONCLUSIVE --> [*]

    Cascade: Dependents weakened
    Cascade --> [*]
```

### Verdict Cascade

When a claim is disproven, all claims that depend on it are automatically weakened:

```mermaid
graph TD
    A["Claim A<br/><b>DISPROVEN</b>"] -->|depends_on| B["Claim B<br/><i>weakened</i>"]
    A -->|depends_on| C["Claim C<br/><i>weakened</i>"]
    B -->|depends_on| D["Claim D<br/><i>weakened</i>"]
    C -->|depends_on| D

    style A fill:#ffcdd2,stroke:#c62828
    style B fill:#fff9c4,stroke:#f9a825
    style C fill:#fff9c4,stroke:#f9a825
    style D fill:#fff9c4,stroke:#f9a825
```

| Verdict | Effect |
|---------|--------|
| **PROVEN** | Claim confirmed. Dependents can proceed. |
| **DISPROVEN** | Hypothesis fails. Dependents **weakened** via cascade. |
| **PARTIAL** | Holds under conditions. Narrow or gather more evidence. |
| **INCONCLUSIVE** | Insufficient evidence. Try a different approach or defer. |

## Agents

Principia uses 8 specialized agents. Each has a specific role and constrained access to prevent bias.

### Agent-Phase Map

| Agent | Role | Understand | Divide | Test | Synthesize |
|-------|------|:----------:|:------:|:----:|:----------:|
| **@architect** | Proposes designs from first principles | | | proposes | |
| **@adversary** | Finds flaws, counterexamples, edge cases | | | attacks | |
| **@experimenter** | Tests claims with code and synthetic data | | | experiments | |
| **@arbiter** | Evaluates evidence, renders verdict | | | verdicts | |
| **@conductor** | Orchestrates full claim cycles | | | orchestrates | |
| **@synthesizer** | Decomposes and unifies | | decomposes | | unifies |
| **@scout** | Surveys prior art and failure cases | surveys | | prior art | |
| **@deep-thinker** | Hard math/theory reasoning | on demand | on demand | on demand | on demand |

| Agent | Model | Access |
|-------|-------|--------|
| **@architect** | Opus | No codebase (isolated to prevent anchoring) |
| **@adversary** | Opus | No codebase (isolated to prevent anchoring) |
| **@experimenter** | Sonnet | Full codebase access |
| **@arbiter** | Opus | Read-only codebase |
| **@conductor** | Opus | Full access + Agent tool |
| **@synthesizer** | Opus | No codebase (isolated) |
| **@scout** | Sonnet | Web search + read access |
| **@deep-thinker** | Opus | Web search |

**Isolation matters**: The architect and adversary have **no codebase access** to prevent anchoring bias. They reason purely from provided context. The experimenter has full access because it needs to write and run code.

**Anti-convergence**: The conductor monitors for **sycophancy** (architect conceding without new evidence, adversary downgrading severity without justification) and injects counter-evidence via `@scout` when agents agree too quickly.

**Knowledge divergence**: The conductor gives architect and adversary **different prior art** — positive results to the architect, failure cases to the adversary — to prevent premature agreement.

## Commands

| Command | What it does |
|---------|-------------|
| `/principia:init [title]` | Bootstrap a new project |
| `/principia:design "<principle>" [--quick]` | Full pipeline: principle to algorithm |
| `/principia:step [path]` | Advance one step manually |
| `/principia:status` | Regenerate PROGRESS.md |
| `/principia:impact <id>` | Preview cascade: what breaks if this claim is disproven? |
| `/principia:query "<sql>"` | Query the evidence database directly |
| `/principia:help` | Overview of commands, agents, and how to get started |

<details>
<summary><b>Internal commands</b> (used by agents and skills)</summary>

| Command | What it does |
|---------|-------------|
| `/principia:scaffold <level> <name>` | Create directory structure for a claim |
| `/principia:new <path>` | Create a design file with auto-generated frontmatter |
| `/principia:falsify <id> [--by <id>]` | Mark a claim as disproven and cascade |
| `/principia:settle <id>` | Mark a claim as proven |
| `/principia:validate` | Check design log integrity |
| `/principia:methodology` | Reference: the principia design methodology |

</details>

## Configuration

### Autonomy

By default, Principia pauses at each phase transition for confirmation. Set **yolo mode** for fully autonomous runs (e.g., overnight):

```yaml
# config/orchestration.yaml
autonomy:
  mode: yolo               # checkpoints (default) | yolo
  checkpoint_at: [understand, divide, test, synthesize]
```

| Mode | Behavior |
|------|----------|
| **checkpoints** (default) | Pauses between phases, asks about claim complexity, prompts on non-terminal verdicts |
| **yolo** | Reports progress and continues automatically -- designed for unattended overnight runs |

### Workflow tuning

```yaml
# config/orchestration.yaml
debate_loop:
  max_rounds: 3          # cap on debate rounds (conductor can extend per-claim)
  final_say: adversary   # who gets last word

severity_keywords:
  fatal: ["fatal", "blocks the approach"]
  minor: ["minor", "worth noting"]
```

The conductor can override `max_rounds` for a specific claim via `extend-debate` when the debate is making real progress but hasn't resolved.

### Dispatch mode

Created by `/principia:init` in `design/.config.md`:

- **internal** (default): agents run as Claude Code subagents
- **external**: generates a self-contained prompt you can paste into any LLM

## Research Tracking

Principia maintains a SQLite database (`design/.db/research.db`) with an append-only audit trail:

| Table | What it tracks |
|-------|---------------|
| **ledger** | Every state change (proven, disproven, weakened) with timestamp and agent |
| **dispatches** | Every agent invocation: who, when, which claim, which round |
| **nodes** | All claims, assumptions, evidence with status and metadata |
| **edges** | Dependency graph (depends_on, assumes, falsified_by) |

Generated reports: `PROGRESS.md` (current blockers and status), `FOUNDATIONS.md` (load-bearing assumptions), `RESULTS.md` (final investigation summary).

The ledger and dispatches survive database rebuilds -- your research history is never lost.

## Directory Structure

```
design/
├── .north-star.md                  # Refined principle
├── .context.md                     # Codebase inspection findings
├── claims/                         # One directory per testable claim
│   └── claim-N-name/
│       ├── architect/round-K/      # Hypothesis proposals
│       ├── adversary/round-K/      # Stress-test attacks
│       ├── experimenter/results/   # Empirical tests
│       ├── arbiter/results/        # Verdicts
│       └── claim.md                # Claim frontmatter + statement
├── context/                        # Scout research outputs
├── blueprint.md                    # Claim registry from synthesizer
├── composition.md                  # Unified algorithm design
├── synthesis.md                    # Cross-claim analysis
├── RESULTS.md                      # Final investigation summary
├── PROGRESS.md                     # Auto-generated status
└── FOUNDATIONS.md                   # Tracked assumptions
```

<details>
<summary><b>Frontmatter schema</b></summary>

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

</details>

## Glossary

| Term | Definition |
|------|-----------|
| **Claim** | A testable assertion decomposed from the user's principle |
| **Blueprint** | Synthesizer's decomposition of a principle into claims with dependency ordering |
| **Verdict** | Outcome of an adversarial cycle: PROVEN, DISPROVEN, PARTIAL, or INCONCLUSIVE |
| **Cascade** | When a claim is disproven, dependents are automatically weakened |
| **Wave** | Claims with no mutual dependencies that can be tested in parallel |
| **Severity** | Adversary's rating (Fatal/Serious/Minor/None) -- determines debate continuation |
| **Falsification** | Pre-registered criterion that would disprove a claim |
| **Anti-convergence** | Protocol that detects premature agent agreement and injects counter-evidence |
| **Knowledge divergence** | Giving architect and adversary different prior art to prevent convergence |

## Development

```bash
uv sync --dev                          # install dev dependencies
uv run python -m pytest tests/ -q      # 373 tests
uv run ruff check scripts/ tests/      # lint
uv run ruff format --check scripts/    # format
uv run python -m mypy scripts/         # type check
```

## License

MIT
