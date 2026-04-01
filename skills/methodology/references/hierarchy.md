# Hierarchy and Naming Conventions

## ID Derivation Rules

Paths are abbreviated for compact IDs:
- `cycles/` prefix stripped
- `context/` prefix stripped
- `cycle-N` -> `cN`
- `unit-M-name` -> `uM`
- `sub-Ma-name` -> `sMa`
- `round-K` -> `rK`
- `prompts/` and `results/` directories dropped

Example: `cycles/cycle-1/unit-2-enrichment/sub-2a-bottleneck/architect/round-1/result.md` -> `c1-u2-s2a-architect-r1-result`

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
| `progress.md` | - | verdict |
| (fallback) | any | reference |

## Architect/Adversary Round Limits

Each role has a maximum of 3 rounds per sub-unit:
- `round-1/`: Initial proposal or attack
- `round-2/`: Refinement based on feedback
- `round-3/`: Final attempt

If 3 rounds are insufficient, escalate to a new sub-unit or redesign.

## Edge Types

| Relation | Meaning |
|----------|---------|
| depends_on | This node builds on the target |
| assumes | This node relies on the target assumption |
| disproven_by | This node was refuted by the target evidence |

## Cascade Rules

When a node is disproven:
1. Its status -> `disproven`
2. All transitive dependents (via `depends_on` or `assumes`) -> `partial`
3. Already `disproven` or `partial` nodes are skipped
4. Each status change is recorded in the audit ledger
