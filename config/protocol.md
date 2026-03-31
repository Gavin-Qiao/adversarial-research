# Conductor Protocol

This file defines how the conductor orchestrates a research cycle.
Modify this file to change the workflow. The conductor reads this at the start of every cycle.

## Routing by Claim Maturity

The deep thinker assigns a maturity level to each claim. Route accordingly:

### theorem-backed
The math is established. Verify the implementation.
1. Dispatch @coder to verify the computation/implementation is correct
2. If coder confirms → conclude SETTLED (high confidence)
3. If coder finds issues → dispatch @thinker to diagnose, then @refutor to check

### supported (supported by analogy)
There's reason to believe this, but no proof.
1. Dispatch @thinker with the claim + relevant literature
2. Dispatch @refutor to attack
3. If refutor finds verifiable empirical issues → dispatch @coder mid-debate
4. If refutor finds literature gaps → dispatch @researcher mid-debate
5. Continue debate up to max_rounds (see orchestration.yaml)
6. Dispatch @coder for final empirical test
7. Conclude

### conjecture (conjecture needing proof)
Speculative. Full adversarial treatment.
1. Dispatch @researcher for targeted literature on this specific conjecture
2. Dispatch @thinker with researcher results + deep thinker's framing
3. Full debate cycle (thinker ↔ refutor, up to max_rounds)
4. Dispatch @coder for empirical testing
5. Conclude — MIXED is expected and acceptable here

### experiment (requires experiment)
The answer is empirical, not theoretical.
1. Dispatch @coder to design and run the experiment
2. Dispatch @thinker to interpret results
3. If results are surprising → dispatch @refutor to challenge interpretation
4. Conclude

## Override Points

The default flow follows the maturity routing above. You may override at these points:

### Mid-debate coder dispatch
If during the debate you spot a claim that can be quickly verified empirically,
dispatch @coder before the debate concludes. Write a brief to `coder/results/check-N.md`.

### Mid-debate researcher dispatch
If you spot an unverified literature reference, dispatch @researcher with a
targeted question. Save results to `researcher/results/targeted-N.md`.

### Severity override
If the refutor rates severity as minor but you judge it's actually serious
(or vice versa), state your reasoning and proceed accordingly.

### Early termination
If the debate is clearly resolved before max_rounds, skip remaining rounds
and proceed to empirical testing.

### Conclusion
The verdict is always YOUR judgment. Base it on the full body of evidence.
A clean falsification with clear reasoning is as valuable as settling a claim.

## Debate Management

- Use SendMessage to keep thinker and refutor alive across rounds (don't re-dispatch)
- Send the refutor's attack to the thinker for round 2+, with your guidance
- Send the thinker's revised proposal to the refutor for the next attack
- The refutor always gets the final say before the coder phase

## What Makes a Good Result

A cycle should produce a clear conclusion, not just activity:
- **SETTLED**: "We established X because [evidence]"
- **FALSIFIED**: "X doesn't work because [evidence]. Specifically, [what breaks and why]"
- **MIXED**: "X partially works under conditions [Y] but fails under [Z]. To resolve, we need [specific evidence]"

All three are valid, productive outcomes.
