# Hierarchy and Naming Conventions

## ID Derivation Rules

Paths are abbreviated for compact IDs:
- `cycles/` prefix stripped
- `context/` prefix stripped
- `cycle-N` → `cN`
- `unit-M-name` → `uM`
- `sub-Ma-name` → `sMa`
- `round-K` → `rK`
- `prompts/` and `results/` directories dropped

Example: `cycles/cycle-1/unit-2-enrichment/sub-2a-bottleneck/thinker/round-1/result.md` → `c1-u2-s2a-thinker-r1-result`

## Type Inference from Path

| Directory | File | Inferred Type |
|-----------|------|---------------|
| `thinker/` | `prompt.md` | question |
| `thinker/` | `result.md` | claim |
| `refutor/` | `prompt.md` | question |
| `refutor/` | `result.md` | claim |
| `deep-thinker/` | `prompt.md` | question |
| `deep-thinker/` | `result.md` | claim |
| `coder/` | any | evidence |
| `researcher/` | any | reference |
| `judge/` | any | verdict |
| `assumptions/` | any | assumption |
| `frontier.md` | - | verdict |
| (fallback) | any | reference |

## Thinker/Refutor Round Limits

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
| falsified_by | This node was disproven by the target evidence |

## Cascade Rules

When a node is falsified:
1. Its status → `falsified`
2. All transitive dependents (via `depends_on` or `assumes`) → `mixed`
3. Already `falsified` or `mixed` nodes are skipped
4. Each status change is recorded in the audit ledger
