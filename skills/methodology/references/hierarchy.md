# Hierarchy and Naming Conventions

## ID Derivation Rules

Paths are abbreviated for compact IDs:
- `claims/` prefix stripped
- `context/` prefix stripped
- `claim-N-name` -> `hN`
- `round-K` -> `rK`
- `prompts/` and `results/` directories dropped

Example: `claims/claim-1-enrichment/architect/round-1/result.md` -> `h1-architect-r1-result`

## Type Inference from Path

| Directory | File | Inferred Type |
|-----------|------|---------------|
| `architect/` | `prompt.md` | question |
| `architect/` | `result.md` | claim |
| `adversary/` | `prompt.md` | question |
| `adversary/` | `result.md` | claim |
| `synthesizer/` | `prompt.md` | question |
| `synthesizer/` | `result.md` | claim |
| `experimenter/` | any | evidence |
| `scout/` | any | reference |
| `arbiter/` | any | verdict |
| `assumptions/` | any | assumption |
| `claim.md` | - | claim |
| (fallback) | any | reference |

## Architect/Adversary Round Limits

Each role has a maximum of 3 rounds per claim:
- `round-1/`: Initial proposal or attack
- `round-2/`: Refinement based on feedback
- `round-3/`: Final attempt

If 3 rounds are insufficient, escalate to a new claim or redesign.

## Edge Types

| Relation | Meaning |
|----------|---------|
| depends_on | This node builds on the target |
| assumes | This node relies on the target assumption |
| falsified_by | This node was refuted by the target evidence |

## Cascade Rules

When a node is disproven:
1. Its status -> `disproven`
2. All transitive dependents (via `depends_on` or `assumes`) -> `weakened`
3. Already `disproven`, `weakened`, or `inconclusive` nodes are skipped
4. Each status change is recorded in the audit ledger

## Valid Status Values

- **pending**: Not yet started
- **active**: Work in progress
- **proven**: Accepted as established (with evidence)
- **disproven**: Refuted by evidence
- **partial**: Arbiter verdict — claim holds under some conditions but not universally
- **weakened**: A dependency was disproven; confidence reduced but claim not directly disproven
- **inconclusive**: Evidence was ambiguous; no clear verdict

## Legacy

The `cycles/cycle-N/unit-M/sub-Ma/` structure from v0.2 is still supported for backward compatibility. Legacy ID derivation rules: `cycle-N` -> `cN`, `unit-M-name` -> `uM`, `sub-Ma-name` -> `sMa`. Use `scaffold claim` for new work.
