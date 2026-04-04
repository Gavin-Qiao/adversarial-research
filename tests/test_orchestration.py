"""Comprehensive test suite for the orchestration engine.

Tests the config-driven state machine, severity/verdict extraction,
context assembly, dispatch config, path computation, and YAML parsing.
"""

from pathlib import Path

from orchestration import (
    DEFAULT_CONFIG,
    _parse_yaml_value,
    attenuate_confidence,
    check_waiting,
    compute_paths,
    detect_investigation_state,
    detect_state,
    extract_confidence,
    extract_severity,
    extract_verdict,
    find_completed_rounds,
    list_context_files,
    load_config,
    parse_framework,
    read_autonomy_config,
    read_dispatch_config,
    suggest_next,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_claim(research_dir, claim_rel="claims/claim-1-test"):
    """Create a claim directory structure with canonical role names."""
    claim = research_dir / claim_rel
    for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
        (claim / role).mkdir(parents=True, exist_ok=True)
    claim_md = claim / "claim.md"
    if not claim_md.exists():
        claim_md.write_text("---\nid: h1-test\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test\n")
    return claim_rel


def write_result(research_dir, rel_path, content="# Result\n\nTest content.", severity=None, verdict=None):
    """Write a result file with optional severity/verdict fields."""
    full = research_dir / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    body = content
    if severity:
        body += f"\n\n**Severity**: {severity}\n"
    if verdict:
        body += f"\n\n**Verdict**: {verdict}\n"
    full.write_text(f"---\nid: test\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n{body}")


# ---------------------------------------------------------------------------
# State Machine Tests
# ---------------------------------------------------------------------------


class TestDetectState:
    def test_empty_claim(self, research_dir):
        """No files -> dispatch_architect round 1"""
        sub = make_claim(research_dir)
        config = DEFAULT_CONFIG
        state = detect_state(research_dir, sub, config)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 1
        assert state["phase"] == "debate"

    def test_architect_r1_done(self, research_dir):
        """Architect R1 exists -> dispatch_adversary round 1"""
        sub = make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_adversary"
        assert state["round"] == 1

    def test_adversary_fatal_continues(self, research_dir):
        """Fatal adversary -> dispatch_architect round 2"""
        sub = make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Fatal (blocks the approach)")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 2

    def test_adversary_serious_continues(self, research_dir):
        sub = make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Serious (requires modification)")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 2

    def test_adversary_minor_exits(self, research_dir):
        """Minor adversary -> dispatch_experimenter"""
        sub = make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Minor (worth noting)")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_experimenter"
        assert state["phase"] == "experiment"

    def test_adversary_none_exits(self, research_dir):
        sub = make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", content="No genuine flaws found.")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_experimenter"

    def test_adversary_unknown_defaults_continue(self, research_dir):
        """Unknown severity with default=continue -> architect R2"""
        sub = make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", content="Some vague criticism.")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"
        assert state.get("severity") == "unknown"

    def test_round_3_forces_experimenter(self, research_dir):
        """After round 3, always dispatch experimenter regardless of severity"""
        sub = make_claim(research_dir)
        for r in range(1, 4):
            write_result(research_dir, f"{sub}/architect/round-{r}/result.md")
            write_result(research_dir, f"{sub}/adversary/round-{r}/result.md", severity="Fatal")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_experimenter"

    def test_experimenter_done_dispatches_arbiter(self, research_dir):
        sub = make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Minor")
        write_result(research_dir, f"{sub}/experimenter/results/output.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_arbiter"
        assert state["phase"] == "verdict"

    def test_verdict_dispatches_post_verdict(self, research_dir):
        sub = make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Minor")
        write_result(research_dir, f"{sub}/experimenter/results/output.md")
        write_result(research_dir, f"{sub}/arbiter/results/verdict.md", verdict="PROVEN")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "post_verdict"
        assert state["phase"] == "recording"

    def test_verdict_dispatches_reviewer_when_auto_review_false(self, research_dir):
        sub = make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Minor")
        write_result(research_dir, f"{sub}/experimenter/results/output.md")
        write_result(research_dir, f"{sub}/arbiter/results/verdict.md", verdict="PROVEN")
        config = {**DEFAULT_CONFIG, "auto_review": False}
        state = detect_state(research_dir, sub, config)
        assert state["action"] == "dispatch_reviewer"
        assert state["phase"] == "recording"

    def test_nonexistent_claim(self, research_dir):
        state = detect_state(research_dir, "claims/nonexistent", DEFAULT_CONFIG)
        assert state["action"] == "error"


# ---------------------------------------------------------------------------
# Severity Tests
# ---------------------------------------------------------------------------


class TestExtractSeverity:
    def test_fatal_structured(self, tmp_path):
        f = tmp_path / "result.md"
        f.write_text("**Severity**: Fatal (blocks the approach)\n")
        assert extract_severity(f, DEFAULT_CONFIG) == "fatal"

    def test_serious_structured(self, tmp_path):
        f = tmp_path / "result.md"
        f.write_text("**Severity**: Serious (requires modification)\n")
        assert extract_severity(f, DEFAULT_CONFIG) == "serious"

    def test_minor_structured(self, tmp_path):
        f = tmp_path / "result.md"
        f.write_text("**Severity**: Minor (worth noting)\n")
        assert extract_severity(f, DEFAULT_CONFIG) == "minor"

    def test_keyword_fallback(self, tmp_path):
        f = tmp_path / "result.md"
        f.write_text("This fundamentally flawed approach cannot work.\n")
        assert extract_severity(f, DEFAULT_CONFIG) == "fatal"

    def test_malformed(self, tmp_path):
        f = tmp_path / "result.md"
        f.write_text("Some text without severity indicators.\n")
        assert extract_severity(f, DEFAULT_CONFIG) == "unknown"

    def test_missing_file(self, tmp_path):
        assert extract_severity(tmp_path / "nonexistent.md", DEFAULT_CONFIG) == "unknown"

    def test_no_fatal_is_none_not_fatal(self, tmp_path):
        """Regression: 'no fatal flaws' must match 'none', not 'fatal'."""
        f = tmp_path / "result.md"
        f.write_text("The design has no fatal flaws and is generally sound.\n")
        assert extract_severity(f, DEFAULT_CONFIG) == "none"


# ---------------------------------------------------------------------------
# Verdict Tests
# ---------------------------------------------------------------------------


class TestExtractVerdict:
    def test_proven(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("**Verdict**: PROVEN\n")
        assert extract_verdict(f, DEFAULT_CONFIG) == "PROVEN"

    def test_disproven(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("**Verdict**: DISPROVEN\n")
        assert extract_verdict(f, DEFAULT_CONFIG) == "DISPROVEN"

    def test_partial(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("**Verdict**: PARTIAL\n")
        assert extract_verdict(f, DEFAULT_CONFIG) == "PARTIAL"

    def test_malformed(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("No verdict here.\n")
        assert extract_verdict(f, DEFAULT_CONFIG) == "UNKNOWN"

    def test_missing(self, tmp_path):
        assert extract_verdict(tmp_path / "nope.md", DEFAULT_CONFIG) == "UNKNOWN"

    def test_inconclusive(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("**Verdict**: INCONCLUSIVE\n")
        assert extract_verdict(f, DEFAULT_CONFIG) == "INCONCLUSIVE"

    def test_inconclusive_in_prose(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("## Analysis\n\nAfter review...\n\n**Verdict**: INCONCLUSIVE — insufficient evidence\n")
        assert extract_verdict(f, DEFAULT_CONFIG) == "INCONCLUSIVE"


class TestExtractConfidence:
    def test_high(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("**Verdict**: SETTLED\n\n**Confidence**: high\n")
        assert extract_confidence(f) == "high"

    def test_moderate(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("**Confidence**: moderate\n")
        assert extract_confidence(f) == "moderate"

    def test_low(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("**Confidence**: low\n")
        assert extract_confidence(f) == "low"

    def test_missing(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("**Verdict**: SETTLED\n")
        assert extract_confidence(f) == "unknown"

    def test_missing_file(self, tmp_path):
        assert extract_confidence(tmp_path / "nope.md") == "unknown"

    def test_bold_format(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("**Confidence**: **high**\n")
        assert extract_confidence(f) == "high"


class TestAttenuateConfidence:
    def test_high_to_moderate(self):
        assert attenuate_confidence("high") == "moderate"

    def test_moderate_to_low(self):
        assert attenuate_confidence("moderate") == "low"

    def test_low_stays_low(self):
        assert attenuate_confidence("low") == "low"

    def test_unknown_to_low(self):
        assert attenuate_confidence("unknown") == "low"

    def test_none_to_low(self):
        assert attenuate_confidence(None) == "low"


# ---------------------------------------------------------------------------
# Context Tests
# ---------------------------------------------------------------------------


class TestContextFiles:
    def test_round_1_architect(self, research_dir):
        """Round 1 architect needs only claim.md"""
        sub = make_claim(research_dir)
        files = list_context_files(research_dir, sub, "dispatch_architect", 1)
        assert any("claim.md" in f for f in files)
        assert not any("architect" in f and "round" in f for f in files)

    def test_round_1_adversary(self, research_dir):
        """Round 1 adversary needs claim.md + architect R1"""
        sub = make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        files = list_context_files(research_dir, sub, "dispatch_adversary", 1)
        assert any("architect/round-1/result.md" in f for f in files)

    def test_experimenter_gets_all_rounds(self, research_dir):
        """Experimenter gets claim.md + all debate rounds"""
        sub = make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md")
        write_result(research_dir, f"{sub}/architect/round-2/result.md")
        write_result(research_dir, f"{sub}/adversary/round-2/result.md")
        files = list_context_files(research_dir, sub, "dispatch_experimenter", None)
        assert len([f for f in files if "architect" in f or "adversary" in f]) == 4

    def test_reviewer_gets_verdict(self, research_dir):
        """Reviewer context includes arbiter verdict"""
        sub = make_claim(research_dir)
        write_result(research_dir, f"{sub}/arbiter/results/verdict.md")
        files = list_context_files(research_dir, sub, "dispatch_reviewer", None)
        assert any("verdict.md" in f for f in files)


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------


class TestConfig:
    def test_load_default(self):
        config = load_config(None)
        assert "debate_loop" in config

    def test_load_yaml_file(self):
        config_path = Path(__file__).resolve().parent.parent / "config" / "orchestration.yaml"
        config = load_config(config_path)
        assert config["debate_loop"]["max_rounds"] == 3

    def test_custom_max_rounds(self, research_dir):
        """Modified max_rounds should affect state machine"""
        sub = make_claim(research_dir)
        config = DEFAULT_CONFIG.copy()
        config["debate_loop"] = {**config["debate_loop"], "max_rounds": 1}
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Fatal")
        state = detect_state(research_dir, sub, config)
        # With max_rounds=1, even fatal severity goes to experimenter
        assert state["action"] == "dispatch_experimenter"

    def test_max_rounds_zero_skips_debate(self, research_dir):
        """max_rounds=0 should skip debate entirely and go to experimenter"""
        sub = make_claim(research_dir)
        config = DEFAULT_CONFIG.copy()
        config["debate_loop"] = {**config["debate_loop"], "max_rounds": 0}
        state = detect_state(research_dir, sub, config)
        assert state["action"] == "dispatch_experimenter"
        assert state["phase"] == "experiment"


# ---------------------------------------------------------------------------
# Compute Paths Tests
# ---------------------------------------------------------------------------


class TestComputePaths:
    def test_architect_round(self):
        paths = compute_paths("claims/claim-1-test", "architect", 2)
        assert "architect/round-2/prompt.md" in paths["prompt_path"]
        assert "architect/round-2/result.md" in paths["result_path"]

    def test_experimenter(self):
        paths = compute_paths("claims/claim-1-test", "experimenter", None)
        assert "experimenter/results/output.md" in paths["result_path"]

    def test_arbiter(self):
        paths = compute_paths("claims/claim-1-test", "arbiter", None)
        assert "arbiter/results/verdict.md" in paths["result_path"]


# ---------------------------------------------------------------------------
# Dispatch Config Tests
# ---------------------------------------------------------------------------


class TestDispatchConfig:
    def test_defaults(self, research_dir):
        config = read_dispatch_config(research_dir)
        assert config["architect"] == "internal"
        assert config["arbiter"] == "internal"

    def test_reads_config(self, research_dir):
        (research_dir / ".config.md").write_text("# Config\n- Architect: external\n- Adversary: internal\n")
        config = read_dispatch_config(research_dir)
        assert config["architect"] == "external"
        assert config["adversary"] == "internal"


# ---------------------------------------------------------------------------
# Suggest Next Tests
# ---------------------------------------------------------------------------


class TestSuggestNext:
    def test_proven(self):
        s = suggest_next("PROVEN", "sub-1a", DEFAULT_CONFIG)
        assert s["action"] == "complete"
        assert "proven" in s["message"].lower()

    def test_partial(self):
        s = suggest_next("PARTIAL", "sub-1a", DEFAULT_CONFIG)
        assert s["action"] == "prompt_user"
        assert len(s["options"]) > 0

    def test_inconclusive(self):
        s = suggest_next("INCONCLUSIVE", "sub-1a", DEFAULT_CONFIG)
        assert s["action"] == "prompt_user"
        assert len(s["options"]) > 0


# ---------------------------------------------------------------------------
# Find Completed Rounds Tests
# ---------------------------------------------------------------------------


class TestFindCompletedRounds:
    def test_no_dir(self, tmp_path):
        assert find_completed_rounds(tmp_path / "nonexistent") == []

    def test_with_rounds(self, tmp_path):
        for r in [1, 3, 2]:  # intentionally out of order
            d = tmp_path / f"round-{r}"
            d.mkdir()
            (d / "result.md").write_text("content")
        assert find_completed_rounds(tmp_path) == [1, 2, 3]

    def test_incomplete_round(self, tmp_path):
        d = tmp_path / "round-1"
        d.mkdir()
        (d / "prompt.md").write_text("prompt only")
        assert find_completed_rounds(tmp_path) == []


# ---------------------------------------------------------------------------
# Waiting Tests
# ---------------------------------------------------------------------------


class TestWaiting:
    def test_not_waiting(self, tmp_path):
        d = tmp_path / "round-1"
        d.mkdir()
        (d / "result.md").write_text("done")
        assert check_waiting(tmp_path, 1) is None

    def test_waiting(self, tmp_path):
        d = tmp_path / "round-1"
        d.mkdir()
        (d / "prompt.md").write_text("waiting for external")
        result = check_waiting(tmp_path, 1)
        assert result is not None
        assert "round 1" in result


# ---------------------------------------------------------------------------
# YAML Parser Tests
# ---------------------------------------------------------------------------


class TestYamlParser:
    def test_inline_comments_stripped(self):
        assert _parse_yaml_value("3                   # hard cap") == 3
        assert _parse_yaml_value("true  # boolean") is True
        assert _parse_yaml_value("refutor  # who gets last word") == "refutor"


# ---------------------------------------------------------------------------
# Parse Framework Tests
# ---------------------------------------------------------------------------

SAMPLE_FRAMEWORK = """\
# Research Framework

Some prose about the investigation.

## Claims

```yaml
# CLAIM_REGISTRY
claims:
  - id: enrichment-bound
    statement: "The enrichment functional has a tight upper bound"
    maturity: supported
    confidence: high
    depends_on: []
    falsification: "Find a sequence exceeding the proposed bound"
  - id: bottleneck-ratio
    statement: "The bottleneck ratio governs convergence rate"
    maturity: conjecture
    confidence: moderate
    depends_on: [enrichment-bound]
    falsification: "Construct a counterexample with divergent bottleneck ratio"
```

## Open Problems

More prose.
"""

FRAMEWORK_NO_REGISTRY = """\
# Research Framework

Some prose with no claim registry YAML block.

## Claims

These are described in text only.
"""

FRAMEWORK_MALFORMED = """\
# Research Framework

```yaml
# CLAIM_REGISTRY
claims:
  - this is not valid yaml mapping
  - id: missing-colon
    statement
```

Done.
"""


class TestParseFramework:
    def test_valid_block(self, tmp_path):
        f = tmp_path / "framework.md"
        f.write_text(SAMPLE_FRAMEWORK)
        claims = parse_framework(f)
        assert len(claims) == 2
        assert claims[0]["id"] == "enrichment-bound"
        assert claims[0]["maturity"] == "supported"
        assert claims[0]["confidence"] == "high"
        assert claims[0]["depends_on"] == []
        assert claims[1]["id"] == "bottleneck-ratio"
        assert claims[1]["depends_on"] == ["enrichment-bound"]

    def test_no_block(self, tmp_path):
        f = tmp_path / "framework.md"
        f.write_text(FRAMEWORK_NO_REGISTRY)
        assert parse_framework(f) == []

    def test_missing_file(self, tmp_path):
        assert parse_framework(tmp_path / "nonexistent.md") == []

    def test_malformed_yaml(self, tmp_path):
        f = tmp_path / "framework.md"
        f.write_text(FRAMEWORK_MALFORMED)
        # Should not crash, returns whatever it can parse
        claims = parse_framework(f)
        # May return partial or empty — just must not raise
        assert isinstance(claims, list)

    def test_single_claim(self, tmp_path):
        f = tmp_path / "framework.md"
        f.write_text("""\
# Framework

```yaml
# CLAIM_REGISTRY
claims:
  - id: solo-claim
    statement: "A single claim"
    maturity: experiment
    confidence: low
    falsification: "Run the experiment"
```
""")
        claims = parse_framework(f)
        assert len(claims) == 1
        assert claims[0]["id"] == "solo-claim"
        assert claims[0]["maturity"] == "experiment"
        assert claims[0]["depends_on"] == []


# ---------------------------------------------------------------------------
# Investigation State Machine Tests
# ---------------------------------------------------------------------------


def _make_investigation_dir(tmp_path):
    """Create base research structure for investigation tests."""
    for d in ["context/assumptions", "claims", ".db"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return tmp_path


class TestDetectInvestigationState:
    def test_empty_returns_understand(self, tmp_path):
        rd = _make_investigation_dir(tmp_path)
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "understand"
        assert state["phase"] == "understand"
        assert "discuss" in state["substeps"]
        assert "inspect" in state["substeps"]
        assert "research" in state["substeps"]

    def test_north_star_only_returns_understand_without_discuss(self, tmp_path):
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# Topology-preserving clustering\n")
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "understand"
        assert "discuss" not in state["substeps"]
        assert "inspect" in state["substeps"]
        assert "research" in state["substeps"]

    def test_north_star_and_context_returns_understand_research_only(self, tmp_path):
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# Topology-preserving clustering\n")
        (rd / ".context.md").write_text("# Context\n\nExisting code survey.\n")
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "understand"
        assert state["substeps"] == ["research"]

    def test_all_understand_outputs_returns_divide(self, tmp_path):
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# Topology-preserving clustering\n")
        (rd / ".context.md").write_text("# Context\n")
        (rd / "context" / "survey-topology.md").write_text("# Literature Survey\n\nContent.")
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "divide"
        assert state["phase"] == "divide"
        assert ".north-star.md" in state["context_files"][0]

    def test_with_blueprint_returns_scaffold(self, tmp_path):
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "survey-topic.md").write_text("# Survey\n")
        (rd / "blueprint.md").write_text(SAMPLE_FRAMEWORK)
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "scaffold"
        assert len(state["claims"]) == 2

    def test_scaffolded_claims_returns_test_claim(self, tmp_path):
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "survey-topic.md").write_text("# Survey\n")
        (rd / "blueprint.md").write_text(SAMPLE_FRAMEWORK)
        for claim_id in ["enrichment-bound", "bottleneck-ratio"]:
            claim_dir = rd / "claims" / f"claim-1-{claim_id}"
            for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
                (claim_dir / role).mkdir(parents=True, exist_ok=True)
            (claim_dir / "claim.md").write_text(
                f"---\nid: h1-claim\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# {claim_id}\n"
            )
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "test_claim"
        assert "sub_unit" in state

    def test_claim_done_returns_record_verdict(self, tmp_path):
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "survey-topic.md").write_text("# Survey\n")
        (rd / "blueprint.md").write_text("""\
# Blueprint

```yaml
# CLAIM_REGISTRY
claims:
  - id: test-claim
    statement: "Test"
    maturity: conjecture
    confidence: moderate
    falsification: "Disprove it"
```
""")
        claim_dir = rd / "claims" / "claim-1-test-claim"
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (claim_dir / role).mkdir(parents=True, exist_ok=True)
        (claim_dir / "claim.md").write_text(
            "---\nid: test\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test\n"
        )
        # Add architect + adversary + experimenter + verdict (complete but no post-verdict)
        a_dir = claim_dir / "architect" / "round-1"
        a_dir.mkdir(parents=True, exist_ok=True)
        (a_dir / "result.md").write_text(
            "---\nid: t\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Proposal\n"
        )
        r_dir = claim_dir / "adversary" / "round-1"
        r_dir.mkdir(parents=True, exist_ok=True)
        (r_dir / "result.md").write_text(
            "---\nid: r\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Attack\n\n**Severity**: minor\n"
        )
        (claim_dir / "experimenter" / "results").mkdir(parents=True, exist_ok=True)
        (claim_dir / "experimenter" / "results" / "output.md").write_text(
            "---\nid: c\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n# Evidence\n"
        )
        (claim_dir / "arbiter" / "results").mkdir(parents=True, exist_ok=True)
        (claim_dir / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: v\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n# Verdict\n\n**Verdict**: PROVEN\n"
        )
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "record_verdict"

    def test_all_done_returns_synthesize(self, tmp_path):
        """When all claims complete, returns synthesize (merging old compose+synthesize)."""
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "survey-topic.md").write_text("# Survey\n")
        (rd / "blueprint.md").write_text("""\
# Blueprint

```yaml
# CLAIM_REGISTRY
claims:
  - id: done-claim
    statement: "Done"
    maturity: supported
    confidence: high
    falsification: "N/A"
```
""")
        claim_dir = rd / "claims" / "claim-1-done-claim"
        for role in ("architect", "adversary", "experimenter", "arbiter"):
            (claim_dir / role).mkdir(parents=True, exist_ok=True)
        (claim_dir / "claim.md").write_text(
            "---\nid: test\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Done\n"
        )
        a_dir = claim_dir / "architect" / "round-1"
        a_dir.mkdir(parents=True, exist_ok=True)
        (a_dir / "result.md").write_text("---\nid: t\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# T\n")
        r_dir = claim_dir / "adversary" / "round-1"
        r_dir.mkdir(parents=True, exist_ok=True)
        (r_dir / "result.md").write_text(
            "---\nid: r\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# R\n\n**Severity**: minor\n"
        )
        (claim_dir / "experimenter" / "results").mkdir(parents=True, exist_ok=True)
        (claim_dir / "experimenter" / "results" / "output.md").write_text(
            "---\nid: c\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n# Evidence\n"
        )
        (claim_dir / "arbiter" / "results").mkdir(parents=True, exist_ok=True)
        (claim_dir / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: v\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n# Verdict\n\n**Verdict**: PROVEN\n"
        )
        # Mark post-verdict done
        (claim_dir / ".post_verdict_done").write_text("")
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        # v0.3 merges compose+synthesize into single synthesize action
        assert state["action"] == "synthesize"
        assert state["phase"] == "synthesize"
        assert "proven_claims" in state

    def test_complete_with_synthesis(self, tmp_path):
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "survey-topic.md").write_text("# Survey\n")
        (rd / "blueprint.md").write_text("""\
# Blueprint

```yaml
# CLAIM_REGISTRY
claims:
  - id: final-claim
    statement: "Final"
    maturity: supported
    confidence: high
    falsification: "N/A"
```
""")
        claim_dir = rd / "claims" / "claim-1-final-claim"
        for role in ("architect", "adversary", "experimenter", "arbiter"):
            (claim_dir / role).mkdir(parents=True, exist_ok=True)
        (claim_dir / "claim.md").write_text(
            "---\nid: test\ntype: verdict\nstatus: proven\ndate: 2026-01-01\n---\n\n# Final\n"
        )
        a_dir = claim_dir / "architect" / "round-1"
        a_dir.mkdir(parents=True, exist_ok=True)
        (a_dir / "result.md").write_text("---\nid: t\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# T\n")
        r_dir = claim_dir / "adversary" / "round-1"
        r_dir.mkdir(parents=True, exist_ok=True)
        (r_dir / "result.md").write_text(
            "---\nid: r\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# R\n\n**Severity**: minor\n"
        )
        (claim_dir / "experimenter" / "results").mkdir(parents=True, exist_ok=True)
        (claim_dir / "experimenter" / "results" / "output.md").write_text("# Evidence\n")
        (claim_dir / "arbiter" / "results").mkdir(parents=True, exist_ok=True)
        (claim_dir / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: v\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n**Verdict**: PROVEN\n"
        )
        # Mark post-verdict done
        (claim_dir / ".post_verdict_done").write_text("")
        (rd / "synthesis.md").write_text("# Final Synthesis\n")
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "complete"
        assert state["phase"] == "complete"

    def test_distillation_glob_counts_as_research(self, tmp_path):
        """survey-*.md OR distillation-*.md counts as research done."""
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "distillation-topic.md").write_text("# Survey\n")
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "divide"

    def test_blueprint_with_no_claims(self, tmp_path):
        """Blueprint exists but has no CLAIM_REGISTRY — should still return scaffold with empty claims."""
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "survey-topic.md").write_text("# Survey\n")
        (rd / "blueprint.md").write_text("# Blueprint\n\nJust prose, no YAML block.\n")
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "scaffold"
        assert state["claims"] == []

    def test_partially_scaffolded_cycles(self, tmp_path):
        """Some claims scaffolded, some not — should return scaffold with unscaffolded only."""
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "survey-topic.md").write_text("# Survey\n")
        (rd / "blueprint.md").write_text(SAMPLE_FRAMEWORK)
        # Only scaffold the first claim (enrichment-bound), not bottleneck-ratio
        claim_dir = rd / "claims" / "claim-1-enrichment-bound"
        claim_dir.mkdir(parents=True)
        (claim_dir / "claim.md").write_text(
            "---\nid: h1-claim\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Enrichment\n"
        )
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "scaffold"
        # Only the unscaffolded claim should be in the list
        assert len(state["claims"]) == 1
        assert state["claims"][0]["id"] == "bottleneck-ratio"


# ---------------------------------------------------------------------------
# Full-cycle integration test
# ---------------------------------------------------------------------------


class TestQuickMode:
    """Test --quick investigation mode."""

    def test_quick_without_north_star_returns_understand(self, tmp_path):
        """Quick mode still requires discuss + inspect (just skips research)."""
        rd = _make_investigation_dir(tmp_path)
        state = detect_investigation_state(rd, DEFAULT_CONFIG, quick=True)
        assert state["action"] == "understand"
        assert "discuss" in state["substeps"]
        assert "research" not in state["substeps"]  # skipped in quick mode

    def test_quick_with_understand_done_returns_scaffold_quick(self, tmp_path):
        """Quick mode skips divide (no blueprint), goes straight to scaffold."""
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# Quick test\n")
        (rd / ".context.md").write_text("# Context\n")
        state = detect_investigation_state(rd, DEFAULT_CONFIG, quick=True)
        assert state["action"] == "scaffold_quick"
        assert state["phase"] == "divide"

    def test_quick_scaffolded_returns_test_claim(self, tmp_path):
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# Quick\n")
        (rd / ".context.md").write_text("# C\n")
        claim_dir = rd / "claims" / "claim-1-quick-test"
        for role in ("architect", "adversary", "experimenter", "arbiter"):
            (claim_dir / role).mkdir(parents=True, exist_ok=True)
        (claim_dir / "claim.md").write_text(
            "---\nid: test\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Quick\n"
        )
        config = {**DEFAULT_CONFIG, "debate_loop": {**DEFAULT_CONFIG["debate_loop"], "max_rounds": 1}}
        state = detect_investigation_state(rd, config, quick=True)
        assert state["action"] == "test_claim"


class TestFullCycleIntegration:
    """Walk the complete state machine through all phases to completion."""

    def test_full_cycle_minor_severity(self, research_dir):
        """A simple 1-round debate with Minor severity goes straight to experimenter."""
        sub = make_claim(research_dir)

        # Step 1: Empty claim -> dispatch_architect
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 1

        # Step 2: Architect done -> dispatch_adversary
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_adversary"
        assert state["round"] == 1

        # Step 3: Adversary (Minor) -> dispatch_experimenter (exits debate)
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Minor")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_experimenter"

        # Step 4: Experimenter done -> dispatch_arbiter
        write_result(research_dir, f"{sub}/experimenter/results/output.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_arbiter"

        # Step 5: Arbiter verdict -> post_verdict
        write_result(research_dir, f"{sub}/arbiter/results/verdict.md", verdict="PROVEN")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "post_verdict"
        assert state["phase"] == "recording"

        # Step 6: Mark post-verdict done
        (research_dir / sub / ".post_verdict_done").write_text("")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "complete_proven"
        assert state["phase"] == "complete"

    def test_full_cycle_fatal_continues_debate(self, research_dir):
        """Fatal severity triggers round 2 before experimenter."""
        sub = make_claim(research_dir)

        # Architect round 1
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        # Adversary round 1 (Fatal)
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Fatal")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 2

        # Architect round 2
        write_result(research_dir, f"{sub}/architect/round-2/result.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_adversary"
        assert state["round"] == 2

        # Adversary round 2 (Minor) -> exits to experimenter
        write_result(research_dir, f"{sub}/adversary/round-2/result.md", severity="Minor")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_experimenter"


class TestFindActiveSubunitFlatClaims:
    def test_finds_flat_claim(self, tmp_path):
        """find_active_subunit finds claims in claims/ directory."""
        from manage import build_db, init_paths, serialise_frontmatter

        rd = tmp_path
        for d in ["claims", "context/assumptions", ".db"]:
            (rd / d).mkdir(parents=True, exist_ok=True)
        init_paths(rd)

        # Create a flat claim
        claim_dir = rd / "claims" / "claim-1-test"
        for role in ("architect", "adversary", "experimenter", "arbiter"):
            (claim_dir / role).mkdir(parents=True)
        (claim_dir / "claim.md").write_text(
            serialise_frontmatter(
                {
                    "id": "h1-claim",
                    "type": "verdict",
                    "status": "pending",
                    "date": "2026-01-01",
                }
            )
            + "\n\n# Test\n"
        )

        # Build DB so the node exists
        build_db()

        from orchestration import find_active_subunit

        result = find_active_subunit(rd, rd / ".db" / "research.db")
        assert result is not None, "find_active_subunit should find flat claims"
        assert "claims/claim-1-test" in result


class TestReadAutonomyConfig:
    """Tests for read_autonomy_config()."""

    def test_defaults_when_no_file(self):
        """Without a config file, defaults to checkpoints mode."""
        result = read_autonomy_config(Path("/nonexistent/config.yaml"))
        assert result["mode"] == "checkpoints"
        assert result["checkpoint_at"] == ["understand", "divide", "test", "synthesize"]

    def test_reads_yolo_mode(self, tmp_path):
        """Reads yolo mode from config file."""
        config = tmp_path / "config.yaml"
        config.write_text("autonomy:\n  mode: yolo\n  checkpoint_at: [understand, synthesize]\n")
        result = read_autonomy_config(config)
        assert result["mode"] == "yolo"
        assert result["checkpoint_at"] == ["understand", "synthesize"]

    def test_missing_autonomy_section(self, tmp_path):
        """Config without autonomy section falls back to defaults."""
        config = tmp_path / "config.yaml"
        config.write_text("debate_loop:\n  max_rounds: 3\n")
        result = read_autonomy_config(config)
        assert result["mode"] == "checkpoints"
        assert result["checkpoint_at"] == ["understand", "divide", "test", "synthesize"]


class TestExtendDebate:
    """Tests for conductor extend-debate override."""

    def test_override_extends_rounds(self, research_dir):
        """A .max_rounds_override file extends debate past config max_rounds."""
        sub_rel = make_claim(research_dir)
        sub_path = research_dir / sub_rel
        config = DEFAULT_CONFIG.copy()
        config["debate_loop"] = {"max_rounds": 2, "sequence": ["architect", "adversary"]}

        # Create 2 rounds of debate (hits max_rounds=2)
        for r in range(1, 3):
            (sub_path / "architect" / f"round-{r}").mkdir(parents=True, exist_ok=True)
            (sub_path / "architect" / f"round-{r}" / "result.md").write_text(f"Design {r}")
            (sub_path / "adversary" / f"round-{r}").mkdir(parents=True, exist_ok=True)
            (sub_path / "adversary" / f"round-{r}" / "result.md").write_text("Severity: Fatal\n")

        # Without override: should dispatch experimenter (max_rounds hit)
        state = detect_state(research_dir, sub_rel, config)
        assert state["action"] == "dispatch_experimenter"

        # With override: should continue debate
        (sub_path / ".max_rounds_override").write_text("5")
        state = detect_state(research_dir, sub_rel, config)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 3

    def test_invalid_override_ignored(self, research_dir):
        """A malformed override file falls back to config max_rounds."""
        sub_rel = make_claim(research_dir)
        sub_path = research_dir / sub_rel
        config = DEFAULT_CONFIG.copy()
        config["debate_loop"] = {"max_rounds": 1, "sequence": ["architect", "adversary"]}

        (sub_path / "architect" / "round-1").mkdir(parents=True, exist_ok=True)
        (sub_path / "architect" / "round-1" / "result.md").write_text("Design")
        (sub_path / "adversary" / "round-1").mkdir(parents=True, exist_ok=True)
        (sub_path / "adversary" / "round-1" / "result.md").write_text("Severity: Fatal\n")

        # Invalid override content
        (sub_path / ".max_rounds_override").write_text("not-a-number")
        state = detect_state(research_dir, sub_rel, config)
        assert state["action"] == "dispatch_experimenter"
