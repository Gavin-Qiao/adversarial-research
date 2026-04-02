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
    read_dispatch_config,
    suggest_next,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_sub_unit(research_dir, sub_rel="cycles/cycle-1/unit-1-test/sub-1a-direct"):
    """Create a sub-unit directory structure."""
    sub = research_dir / sub_rel
    for role in ("thinker", "refutor", "coder", "judge", "researcher"):
        (sub / role).mkdir(parents=True, exist_ok=True)
    # Create frontier files
    for frontier_path in [sub.parent / "frontier.md", sub / "frontier.md"]:
        if not frontier_path.exists():
            frontier_path.parent.mkdir(parents=True, exist_ok=True)
            frontier_path.write_text(
                "---\nid: test-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test\n"
            )
    return sub_rel


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
    def test_empty_subunit(self, research_dir):
        """No files -> dispatch_architect round 1"""
        sub = make_sub_unit(research_dir)
        config = DEFAULT_CONFIG
        state = detect_state(research_dir, sub, config)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 1
        assert state["phase"] == "debate"

    def test_thinker_r1_done(self, research_dir):
        """Thinker R1 exists -> dispatch_adversary round 1"""
        sub = make_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_adversary"
        assert state["round"] == 1

    def test_refutor_fatal_continues(self, research_dir):
        """Fatal refutor -> dispatch_architect round 2"""
        sub = make_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Fatal (blocks the approach)")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 2

    def test_refutor_serious_continues(self, research_dir):
        sub = make_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Serious (requires modification)")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 2

    def test_refutor_minor_exits(self, research_dir):
        """Minor refutor -> dispatch_experimenter"""
        sub = make_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Minor (worth noting)")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_experimenter"
        assert state["phase"] == "experiment"

    def test_refutor_none_exits(self, research_dir):
        sub = make_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        write_result(research_dir, f"{sub}/refutor/round-1/result.md", content="No genuine flaws found.")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_experimenter"

    def test_refutor_unknown_defaults_continue(self, research_dir):
        """Unknown severity with default=continue -> thinker R2"""
        sub = make_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        write_result(research_dir, f"{sub}/refutor/round-1/result.md", content="Some vague criticism.")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"
        assert state.get("severity") == "unknown"

    def test_round_3_forces_coder(self, research_dir):
        """After round 3, always dispatch coder regardless of severity"""
        sub = make_sub_unit(research_dir)
        for r in range(1, 4):
            write_result(research_dir, f"{sub}/thinker/round-{r}/result.md")
            write_result(research_dir, f"{sub}/refutor/round-{r}/result.md", severity="Fatal")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_experimenter"

    def test_coder_done_dispatches_judge(self, research_dir):
        sub = make_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Minor")
        write_result(research_dir, f"{sub}/coder/results/output.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_arbiter"
        assert state["phase"] == "verdict"

    def test_verdict_dispatches_post_verdict(self, research_dir):
        sub = make_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Minor")
        write_result(research_dir, f"{sub}/coder/results/output.md")
        write_result(research_dir, f"{sub}/judge/results/verdict.md", verdict="SETTLED")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "post_verdict"
        assert state["phase"] == "recording"

    def test_verdict_dispatches_reviewer_when_auto_review_false(self, research_dir):
        sub = make_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Minor")
        write_result(research_dir, f"{sub}/coder/results/output.md")
        write_result(research_dir, f"{sub}/judge/results/verdict.md", verdict="SETTLED")
        config = {**DEFAULT_CONFIG, "auto_review": False}
        state = detect_state(research_dir, sub, config)
        assert state["action"] == "dispatch_reviewer"
        assert state["phase"] == "recording"

    def test_nonexistent_subunit(self, research_dir):
        state = detect_state(research_dir, "cycles/nonexistent/sub-1a", DEFAULT_CONFIG)
        assert state["action"] == "error"


# ---------------------------------------------------------------------------
# Flat Claim Tests (principia hierarchy)
# ---------------------------------------------------------------------------


class TestFlatClaimDetectState:
    """Test detect_state with claims/claim-N-name/ directories (new principia layout)."""

    def _make_claim(self, research_dir, name="enrichment"):
        """Create a flat claim directory with principia role names."""
        claim_dir = research_dir / "claims" / f"claim-1-{name}"
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (claim_dir / role).mkdir(parents=True, exist_ok=True)
        claim_md = claim_dir / "claim.md"
        claim_md.write_text(
            "---\nid: h1-claim\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test Claim\n"
        )
        # Parent frontier (claims/ level)
        return f"claims/claim-1-{name}"

    def test_empty_claim_dispatches_architect(self, research_dir):
        sub = self._make_claim(research_dir)
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 1
        assert state["phase"] == "debate"

    def test_architect_done_dispatches_adversary(self, research_dir):
        sub = self._make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_adversary"

    def test_adversary_minor_dispatches_experimenter(self, research_dir):
        sub = self._make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Minor")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_experimenter"
        assert state["phase"] == "experiment"

    def test_experimenter_done_dispatches_arbiter(self, research_dir):
        sub = self._make_claim(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Minor")
        write_result(research_dir, f"{sub}/experimenter/results/output.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_arbiter"
        assert state["phase"] == "verdict"


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


# ---------------------------------------------------------------------------
# Verdict Tests
# ---------------------------------------------------------------------------


class TestExtractVerdict:
    def test_settled(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("**Verdict**: SETTLED\n")
        assert extract_verdict(f, DEFAULT_CONFIG) == "PROVEN"

    def test_falsified(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("**Verdict**: FALSIFIED\n")
        assert extract_verdict(f, DEFAULT_CONFIG) == "DISPROVEN"

    def test_mixed(self, tmp_path):
        f = tmp_path / "verdict.md"
        f.write_text("**Verdict**: MIXED\n")
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
    def test_round_1_thinker(self, research_dir):
        """Round 1 thinker needs only frontiers"""
        sub = make_sub_unit(research_dir)
        files = list_context_files(research_dir, sub, "dispatch_architect", 1)
        assert any("frontier.md" in f for f in files)
        assert not any("thinker" in f for f in files)

    def test_round_1_refutor(self, research_dir):
        """Round 1 refutor needs frontiers + thinker R1"""
        sub = make_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        files = list_context_files(research_dir, sub, "dispatch_adversary", 1)
        assert any("thinker/round-1/result.md" in f for f in files)

    def test_coder_gets_all_rounds(self, research_dir):
        """Coder gets frontiers + all debate rounds"""
        sub = make_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        write_result(research_dir, f"{sub}/refutor/round-1/result.md")
        write_result(research_dir, f"{sub}/thinker/round-2/result.md")
        write_result(research_dir, f"{sub}/refutor/round-2/result.md")
        files = list_context_files(research_dir, sub, "dispatch_experimenter", None)
        assert len([f for f in files if "thinker" in f or "refutor" in f]) == 4

    def test_reviewer_gets_verdict(self, research_dir):
        """Reviewer context includes judge verdict"""
        sub = make_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/judge/results/verdict.md")
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
        sub = make_sub_unit(research_dir)
        config = DEFAULT_CONFIG.copy()
        config["debate_loop"] = {**config["debate_loop"], "max_rounds": 1}
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Fatal")
        state = detect_state(research_dir, sub, config)
        # With max_rounds=1, even fatal severity goes to coder
        assert state["action"] == "dispatch_experimenter"

    def test_max_rounds_zero_skips_debate(self, research_dir):
        """max_rounds=0 should skip debate entirely and go to coder"""
        sub = make_sub_unit(research_dir)
        config = DEFAULT_CONFIG.copy()
        config["debate_loop"] = {**config["debate_loop"], "max_rounds": 0}
        state = detect_state(research_dir, sub, config)
        assert state["action"] == "dispatch_experimenter"
        assert state["phase"] == "experiment"


# ---------------------------------------------------------------------------
# Compute Paths Tests
# ---------------------------------------------------------------------------


class TestComputePaths:
    def test_thinker_round(self):
        paths = compute_paths("cycles/c1/unit-1/sub-1a", "thinker", 2)
        assert "thinker/round-2/prompt.md" in paths["prompt_path"]
        assert "thinker/round-2/result.md" in paths["result_path"]

    def test_coder(self):
        paths = compute_paths("cycles/c1/unit-1/sub-1a", "coder", None)
        assert "coder/results/output.md" in paths["result_path"]

    def test_judge(self):
        paths = compute_paths("cycles/c1/unit-1/sub-1a", "judge", None)
        assert "judge/results/verdict.md" in paths["result_path"]


# ---------------------------------------------------------------------------
# Dispatch Config Tests
# ---------------------------------------------------------------------------


class TestDispatchConfig:
    def test_defaults(self, research_dir):
        config = read_dispatch_config(research_dir)
        assert config["thinker"] == "internal"
        assert config["judge"] == "internal"

    def test_reads_config(self, research_dir):
        (research_dir / ".config.md").write_text("# Config\n- Thinker: external\n- Refutor: internal\n")
        config = read_dispatch_config(research_dir)
        assert config["thinker"] == "external"
        assert config["refutor"] == "internal"


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
        (a_dir / "result.md").write_text(
            "---\nid: t\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# T\n"
        )
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
            "---\nid: test\ntype: verdict\nstatus: settled\ndate: 2026-01-01\n---\n\n# Final\n"
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

    def test_legacy_distillation_still_works(self, tmp_path):
        """Backward compat: survey-*.md OR distillation-*.md counts as research done."""
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "distillation-topic.md").write_text("# Survey\n")
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "divide"

    def test_legacy_framework_still_works(self, tmp_path):
        """Backward compat: framework.md still detected for divide phase."""
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "survey-topic.md").write_text("# Survey\n")
        (rd / "framework.md").write_text(SAMPLE_FRAMEWORK)
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "scaffold"

    def test_framework_with_no_claims(self, tmp_path):
        """Framework exists but has no CLAIM_REGISTRY — should still return scaffold with empty claims."""
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "survey-topic.md").write_text("# Survey\n")
        (rd / "framework.md").write_text("# Framework\n\nJust prose, no YAML block.\n")
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

    def test_legacy_cycles_dir_returns_test_claim(self, tmp_path):
        """Backward compat: legacy cycles/ directory structure still works."""
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "survey-topic.md").write_text("# Survey\n")
        (rd / "framework.md").write_text(SAMPLE_FRAMEWORK)
        # Create legacy cycle dirs
        (rd / "cycles").mkdir(exist_ok=True)
        for claim_id in ["enrichment-bound", "bottleneck-ratio"]:
            cycle_dir = rd / "cycles" / f"cycle-1-{claim_id}"
            unit_dir = cycle_dir / "unit-1-investigation"
            sub_dir = unit_dir / "sub-1a-primary"
            for role in ("thinker", "refutor", "coder", "judge", "researcher"):
                (sub_dir / role).mkdir(parents=True, exist_ok=True)
            (cycle_dir / "frontier.md").write_text(
                f"---\nid: c1-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# {claim_id}\n"
            )
            (unit_dir / "frontier.md").write_text(
                "---\nid: u1-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Investigation\n"
            )
            (sub_dir / "frontier.md").write_text(
                "---\nid: s1a-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Primary\n"
            )
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "test_claim"
        assert "sub_unit" in state

    def test_legacy_cycle_done_returns_record_verdict(self, tmp_path):
        """Backward compat: legacy cycles/ with completed cycle returns record_verdict."""
        rd = _make_investigation_dir(tmp_path)
        (rd / ".north-star.md").write_text("# NS\n")
        (rd / ".context.md").write_text("# C\n")
        (rd / "context" / "survey-topic.md").write_text("# Survey\n")
        (rd / "framework.md").write_text("""\
# Framework

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
        (rd / "cycles").mkdir(exist_ok=True)
        cycle_dir = rd / "cycles" / "cycle-1-test-claim"
        unit_dir = cycle_dir / "unit-1-investigation"
        sub_dir = unit_dir / "sub-1a-primary"
        for role in ("thinker", "refutor", "coder", "judge", "researcher"):
            (sub_dir / role).mkdir(parents=True, exist_ok=True)
        for p in [cycle_dir / "frontier.md", unit_dir / "frontier.md", sub_dir / "frontier.md"]:
            p.write_text("---\nid: test\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test\n")
        t_dir = sub_dir / "thinker" / "round-1"
        t_dir.mkdir(parents=True, exist_ok=True)
        (t_dir / "result.md").write_text("---\nid: t\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# T\n")
        r_dir = sub_dir / "refutor" / "round-1"
        r_dir.mkdir(parents=True, exist_ok=True)
        (r_dir / "result.md").write_text(
            "---\nid: r\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# R\n\n**Severity**: minor\n"
        )
        (sub_dir / "coder" / "results").mkdir(parents=True, exist_ok=True)
        (sub_dir / "coder" / "results" / "output.md").write_text(
            "---\nid: c\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n# Coder\n"
        )
        (sub_dir / "judge" / "results").mkdir(parents=True, exist_ok=True)
        (sub_dir / "judge" / "results" / "verdict.md").write_text(
            "---\nid: v\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n# Verdict\n\n**Verdict**: SETTLED\n"
        )
        state = detect_investigation_state(rd, DEFAULT_CONFIG)
        assert state["action"] == "record_verdict"


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
    """Walk the complete state machine: thinker → refutor → coder → judge → post_verdict → complete."""

    def test_full_cycle_minor_severity(self, research_dir):
        """A simple 1-round debate with Minor severity goes straight to coder."""
        sub = make_sub_unit(research_dir)

        # Step 1: Empty sub-unit → dispatch_architect
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 1

        # Step 2: Thinker done → dispatch_adversary
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_adversary"
        assert state["round"] == 1

        # Step 3: Refutor (Minor) → dispatch_experimenter (exits debate)
        write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Minor")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_experimenter"

        # Step 4: Coder done → dispatch_arbiter
        write_result(research_dir, f"{sub}/coder/results/output.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_arbiter"

        # Step 5: Judge verdict → post_verdict
        write_result(research_dir, f"{sub}/judge/results/verdict.md", verdict="SETTLED")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "post_verdict"
        assert state["phase"] == "recording"

        # Step 6: Reviewer done (frontier mtime > verdict mtime) → complete
        import time
        time.sleep(0.1)
        frontier = research_dir / sub / "frontier.md"
        frontier.write_text(
            "---\nid: done\ntype: claim\nstatus: settled\ndate: 2026-01-01\n---\n\n# Done\n"
        )
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "complete_proven"
        assert state["phase"] == "complete"

    def test_full_cycle_fatal_continues_debate(self, research_dir):
        """Fatal severity triggers round 2 before coder."""
        sub = make_sub_unit(research_dir)

        # Thinker round 1
        write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        # Refutor round 1 (Fatal)
        write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Fatal")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 2

        # Thinker round 2
        write_result(research_dir, f"{sub}/thinker/round-2/result.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_adversary"
        assert state["round"] == 2

        # Refutor round 2 (Minor) → exits to coder
        write_result(research_dir, f"{sub}/refutor/round-2/result.md", severity="Minor")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_experimenter"


# ---------------------------------------------------------------------------
# New Role Name Tests (architect/adversary/experimenter/arbiter)
# ---------------------------------------------------------------------------


def make_new_sub_unit(research_dir, sub_rel="cycles/cycle-1/unit-1-test/sub-1a-direct"):
    """Create a sub-unit using NEW role names."""
    sub = research_dir / sub_rel
    for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
        (sub / role).mkdir(parents=True, exist_ok=True)
    for frontier_path in [sub.parent / "frontier.md", sub / "frontier.md"]:
        if not frontier_path.exists():
            frontier_path.parent.mkdir(parents=True, exist_ok=True)
            frontier_path.write_text(
                "---\nid: test-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test\n"
            )
    return sub_rel


class TestNewRoleNameStateMachine:
    """Verify the state machine works with architect/adversary/experimenter/arbiter dirs."""

    def test_empty_dispatches_architect(self, research_dir):
        sub = make_new_sub_unit(research_dir)
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"

    def test_architect_done_dispatches_adversary(self, research_dir):
        sub = make_new_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_adversary"

    def test_adversary_fatal_continues_debate(self, research_dir):
        sub = make_new_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Fatal (blocks the approach)")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_architect"
        assert state["round"] == 2

    def test_adversary_minor_exits_to_experimenter(self, research_dir):
        sub = make_new_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Minor (worth noting)")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_experimenter"

    def test_experimenter_done_dispatches_arbiter(self, research_dir):
        sub = make_new_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        write_result(research_dir, f"{sub}/adversary/round-1/result.md", severity="Minor")
        write_result(research_dir, f"{sub}/experimenter/results/output.md")
        state = detect_state(research_dir, sub, DEFAULT_CONFIG)
        assert state["action"] == "dispatch_arbiter"

    def test_context_files_include_new_names(self, research_dir):
        sub = make_new_sub_unit(research_dir)
        write_result(research_dir, f"{sub}/architect/round-1/result.md")
        files = list_context_files(research_dir, sub, "dispatch_adversary", round_num=1)
        assert any("architect" in f for f in files)
