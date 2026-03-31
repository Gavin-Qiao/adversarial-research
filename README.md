# adversarial-research

Evidence-based adversarial research methodology for Claude Code. Track hypotheses, manage assumptions, cascade invalidation, and run structured adversarial cycles with specialized agents.

## Installation

```bash
claude --plugin-dir /path/to/adversarial-research
```

## Quick Start

```
# Initialize a project
/adversarial-research:init "My Research Project"

# Scaffold a research structure
/adversarial-research:scaffold cycle hypothesis-testing
/adversarial-research:scaffold unit baseline --parent cycles/cycle-1-hypothesis-testing
/adversarial-research:scaffold sub-unit direct --parent cycles/cycle-1-hypothesis-testing/unit-1-baseline

# Run the cycle (step by step)
/adversarial-research:next

# Or run the full cycle automatically
/adversarial-research:investigate "Does X predict Y?"
```

## Agents

| Agent | Model | Purpose | Codebase | Web |
|-------|-------|---------|----------|-----|
| `@researcher` | Sonnet | Survey literature, gather background | Read | Yes |
| `@thinker` | Opus | Propose hypotheses from context | None | Yes |
| `@deep-thinker` | Opus | Synthesize across sub-units/cycles | None | Yes |
| `@refutor` | Opus | Attack hypotheses, find counterexamples | None | Yes |
| `@coder` | Sonnet | Validate empirically with synthetic data | Full | No |
| `@judge` | Opus | Evaluate evidence, render verdict | Read-only | No |
| `@reviewer` | Sonnet | Record outcomes, update frontier | Full | No |
| `@conductor` | Opus | Orchestrate full cycle, dispatch agents | Full + Agent | No |

Thinker and refutor have web access (for literature search) but no codebase access — isolated from files to prevent anchoring bias. The conductor orchestrates other agents as subagents and uses the state machine for routing.

## Commands

### Orchestration

| Command | Description |
|---------|-------------|
| `/adversarial-research:next [path]` | Advance one step. Auto-detects active sub-unit. |
| `/adversarial-research:investigate "<question>"` | Full automated cycle: scaffold → debate → test → verdict |

### Structure

| Command | Description |
|---------|-------------|
| `/adversarial-research:init` | Bootstrap research directory |
| `/adversarial-research:scaffold <level> <name>` | Create cycle/unit/sub-unit structure |
| `/adversarial-research:new <path>` | Create file with auto-generated frontmatter |

### Verdict Management

| Command | Description |
|---------|-------------|
| `/adversarial-research:settle <id>` | Mark claim as settled |
| `/adversarial-research:falsify <id> [--by <evidence-id>]` | Falsify + cascade to dependents |
| `/adversarial-research:cascade <id>` | Dry-run: preview cascade impact |

### Tracking

| Command | Description |
|---------|-------------|
| `/adversarial-research:status` | Generate FRONTIER.md + ASSUMPTIONS.md |
| `/adversarial-research:validate` | Check database integrity |
| `/adversarial-research:query "<sql>"` | Query the research database |
| `/adversarial-research:methodology` | View the research methodology reference |

### Coder Artifacts

| Command | Description |
|---------|-------------|
| `manage.py register --id <id> --name --type --path` | Register a coder artifact for cross-cycle reuse |
| `manage.py artifacts` | List all registered artifacts |
| `manage.py codebook` | Generate CODEBOOK.md from the registry |

### Investigation Planning (CLI)

These commands are used internally by `/investigate` and the conductor:

| Command | Description |
|---------|-------------|
| `manage.py investigate-next` | Detect next phase of the full investigation |
| `manage.py parse-framework` | Parse claim registry from `framework.md` |
| `manage.py waves [--json]` | Show execution waves (dependency order) |
| `manage.py log-dispatch --cycle --agent --action` | Log a dispatch event (audit trail) |
| `manage.py dispatch-log [--cycle] [--json]` | View dispatch history |

## Complete Workflow Example

Investigating whether metric X predicts outcome Y:

```
# 1. Initialize
/adversarial-research:init "Metric X Investigation"

# 2. Scaffold
/adversarial-research:scaffold cycle predictive-power
/adversarial-research:scaffold unit baseline --parent cycles/cycle-1-predictive-power
/adversarial-research:scaffold sub-unit direct-correlation --parent cycles/cycle-1-predictive-power/unit-1-baseline

# 3. Step through the adversarial cycle
/adversarial-research:next          # dispatches thinker R1
/adversarial-research:next          # dispatches refutor R1
/adversarial-research:next          # checks severity → thinker R2 or coder
/adversarial-research:next          # ... continues to verdict

# 4. Check the frontier
/adversarial-research:status

# 5. If falsified, inspect the cascade
/adversarial-research:cascade assumption-id
/adversarial-research:falsify assumption-id --by evidence-id
```

Or automate the whole thing:

```
/adversarial-research:investigate "Does metric X predict outcome Y?"
```

## How the Orchestration Works

The `/next` command reads the sub-unit directory to determine what files exist and dispatches the next agent:

```
No thinker result     → dispatch thinker
Thinker done          → dispatch refutor
Refutor: fatal flaw   → dispatch thinker (next round, different framework)
Refutor: minor/none   → dispatch coder
Coder done            → prepare judge brief, dispatch judge
Verdict rendered      → dispatch reviewer
Reviewer done         → report verdict + suggestions
```

The debate loop caps at 3 rounds (configurable). The refutor always gets the last word.

The conductor agent uses this same state machine (`manage.py next`) for main-line routing, with autonomy to dispatch side-channel coder checks and researcher lookups. All dispatches are logged to the `dispatches` table.

After the verdict:
- **SETTLED**: Sub-unit complete. Dependents can proceed.
- **FALSIFIED**: Cascade applied — dependents set to `undermined` with attenuated confidence.
- **MIXED**: Claim partially true under some conditions. Refine or gather more evidence.
- **INCONCLUSIVE**: Insufficient evidence either way. Retry with different approach or defer.

## Configuration

Orchestration behavior is controlled by `config/orchestration.yaml`:

```yaml
debate_loop:
  max_rounds: 3         # change to 1 for fast mode
  final_say: refutor    # who gets last word

severity_keywords:
  fatal: ["fatal", "blocks the approach"]
  minor: ["minor", "worth noting"]
```

See `config/README.md` for the full configuration reference.

Agent dispatch preferences (internal subagent vs external prompt) are set during `/init` and stored in `research/.config.md`.

## Directory Structure

```
research/
├── cycles/                     # Research cycles
│   └── cycle-N-name/
│       └── unit-M-name/
│           └── sub-Ma-name/
│               ├── thinker/round-K/{prompt,result}.md
│               ├── refutor/round-K/{prompt,result}.md
│               ├── coder/{prompt.md,results/output.md}
│               ├── judge/{brief.md,results/verdict.md}
│               ├── researcher/results/
│               └── frontier.md
├── context/                    # Knowledge distillations
│   └── assumptions/            # Tracked assumptions
├── .db/                        # SQLite database (gitignored)
├── .config.md                  # Agent dispatch preferences
├── FRONTIER.md                 # Auto-generated research frontier
└── ASSUMPTIONS.md              # Auto-generated assumption registry
```

## Frontmatter Schema

```yaml
---
id: <auto-derived from path>
type: claim | assumption | evidence | reference | verdict | question
status: pending | active | settled | falsified | mixed | undermined
date: YYYY-MM-DD
depends_on: [node-id, ...]
assumes: [assumption-id, ...]
attack_type: undermines | rebuts | undercuts
falsified_by: evidence-id
counterfactual: "what changes if false"
---
```

## Development

```bash
uv venv && uv pip install pytest ruff mypy
source .venv/bin/activate
pytest tests/ -q         # 201+ tests
ruff check scripts/      # lint
mypy scripts/            # type check
```

## Requirements

- Python 3.10+ (stdlib only for core — no pip packages needed at runtime)
- Claude Code 2.0+
