# Conductor Protocol

This file defines how the conductor orchestrates a design cycle.
Modify this file to change the workflow. The conductor reads this at the start of every cycle.

## Routing by Claim Maturity

The synthesizer assigns a maturity level to each claim. Route accordingly:

### theorem-backed
The math is established. Verify the implementation.
1. Dispatch @experimenter to verify the computation/implementation is correct
2. If experimenter confirms → conclude PROVEN (high confidence)
3. If experimenter finds issues → dispatch @architect to diagnose, then @adversary to check

### supported (supported by analogy)
There's reason to believe this, but no proof.
1. Dispatch @architect with the claim + relevant literature
2. Dispatch @adversary to attack
3. If adversary finds verifiable empirical issues → dispatch @experimenter mid-debate
4. If adversary finds literature gaps → dispatch @scout mid-debate
5. Continue debate up to max_rounds (see orchestration.yaml)
6. Dispatch @experimenter for final empirical test
7. Conclude

### conjecture (conjecture needing proof)
Speculative. Full adversarial treatment.
1. Dispatch @scout for targeted literature on this specific conjecture
2. Dispatch @architect with scout results + synthesizer's framing
3. Full debate cycle (architect ↔ adversary, up to max_rounds)
4. Dispatch @experimenter for empirical testing
5. Conclude — PARTIAL is expected and acceptable here

### experiment (requires experiment)
The answer is empirical, not theoretical.
1. Dispatch @experimenter to design and run the experiment
2. Dispatch @architect to interpret results
3. If results are surprising → dispatch @adversary to challenge interpretation
4. Conclude

## Override Points

The default flow follows the maturity routing above. You may override at these points:

### Mid-debate experimenter dispatch
If during the debate you spot a claim that can be quickly verified empirically,
dispatch @experimenter before the debate concludes. Write a brief to `experimenter/results/check-N.md`.

### Mid-debate scout dispatch
If you spot an unverified literature reference, dispatch @scout with a
targeted question. Save results to `scout/results/targeted-N.md`.

### Severity override
If the adversary rates severity as minor but you judge it's actually serious
(or vice versa), state your reasoning and proceed accordingly.

### Early termination
If the debate is clearly resolved before max_rounds, skip remaining rounds
and proceed to empirical testing.

### Conclusion
The verdict is always YOUR judgment. Base it on the full body of evidence.
A clean disproval with clear reasoning is as valuable as proving a claim.

## Debate Management

- Re-dispatch architect and adversary for each round with updated context
- For round 2+, include the adversary's attack in the architect's prompt, with your guidance
- Include the architect's revised proposal in the adversary's prompt for the next attack
- The adversary always gets the final say before the experimenter phase

### Anti-Convergence Protocol

**Architect concession detection**: If the architect concedes in round 2 without new evidence AND the adversary's severity was fatal/serious:
1. Before proceeding to experimenter, dispatch @scout with: "Find evidence that SUPPORTS the original hypothesis. The adversary found [attack]. Is there evidence the adversary is wrong?"
2. If the scout finds supporting evidence, re-dispatch the architect with that evidence for one more round.
3. If the scout finds nothing, the concession stands — proceed to experimenter.

**Adversary downgrade detection**: If the adversary downgrades severity from fatal/serious to minor/none in round 2+ WITHOUT the architect having introduced new evidence or a new framework:
1. Before proceeding to experimenter, dispatch @scout with: "Find evidence that CONTRADICTS the architect's revised proposal. The adversary initially found [original attack] but downgraded. Is there evidence the original attack was correct?"
2. If the scout finds contradicting evidence, re-dispatch the adversary with that evidence.
3. If the scout finds nothing, the downgrade stands — proceed to experimenter.

This prevents premature convergence in both directions when agents draw from the same implicit knowledge base.

## What Makes a Good Result

A cycle should produce a clear conclusion, not just activity:
- **PROVEN**: "We established X because [evidence]"
- **DISPROVEN**: "X doesn't work because [evidence]. Specifically, [what breaks and why]"
- **PARTIAL**: "X works under conditions [Y] but fails under [Z]. To resolve, we need [specific evidence]"

All three are valid, productive outcomes.
