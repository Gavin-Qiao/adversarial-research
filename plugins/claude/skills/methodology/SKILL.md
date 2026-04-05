---
name: methodology
description: "Reference: explains the principia algorithm design methodology -- hierarchy, roles, frontmatter schema, status tags, and workflow. This is informational only and does not perform any actions. Use when the user asks how the design system works."
user-invocable: false
---

# Principia Algorithm Design Methodology

## Philosophy

Algorithm design proceeds through adversarial cycles where design proposals are proposed, attacked, tested empirically, and evaluated by an arbiter. This prevents confirmation bias and ensures only evidence-backed claims survive.

## Hierarchy

```
principia/
├── .north-star.md          # Refined principle (Understand > discuss)
├── .context.md             # Codebase findings (Understand > inspect)
├── context/
│   ├── assumptions/
│   └── survey-*.md         # Literature (Understand > research)
├── blueprint.md            # Claim decomposition (Divide)
├── claims/
│   ├── claim-1-foo/
│   │   ├── claim.md        # Frontmatter + statement
│   │   ├── architect/      # round-{1,2,3}/result.md
│   │   ├── adversary/      # round-{1,2,3}/result.md
│   │   ├── experimenter/   # results/output.md
│   │   ├── arbiter/        # results/verdict.md
│   │   └── scout/
│   └── claim-2-bar/
├── composition.md
├── synthesis.md
└── RESULTS.md
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

Every `.md` node file starts with YAML frontmatter:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique node identifier, derived from file path |
| `type` | Yes | `claim`, `assumption`, `evidence`, `verdict`, `reference`, `question` |
| `status` | Yes | `pending`, `active`, `proven`, `disproven`, `partial`, `weakened`, `inconclusive` |
| `date` | Yes | Creation date (YYYY-MM-DD) |
| `depends_on` | No | List of node IDs this depends on (drives wave ordering) |
| `assumes` | No | List of assumption node IDs |
| `attack_type` | No | For adversary results: `weakens`, `rebuts`, `undercuts` |
| `falsified_by` | No | Node ID of evidence that disproved this |
| `counterfactual` | No | What would be true if this assumption is wrong |
| `maturity` | No | Claim maturity: `theorem-backed`, `supported`, `conjecture`, `experiment` |
| `confidence` | No | `high`, `moderate`, `low` |
| `wave` | No | Execution wave number (computed by dependency sort) |
| `cycle_status` | No | Per-cycle status tracking |
| `falsification` | No | Pre-registered falsification criterion from claim registry |

## Status Tags

- **pending**: Not yet started
- **active**: Work in progress
- **proven**: Accepted as established (with evidence)
- **disproven**: Refuted by evidence
- **partial**: Arbiter verdict — claim holds under some conditions but not universally
- **weakened**: A dependency was disproven; confidence reduced but claim not directly disproven
- **inconclusive**: Evidence was ambiguous; no clear verdict

## Workflow

1. **Scaffold**: Create claim structure (`/scaffold`)
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
   - PROVEN -> claim complete, dependents proceed
   - DISPROVEN -> cascade to dependents, open new claim
   - PARTIAL -> user decides: retry, more evidence, or escalate

Use `/principia:step` to step through this workflow automatically, or `/principia:design` to run the full cycle.

The orchestration behavior (round limits, severity thresholds, post-verdict actions) is configurable in `config/orchestration.yaml`. See `config/README.md` for details.

For the hierarchy and naming conventions, see `references/hierarchy.md`.
For the full state machine and phase definitions, see `references/workflow.md`.
