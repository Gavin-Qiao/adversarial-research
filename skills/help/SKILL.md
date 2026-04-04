---
name: help
description: Show an overview of what Principia can do and how to get started. Use when the user asks for help, asks what commands are available, or seems unsure how to use the plugin.
---

# Principia Help

Present this guide to the user:

---

**Principia** turns a philosophical principle into a working algorithm through adversarial testing.

## Getting Started

```
/principia:init "Your project title"
/principia:design "Your principle or insight here"
```

That's it. Principia runs 4 phases automatically:

1. **Understand** -- refines your principle, surveys the research landscape
2. **Divide** -- decomposes into testable claims with dependency ordering
3. **Test** -- each claim goes through adversarial debate, then empirical experiment, then verdict
4. **Synthesize** -- composes surviving claims into a unified theory

Add `--quick` for a fast single-claim investigation (1 debate round, no deep research).

## Commands

| Command | What it does |
|---------|-------------|
| `/principia:init [title]` | Set up a new design project |
| `/principia:design "<principle>"` | Full pipeline: principle to algorithm |
| `/principia:design "<principle>" --quick` | Quick mode: 1 round, 1 claim, fast results |
| `/principia:step` | Advance one step manually (for fine-grained control) |
| `/principia:status` | Show current progress, blockers, and proven claims |
| `/principia:impact <id>` | Preview: what breaks if this claim is disproven? |
| `/principia:query "<sql>"` | Query the evidence database directly |
| `/principia:methodology` | Reference: how the design methodology works |
| `/principia:help` | This guide |

## Agents

Principia uses 8 agents:

- **@architect** -- proposes designs (no codebase access, reasons from theory)
- **@adversary** -- attacks designs (no codebase access, finds flaws)
- **@experimenter** -- tests claims empirically with real code
- **@arbiter** -- evaluates all evidence and renders verdict
- **@conductor** -- orchestrates a full claim cycle automatically
- **@synthesizer** -- decomposes principles into claims (Divide) and unifies findings (Synthesize)
- **@scout** -- surveys prior art and literature
- **@deep-thinker** -- hard math/theory reasoning (available in any phase)

## Modes

- **Checkpoints** (default): pauses between phases for your input
- **Yolo**: runs fully automated, designed for overnight runs. Set `autonomy.mode: yolo` in `config/orchestration.yaml`

## Tips

- Start with `/principia:design` for the full experience
- Use `--quick` if you have a focused question and want a fast answer
- Use `/principia:step` if you want to control each agent dispatch manually
- Use `/principia:status` any time to see where things stand
- The conductor can extend debate rounds if the adversary keeps finding serious flaws
- Every state change is tracked in the research log -- your investigation history is never lost

## Example

```
/principia:init "Topological Enrichment"
/principia:design "Persistent homology captures information that clustering
algorithms discard. An algorithm that preserves topological features during
hierarchical merging should produce more faithful cluster boundaries."
```

For more details, see the [README](https://github.com/Gavin-Qiao/principia).
