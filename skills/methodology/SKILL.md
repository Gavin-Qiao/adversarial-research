---
name: methodology
description: This skill provides knowledge about the adversarial research methodology, including the cycle/unit/sub-unit hierarchy, role definitions (thinker, refutor, coder, judge), YAML frontmatter schema, status tags, naming conventions, and the evidence-based research workflow. Use when the user discusses research methodology, adversarial cycles, hypothesis tracking, falsification, or asks how the research system works.
---

# Adversarial Research Methodology

## Philosophy

Research proceeds through adversarial cycles where hypotheses are proposed, attacked, tested empirically, and judged. This prevents confirmation bias and ensures only evidence-backed claims survive.

## Hierarchy

```
research/
├── cycles/
│   └── cycle-N/                    # A research cycle
│       ├── frontier.md             # Cycle-level frontier
│       └── unit-M-<name>/          # A research unit (topic)
│           ├── frontier.md         # Unit-level frontier
│           └── sub-Ma-<name>/      # A sub-investigation
│               ├── frontier.md     # Sub-unit frontier
│               ├── thinker/        # Hypothesis proposals
│               │   └── round-K/
│               │       ├── prompt.md
│               │       └── result.md
│               ├── refutor/        # Attacks on hypotheses
│               │   └── round-K/
│               │       ├── prompt.md
│               │       └── result.md
│               ├── coder/          # Empirical validation
│               │   ├── prompt.md
│               │   └── results/
│               │       └── output.md
│               └── judge/          # Verdict
│                   └── results/
│                       └── verdict.md
└── context/
    ├── distillation-*.md           # Knowledge summaries
    └── assumptions/                # Tracked assumptions
        └── assumption-*.md
```

## Roles

| Role | Type | Purpose | Codebase Access |
|------|------|---------|-----------------|
| Researcher | reference | Survey literature, gather background knowledge | Web + read |
| Thinker | claim | Propose hypotheses from provided context | None |
| Refutor | claim | Attack hypotheses, find counterexamples | None |
| Coder | evidence | Generate synthetic data, run experiments | Full |
| Judge | verdict | Evaluate evidence, render decisions | Read-only |
| Reviewer | - | Record outcomes, update statuses, maintain frontier | Full |

Thinker and Refutor must NOT read the codebase. They reason only from the context provided in their prompts. This prevents anchoring bias.

The Reviewer runs after each verdict to update frontmatter statuses, run cascade invalidation, regenerate FRONTIER.md and ASSUMPTIONS.md, and write summary notes.

## Frontmatter Schema

```yaml
---
id: <auto-derived from path>
type: claim | assumption | evidence | reference | verdict | question
status: pending | active | settled | falsified | mixed
date: YYYY-MM-DD
depends_on: [<node-id>, ...]
assumes: [<assumption-id>, ...]
attack_type: undermines | rebuts | undercuts | null
falsified_by: <evidence-id> | null
counterfactual: "<what changes if this is false>" | null
---
```

## Status Tags

- **pending**: Not yet started
- **active**: Work in progress
- **settled**: Accepted as established (with evidence)
- **falsified**: Disproven by evidence
- **mixed**: A dependency was falsified; needs review

## Workflow

1. **Scaffold**: Create cycle/unit/sub-unit structure (`/scaffold`)
2. **Pre-falsification** (debate loop, max 3 rounds):
   - **Thinker** proposes hypothesis
   - **Refutor** attacks (rates severity: Fatal / Serious / Minor)
   - If Fatal/Serious and round < max: thinker revises from a *different framework*
   - If Minor/None or round = max: exit to empirical testing
   - Refutor always gets the final word before the coder
3. **Falsification**: **Coder** tests empirically with synthetic data
4. **Judgment**: **Judge** evaluates all evidence from a structured brief, renders SETTLED / FALSIFIED / MIXED
5. **Recording**: **Reviewer** updates statuses, runs cascade, regenerates FRONTIER.md
6. **Branching**:
   - SETTLED → sub-unit complete, dependents proceed
   - FALSIFIED → cascade to dependents, open new sub-unit
   - MIXED → user decides: retry, more evidence, or escalate

Use `/adversarial-research:next` to step through this workflow automatically, or `/adversarial-research:investigate` to run the full cycle.

The orchestration behavior (round limits, severity thresholds, post-verdict actions) is configurable in `config/orchestration.yaml`. See `config/README.md` for details.

For the hierarchy and naming conventions, see `references/hierarchy.md`.
For the full state machine and phase definitions, see `references/workflow.md`.
