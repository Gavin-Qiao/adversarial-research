---
name: methodology
description: "Reference: explains the principia algorithm design methodology -- hierarchy, roles, frontmatter schema, status tags, and workflow. This is informational only and does not perform any actions. Use when the user asks how the design system works."
user-invocable: false
---

# Principia Algorithm Design Methodology

## Philosophy

Algorithm design proceeds through adversarial cycles where design proposals are proposed, attacked, tested empirically, and judged. This prevents confirmation bias and ensures only evidence-backed claims survive.

## Hierarchy

```
design/
├── cycles/
│   └── cycle-N/                    # A design cycle
│       ├── progress.md             # Cycle-level progress
│       └── unit-M-<name>/          # A design unit (topic)
│           ├── progress.md         # Unit-level progress
│           └── sub-Ma-<name>/      # A sub-investigation
│               ├── progress.md     # Sub-unit progress
│               ├── architect/      # Design proposals
│               │   └── round-K/
│               │       ├── prompt.md
│               │       └── result.md
│               ├── adversary/      # Attacks on proposals
│               │   └── round-K/
│               │       ├── prompt.md
│               │       └── result.md
│               ├── experimenter/   # Empirical validation
│               │   ├── prompt.md
│               │   └── results/
│               │       └── output.md
│               └── arbiter/        # Verdict
│                   └── results/
│                       └── verdict.md
└── context/
    ├── survey-*.md                 # Knowledge summaries
    └── assumptions/                # Tracked assumptions
        └── assumption-*.md
```

## Roles

| Role | Type | Purpose | Codebase Access |
|------|------|---------|-----------------|
| Scout | reference | Survey literature, gather background knowledge | Web + read |
| Architect | claim | Propose design solutions from provided context | None |
| Adversary | claim | Attack proposals, find counterexamples | None |
| Experimenter | evidence | Generate synthetic data, run experiments | Full |
| Arbiter | verdict | Evaluate evidence, render decisions | Read-only |
| Post-verdict | - | Record outcomes, update statuses, maintain progress (automated) | Full |

Architect and Adversary must NOT read the codebase. They reason only from the context provided in their prompts. This prevents anchoring bias.

The post-verdict step runs after each verdict to update frontmatter statuses, run cascade invalidation, regenerate PROGRESS.md and FOUNDATIONS.md, and write summary notes.

## Frontmatter Schema

```yaml
---
id: <auto-derived from path>
type: claim | assumption | evidence | reference | verdict | question
status: pending | active | proven | disproven | partial
date: YYYY-MM-DD
depends_on: [<node-id>, ...]
assumes: [<assumption-id>, ...]
attack_type: undermines | rebuts | undercuts | null
disproven_by: <evidence-id> | null
counterfactual: "<what changes if this is false>" | null
---
```

## Status Tags

- **pending**: Not yet started
- **active**: Work in progress
- **proven**: Accepted as established (with evidence)
- **disproven**: Refuted by evidence
- **partial**: A dependency was disproven; needs review

## Workflow

1. **Scaffold**: Create cycle/unit/sub-unit structure (`/scaffold`)
2. **Dialectic** (debate loop, max 3 rounds):
   - **Architect** proposes design solution
   - **Adversary** attacks (rates severity: Fatal / Serious / Minor)
   - If Fatal/Serious and round < max: architect revises from a *different framework*
   - If Minor/None or round = max: exit to empirical testing
   - Adversary always gets the final word before the experimenter
3. **Refutation**: **Experimenter** tests empirically with synthetic data
4. **Judgment**: **Arbiter** evaluates all evidence from a structured brief, renders PROVEN / DISPROVEN / PARTIAL / INCONCLUSIVE
5. **Recording**: **Post-verdict** (automated) updates statuses, runs cascade, regenerates PROGRESS.md
6. **Branching**:
   - PROVEN -> sub-unit complete, dependents proceed
   - DISPROVEN -> cascade to dependents, open new sub-unit
   - PARTIAL -> user decides: retry, more evidence, or escalate

Use `/principia:step` to step through this workflow automatically, or `/principia:design` to run the full cycle.

The orchestration behavior (round limits, severity thresholds, post-verdict actions) is configurable in `config/orchestration.yaml`. See `config/README.md` for details.

For the hierarchy and naming conventions, see `references/hierarchy.md`.
For the full state machine and phase definitions, see `references/workflow.md`.
