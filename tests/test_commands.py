"""Tests for CLI commands (Tier 3) — require filesystem and database."""

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)


def run_manage(research_dir, *args):
    """Run manage.py as subprocess and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "scripts/manage.py", "--root", str(research_dir), *list(args)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_PROJECT_ROOT)
    return result.returncode, result.stdout, result.stderr


class TestCmdNew:
    def test_creates_file(self, research_dir):
        rc, out, _ = run_manage(research_dir, "new", "claims/claim-1-test/architect/round-1/result.md")
        assert rc == 0
        assert "Created" in out
        f = research_dir / "claims" / "claim-1-test" / "architect" / "round-1" / "result.md"
        assert f.exists()
        content = f.read_text()
        assert "id: h1-architect-r1-result" in content
        assert "type: claim" in content
        assert "status: pending" in content

    def test_rejects_absolute_path(self, research_dir):
        rc, out, _ = run_manage(research_dir, "new", "/etc/passwd")
        assert rc != 0
        assert "ERROR" in out

    def test_rejects_existing_file(self, research_dir):
        run_manage(research_dir, "new", "cycles/cycle-1/unit-1-test/thinker/round-1/result.md")
        rc, out, _ = run_manage(research_dir, "new", "cycles/cycle-1/unit-1-test/thinker/round-1/result.md")
        assert rc != 0
        assert "already exists" in out

    def test_appends_md(self, research_dir):
        rc, out, _ = run_manage(research_dir, "new", "cycles/cycle-1/unit-1-test/thinker/round-1/result")
        assert rc == 0
        assert ".md" in out


class TestCmdValidate:
    def test_clean(self, populated_research):
        rc, out, _ = run_manage(populated_research, "validate")
        assert rc == 0
        assert "passed" in out.lower()

    def test_invalid_status(self, research_dir):
        from frontmatter import serialise_frontmatter

        path = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        path.mkdir(parents=True)
        (path / "result.md").write_text(
            serialise_frontmatter(
                {
                    "id": "h1-architect-r1-result",
                    "type": "claim",
                    "status": "INVALID",
                    "date": "2026-01-01",
                    "depends_on": [],
                    "assumes": [],
                }
            )
            + "\n"
        )
        rc, out, _ = run_manage(research_dir, "validate")
        assert rc != 0
        assert "INVALID" in out


class TestCmdFalsify:
    def test_cascades(self, populated_research):
        rc, out, _ = run_manage(populated_research, "falsify", "assumption-a1")
        assert rc == 0
        assert "Disproven: assumption-a1" in out
        # The dependent claim should be weakened
        assert "weakened" in out.lower()

    def test_records_ledger(self, populated_research):
        run_manage(populated_research, "falsify", "assumption-a1")
        rc, out, _ = run_manage(populated_research, "query", "SELECT * FROM ledger WHERE event='disproven'")
        assert rc == 0
        assert "assumption-a1" in out

    def test_skips_already_disproven(self, populated_research):
        run_manage(populated_research, "falsify", "assumption-a1")
        _rc, out, _ = run_manage(populated_research, "falsify", "assumption-a1")
        assert "already disproven" in out.lower()

    def test_multi_level_cascade(self, research_dir):
        """A → B → C: falsify A, both B and C should be undermined."""
        from frontmatter import serialise_frontmatter

        assume_dir = research_dir / "context" / "assumptions"
        assume_dir.mkdir(parents=True, exist_ok=True)
        (assume_dir / "a.md").write_text(
            serialise_frontmatter(
                {
                    "id": "a",
                    "type": "assumption",
                    "status": "active",
                    "date": "2026-01-01",
                    "depends_on": [],
                    "assumes": [],
                }
            )
            + "\n# A\n"
        )
        architect_dir = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        architect_dir.mkdir(parents=True)
        (architect_dir / "result.md").write_text(
            serialise_frontmatter(
                {
                    "id": "b",
                    "type": "claim",
                    "status": "active",
                    "date": "2026-01-01",
                    "depends_on": [],
                    "assumes": ["a"],
                }
            )
            + "\n# B\n"
        )
        experimenter_dir = research_dir / "claims" / "claim-1-test" / "experimenter" / "results"
        experimenter_dir.mkdir(parents=True)
        (experimenter_dir / "output.md").write_text(
            serialise_frontmatter(
                {
                    "id": "c",
                    "type": "evidence",
                    "status": "active",
                    "date": "2026-01-01",
                    "depends_on": ["b"],
                    "assumes": [],
                }
            )
            + "\n# C\n"
        )
        rc, out, _ = run_manage(research_dir, "falsify", "a")
        assert rc == 0
        assert "weakened" in out
        # Verify both b and c are weakened via DB query
        _rc2, out2, _ = run_manage(research_dir, "query", "SELECT id, status FROM nodes WHERE status='weakened'")
        assert "b" in out2
        assert "c" in out2

    def test_cascade_attenuates_confidence(self, research_dir):
        """Cascade should downgrade confidence on undermined nodes."""
        from frontmatter import serialise_frontmatter

        assume_dir = research_dir / "context" / "assumptions"
        assume_dir.mkdir(parents=True, exist_ok=True)
        (assume_dir / "base.md").write_text(
            serialise_frontmatter(
                {
                    "id": "base",
                    "type": "assumption",
                    "status": "active",
                    "date": "2026-01-01",
                    "depends_on": [],
                    "assumes": [],
                }
            )
            + "\n# Base\n"
        )
        architect_dir = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        architect_dir.mkdir(parents=True)
        (architect_dir / "result.md").write_text(
            serialise_frontmatter(
                {
                    "id": "dep",
                    "type": "claim",
                    "status": "active",
                    "date": "2026-01-01",
                    "depends_on": [],
                    "assumes": ["base"],
                    "confidence": "high",
                }
            )
            + "\n# Dep\n"
        )
        rc, _out, _ = run_manage(research_dir, "falsify", "base")
        assert rc == 0
        # Check that confidence was attenuated: high → moderate
        _rc2, out2, _ = run_manage(research_dir, "query", "SELECT id, confidence FROM nodes WHERE id='dep'")
        assert "moderate" in out2

    def test_dry_run_no_changes(self, populated_research):
        """--dry-run should preview cascade without modifying files."""
        rc, out, _ = run_manage(populated_research, "falsify", "assumption-a1", "--dry-run")
        assert rc == 0
        assert "Dry-run" in out
        # Verify the node was NOT actually falsified
        _rc2, out2, _ = run_manage(populated_research, "query", "SELECT status FROM nodes WHERE id='assumption-a1'")
        assert "falsified" not in out2

    def test_dry_run_shows_cascade(self, populated_research):
        """--dry-run should list affected dependents."""
        rc, out, _ = run_manage(populated_research, "falsify", "assumption-a1", "--dry-run")
        assert rc == 0
        assert "weaken" in out.lower()

    def test_force_skips_prompt(self, populated_research):
        """--force should execute without confirmation even with cascade targets."""
        rc, out, _ = run_manage(populated_research, "falsify", "assumption-a1", "--force")
        assert rc == 0
        assert "Disproven: assumption-a1" in out


class TestCmdSettle:
    def test_marks_settled(self, sample_node):
        rc, out, _ = run_manage(sample_node, "settle", "h1-architect-r1-result")
        assert rc == 0
        assert "Settled" in out

    def test_rejects_disproven(self, populated_research):
        run_manage(populated_research, "falsify", "assumption-a1")
        rc, out, _ = run_manage(populated_research, "settle", "assumption-a1")
        assert rc != 0
        assert "disproven" in out.lower()


class TestCmdStatus:
    def test_generates_frontier(self, populated_research):
        rc, out, _ = run_manage(populated_research, "status")
        assert rc == 0
        assert "Generated" in out
        frontier = populated_research / "PROGRESS.md"
        assert frontier.exists()
        content = frontier.read_text()
        assert "Design Progress" in content


class TestCmdAssumptions:
    def test_generates_file(self, populated_research):
        rc, _out, _ = run_manage(populated_research, "assumptions")
        assert rc == 0
        assumptions = populated_research / "FOUNDATIONS.md"
        assert assumptions.exists()
        content = assumptions.read_text()
        assert "assumption-a1" in content


class TestCmdCascade:
    def test_dry_run(self, populated_research):
        rc, out, _ = run_manage(populated_research, "cascade", "assumption-a1")
        assert rc == 0
        assert "Cascade analysis" in out
        # Should show the architect claim as affected
        assert "h1-architect-r1-result" in out


class TestCmdLogDispatch:
    def test_logs_dispatch(self, research_dir):
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(
            research_dir,
            "log-dispatch",
            "--cycle",
            "cycle-1-test",
            "--agent",
            "thinker",
            "--action",
            "dispatch",
            "--round",
            "1",
        )
        assert rc == 0
        assert "Logged" in out

    def test_logs_side_dispatch(self, research_dir):
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(
            research_dir,
            "log-dispatch",
            "--cycle",
            "cycle-1-test",
            "--agent",
            "coder",
            "--action",
            "side_dispatch",
            "--details",
            "checking empirical claim",
        )
        assert rc == 0
        assert "Logged" in out


class TestCmdDispatchLog:
    def test_empty_log(self, research_dir):
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(research_dir, "dispatch-log")
        assert rc == 0
        assert "No dispatches" in out

    def test_shows_logged_dispatches(self, research_dir):
        run_manage(research_dir, "build")
        run_manage(
            research_dir,
            "log-dispatch",
            "--cycle",
            "cycle-1",
            "--agent",
            "thinker",
            "--action",
            "dispatch",
            "--round",
            "1",
        )
        rc, out, _ = run_manage(research_dir, "dispatch-log")
        assert rc == 0
        assert "thinker" in out
        assert "dispatch" in out

    def test_json_output(self, research_dir):
        import json

        run_manage(research_dir, "build")
        run_manage(
            research_dir,
            "log-dispatch",
            "--cycle",
            "cycle-1",
            "--agent",
            "refutor",
            "--action",
            "dispatch",
            "--round",
            "1",
        )
        rc, out, _ = run_manage(research_dir, "dispatch-log", "--json")
        assert rc == 0
        data = json.loads(out)
        assert len(data) == 1
        assert data[0]["agent"] == "refutor"

    def test_filter_by_cycle(self, research_dir):
        run_manage(research_dir, "build")
        run_manage(
            research_dir,
            "log-dispatch",
            "--cycle",
            "cycle-1",
            "--agent",
            "thinker",
            "--action",
            "dispatch",
        )
        run_manage(
            research_dir,
            "log-dispatch",
            "--cycle",
            "cycle-2",
            "--agent",
            "refutor",
            "--action",
            "dispatch",
        )
        rc, out, _ = run_manage(research_dir, "dispatch-log", "--cycle", "cycle-1")
        assert rc == 0
        assert "thinker" in out
        assert "refutor" not in out


class TestCmdWavesJson:
    def test_json_flag_empty(self, research_dir):
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(research_dir, "waves", "--json")
        assert rc == 0
        assert out.strip() == "[]"

    def test_json_flag_with_data(self, populated_research):
        rc, out, _ = run_manage(populated_research, "waves", "--json")
        assert rc == 0
        import json

        data = json.loads(out)
        assert isinstance(data, list)


class TestCmdInvestigateNext:
    def test_empty_research_returns_understand(self, research_dir):
        rc, out, _ = run_manage(research_dir, "investigate-next")
        assert rc == 0
        import json

        state = json.loads(out)
        assert state["action"] == "understand"


class TestCmdParseFramework:
    def test_no_framework_exits_with_error(self, research_dir):
        rc, _out, _ = run_manage(research_dir, "parse-framework")
        assert rc != 0

    def test_with_valid_framework(self, research_dir):
        (research_dir / "blueprint.md").write_text("""\
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
        rc, out, _ = run_manage(research_dir, "parse-framework")
        assert rc == 0
        import json

        claims = json.loads(out)
        assert len(claims) == 1
        assert claims[0]["id"] == "test-claim"


class TestCmdRegister:
    def test_registers_artifact(self, research_dir):
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(
            research_dir,
            "register",
            "--id",
            "ring-gen",
            "--name",
            "Ring Generator",
            "--type",
            "function",
            "--path",
            "code/ring.py",
            "--description",
            "Generates test rings",
            "--cycle",
            "cycle-1",
        )
        assert rc == 0
        assert "Registered" in out
        assert "ring-gen" in out

    def test_register_overwrites(self, research_dir):
        run_manage(research_dir, "build")
        run_manage(
            research_dir,
            "register",
            "--id",
            "dup",
            "--name",
            "V1",
            "--type",
            "function",
            "--path",
            "v1.py",
        )
        rc, out, _ = run_manage(
            research_dir,
            "register",
            "--id",
            "dup",
            "--name",
            "V2",
            "--type",
            "script",
            "--path",
            "v2.py",
        )
        assert rc == 0
        assert "Registered" in out


class TestCmdArtifacts:
    def test_empty_list(self, research_dir):
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(research_dir, "artifacts")
        assert rc == 0
        assert "No experiment artifacts" in out

    def test_lists_registered(self, research_dir):
        run_manage(research_dir, "build")
        run_manage(
            research_dir,
            "register",
            "--id",
            "bench-1",
            "--name",
            "Benchmark",
            "--type",
            "script",
            "--path",
            "bench.py",
        )
        rc, out, _ = run_manage(research_dir, "artifacts")
        assert rc == 0
        assert "bench-1" in out
        assert "Benchmark" in out


class TestCmdCodebook:
    def test_generates_codebook_empty(self, research_dir):
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(research_dir, "codebook")
        assert rc == 0
        assert "Generated" in out
        codebook = research_dir / "TOOLKIT.md"
        assert codebook.exists()
        assert "No artifacts" in codebook.read_text()

    def test_generates_codebook_with_artifacts(self, research_dir):
        run_manage(research_dir, "build")
        run_manage(
            research_dir,
            "register",
            "--id",
            "gen-1",
            "--name",
            "Generator",
            "--type",
            "function",
            "--path",
            "gen.py",
            "--description",
            "Generates data",
        )
        rc, _out, _ = run_manage(research_dir, "codebook")
        assert rc == 0
        codebook = research_dir / "TOOLKIT.md"
        content = codebook.read_text()
        assert "gen-1" in content
        assert "Generator" in content
        assert "Generates data" in content


class TestCmdList:
    def test_list_all(self, sample_node):
        rc, out, _ = run_manage(sample_node, "list")
        assert rc == 0
        assert "h1-architect-r1-result" in out

    def test_list_filter_type(self, populated_research):
        rc, out, _ = run_manage(populated_research, "list", "--type", "assumption")
        assert rc == 0
        assert "assumption" in out

    def test_list_filter_status(self, populated_research):
        rc, _out, _ = run_manage(populated_research, "list", "--status", "active")
        assert rc == 0

    def test_list_json(self, sample_node):
        import json

        rc, out, _ = run_manage(sample_node, "list", "--json")
        assert rc == 0
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "id" in data[0]


class TestScaffoldClaim:
    """Tests for the flat claim scaffold level."""

    def test_scaffold_claim_creates_directory(self, research_dir):
        rc, _out, _ = run_manage(research_dir, "scaffold", "claim", "enrichment")
        assert rc == 0
        claim_dir = research_dir / "claims" / "claim-1-enrichment"
        assert claim_dir.exists()
        assert (claim_dir / "claim.md").exists()

    def test_scaffold_claim_creates_role_dirs(self, research_dir):
        run_manage(research_dir, "scaffold", "claim", "topology")
        claim_dir = research_dir / "claims" / "claim-1-topology"
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            assert (claim_dir / role).is_dir(), f"Missing role dir: {role}"

    def test_scaffold_claim_auto_numbers(self, research_dir):
        run_manage(research_dir, "scaffold", "claim", "first")
        run_manage(research_dir, "scaffold", "claim", "second")
        assert (research_dir / "claims" / "claim-1-first").exists()
        assert (research_dir / "claims" / "claim-2-second").exists()

    def test_scaffold_claim_id_derivation(self, research_dir):
        run_manage(research_dir, "scaffold", "claim", "enrichment")
        claim_md = research_dir / "claims" / "claim-1-enrichment" / "claim.md"
        from frontmatter import parse_frontmatter

        meta = parse_frontmatter(claim_md.read_text())
        # claim-1-enrichment/claim -> h1-claim
        assert meta["id"] == "h1-claim"


class TestCmdResults:
    """Tests for the results command."""

    def test_results_generates_file(self, populated_research):
        rc, _out, _ = run_manage(populated_research, "results")
        assert rc == 0
        results = populated_research / "RESULTS.md"
        assert results.exists()
        content = results.read_text()
        assert "Design Results" in content

    def test_results_includes_limitations(self, populated_research):
        run_manage(populated_research, "results")
        content = (populated_research / "RESULTS.md").read_text()
        assert "Limitations" in content

    def test_results_includes_synthesis(self, research_dir):
        # Create a synthesis file
        (research_dir / "synthesis.md").write_text("---\nid: synthesis\n---\n\nAll claims converge.")
        rc, _, _ = run_manage(research_dir, "results")
        assert rc == 0
        content = (research_dir / "RESULTS.md").read_text()
        assert "Synthesis" in content
        assert "All claims converge" in content

    def test_list_empty(self, research_dir):
        rc, out, _ = run_manage(research_dir, "list")
        assert rc == 0
        assert "No nodes" in out


class TestCmdQueryJson:
    def test_query_json(self, sample_node):
        import json

        rc, out, _ = run_manage(sample_node, "query", "--json", "SELECT id, type FROM nodes")
        assert rc == 0
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_query_json_empty(self, research_dir):
        rc, out, _ = run_manage(research_dir, "query", "--json", "SELECT * FROM nodes")
        assert rc == 0
        assert out.strip() == "[]"


class TestCmdValidateJson:
    def test_validate_json_pass(self, sample_node):
        import json

        rc, out, _ = run_manage(sample_node, "validate", "--json")
        assert rc == 0
        data = json.loads(out)
        assert data["valid"] is True
        assert data["error_count"] == 0


class TestCmdNext:
    def _make_sub_unit(self, research_dir):
        """Create a sub-unit with architect dir for testing."""
        sub = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        sub.mkdir(parents=True)
        (sub / "frontier.md").write_text(
            "---\nid: s1a-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Probe\n"
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (sub / role).mkdir()
        return "cycles/cycle-1/unit-1-test/sub-1a-probe"

    def test_empty_sub_unit_dispatches_architect(self, research_dir):
        import json

        sub_path = self._make_sub_unit(research_dir)
        rc, out, _ = run_manage(research_dir, "next", sub_path)
        assert rc == 0
        state = json.loads(out)
        assert state["action"] == "dispatch_architect"

    def test_with_architect_dispatches_adversary(self, research_dir):
        import json

        sub_path = self._make_sub_unit(research_dir)
        sub = research_dir / sub_path
        r1 = sub / "architect" / "round-1"
        r1.mkdir(parents=True)
        (r1 / "result.md").write_text(
            "---\nid: arch-r1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Proposal\n"
        )
        rc, out, _ = run_manage(research_dir, "next", sub_path)
        assert rc == 0
        state = json.loads(out)
        assert state["action"] == "dispatch_adversary"

    def test_includes_context_files(self, research_dir):
        import json

        sub_path = self._make_sub_unit(research_dir)
        rc, out, _ = run_manage(research_dir, "next", sub_path)
        assert rc == 0
        state = json.loads(out)
        assert "context_files" in state
        assert isinstance(state["context_files"], list)

    def test_auto_no_claims(self, research_dir):
        rc, out, _ = run_manage(research_dir, "next", "auto")
        assert rc == 0
        assert "No active claims" in out


class TestCmdContext:
    def test_assembles_context(self, research_dir):
        # Create a claim with claim.md
        claim = research_dir / "claims" / "claim-1-probe"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test Question\n"
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (claim / role).mkdir()
        claim_path = "claims/claim-1-probe"

        rc, out, _ = run_manage(research_dir, "context", claim_path)
        assert rc == 0
        assert "Test Question" in out


class TestCmdPrompt:
    def test_generates_prompt_file(self, research_dir):
        sub = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        sub.mkdir(parents=True)
        (sub / "frontier.md").write_text(
            "---\nid: s1a-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Probe\n"
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (sub / role).mkdir()
        sub_path = "cycles/cycle-1/unit-1-test/sub-1a-probe"

        rc, out, _ = run_manage(research_dir, "prompt", sub_path)
        assert rc == 0
        assert "Written:" in out
        # The prompt file should exist
        prompt_file = sub / "architect" / "round-1" / "prompt.md"
        assert prompt_file.exists()


class TestCmdPostVerdict:
    def _make_verdicted_sub_unit(self, research_dir, verdict="PROVEN", confidence="high"):
        """Create a claim with architect, adversary, experimenter, and arbiter results."""
        claim = research_dir / "claims" / "claim-1-probe"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n# Probe\n"
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (claim / role).mkdir()

        # Architect round 1
        r1 = claim / "architect" / "round-1"
        r1.mkdir()
        (r1 / "result.md").write_text(
            "---\nid: arch-r1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Proposal\n"
        )
        # Adversary round 1
        a1 = claim / "adversary" / "round-1"
        a1.mkdir()
        (a1 / "result.md").write_text(
            "---\nid: adv-r1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Attack\n\n**Severity**: Minor\n"
        )
        # Experimenter
        exp = claim / "experimenter" / "results"
        exp.mkdir()
        (exp / "output.md").write_text(
            "---\nid: exp-out\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n# Results\nAUROC: 0.92\n"
        )
        # Verdict
        arb = claim / "arbiter" / "results"
        arb.mkdir()
        (arb / "verdict.md").write_text(
            f"---\nid: verdict\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            f"# Verdict\n\n**Verdict**: {verdict}\n**Confidence**: {confidence}\n"
        )
        return "claims/claim-1-probe"

    def test_proven_updates_frontier(self, research_dir):
        import json

        sub_path = self._make_verdicted_sub_unit(research_dir, verdict="PROVEN")
        # Build DB first
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(research_dir, "post-verdict", sub_path)
        assert rc == 0
        result = json.loads(out)
        assert result["verdict"] == "PROVEN"
        # Claim status should be updated
        from frontmatter import parse_frontmatter

        from config import init_paths

        init_paths(research_dir)
        claim_file = research_dir / sub_path / "claim.md"
        meta = parse_frontmatter(claim_file.read_text())
        assert meta["status"] == "proven"

    def test_writes_marker_file(self, research_dir):
        sub_path = self._make_verdicted_sub_unit(research_dir, verdict="PROVEN")
        run_manage(research_dir, "build")
        rc, _, _ = run_manage(research_dir, "post-verdict", sub_path)
        assert rc == 0
        marker = research_dir / sub_path / ".post_verdict_done"
        assert marker.exists()

    def test_disproven_cascades(self, research_dir):
        import json

        sub_path = self._make_verdicted_sub_unit(research_dir, verdict="DISPROVEN")
        # Add a dependent node
        dep_dir = research_dir / "context"
        (dep_dir / "dependent.md").write_text(
            "---\nid: dependent\ntype: claim\nstatus: active\ndate: 2026-01-01\n"
            "depends_on: [h1-claim]\n---\n\n# Dependent\n"
        )
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(research_dir, "post-verdict", sub_path)
        assert rc == 0
        result = json.loads(out)
        assert result["verdict"] == "DISPROVEN"
        assert any("Weakened" in c for c in result["changes"])

    def test_partial_sets_status(self, research_dir):
        import json

        sub_path = self._make_verdicted_sub_unit(research_dir, verdict="PARTIAL")
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(research_dir, "post-verdict", sub_path)
        assert rc == 0
        result = json.loads(out)
        assert result["verdict"] == "PARTIAL"

    def test_no_verdict_file_errors(self, research_dir):
        sub = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        sub.mkdir(parents=True)
        (sub / "frontier.md").write_text("---\nid: test\n---\n")
        rc, _, _ = run_manage(research_dir, "post-verdict", "cycles/cycle-1/unit-1-test/sub-1a-probe")
        assert rc != 0


class TestBreadcrumb:
    def test_understand_breadcrumb(self, research_dir):
        """investigate-next includes breadcrumb for understand phase."""
        import json

        rc, out, _ = run_manage(research_dir, "investigate-next")
        assert rc == 0
        state = json.loads(out)
        assert "breadcrumb" in state
        assert "[Understand" in state["breadcrumb"]

    def test_divide_breadcrumb(self, research_dir):
        """investigate-next includes breadcrumb for divide phase."""
        import json

        (research_dir / ".north-star.md").write_text("# Test principle\n")
        (research_dir / ".context.md").write_text("# Context\n")
        (research_dir / "context" / "survey-test.md").write_text("# Survey\n")
        rc, out, _ = run_manage(research_dir, "investigate-next")
        assert rc == 0
        state = json.loads(out)
        assert "[Divide]" in state["breadcrumb"]

    def test_breadcrumb_includes_north_star(self, research_dir):
        """Breadcrumb includes north star title when .north-star.md exists."""
        import json

        (research_dir / ".north-star.md").write_text("# Topology-preserving clustering\n\nDetails.\n")
        rc, out, _ = run_manage(research_dir, "investigate-next")
        assert rc == 0
        state = json.loads(out)
        assert "Topology-preserving" in state["breadcrumb"]


class TestValidatePaste:
    def test_valid_adversary_paste(self, research_dir, tmp_path):
        paste_file = tmp_path / "paste.md"
        paste_file.write_text("# Attack\n\nThe proposal has a flaw.\n\n**Severity**: Serious\n\nDetails here.")
        rc, out, _ = run_manage(research_dir, "validate-paste", "--agent", "adversary", "--file", str(paste_file))
        assert rc == 0
        assert "valid" in out.lower() or "ok" in out.lower()

    def test_invalid_adversary_missing_severity(self, research_dir, tmp_path):
        paste_file = tmp_path / "paste.md"
        paste_file.write_text(
            "# Attack\n\nSome text without the required rating field that is long enough to pass length check."
        )
        rc, out, _ = run_manage(research_dir, "validate-paste", "--agent", "adversary", "--file", str(paste_file))
        assert rc != 0
        assert "severity" in out.lower()

    def test_empty_paste_rejected(self, research_dir, tmp_path):
        paste_file = tmp_path / "paste.md"
        paste_file.write_text("")
        rc, out, _ = run_manage(research_dir, "validate-paste", "--agent", "architect", "--file", str(paste_file))
        assert rc != 0
        assert "empty" in out.lower() or "truncated" in out.lower()

    def test_valid_scout_paste(self, research_dir, tmp_path):
        paste_file = tmp_path / "paste.md"
        paste_file.write_text("# Survey\n\n## Key Findings\n\n- Finding 1\n\n## Sources\n\n- Paper A (2024)\n")
        rc, _out, _ = run_manage(research_dir, "validate-paste", "--agent", "scout", "--file", str(paste_file))
        assert rc == 0

    def test_valid_arbiter_paste(self, research_dir, tmp_path):
        paste_file = tmp_path / "paste.md"
        paste_file.write_text(
            "# Verdict Assessment\n\n**Verdict**: PROVEN\n"
            "**Confidence**: high\n\n## Reasoning\nDetails here with enough text.\n"
        )
        rc, _out, _ = run_manage(research_dir, "validate-paste", "--agent", "arbiter", "--file", str(paste_file))
        assert rc == 0

    def test_invalid_verdict_value(self, research_dir, tmp_path):
        paste_file = tmp_path / "paste.md"
        paste_file.write_text(
            "# Verdict\n\n**Verdict**: MAYBE\n**Confidence**: high\n\nEnough content to pass length.\n"
        )
        rc, out, _ = run_manage(research_dir, "validate-paste", "--agent", "arbiter", "--file", str(paste_file))
        assert rc != 0
        assert "invalid verdict" in out.lower()

    def test_invalid_severity_value(self, research_dir, tmp_path):
        paste_file = tmp_path / "paste.md"
        paste_file.write_text(
            "# Attack\n\n**Severity**: Devastating\n\nThis is a detailed critique with enough text.\n"
        )
        rc, out, _ = run_manage(research_dir, "validate-paste", "--agent", "adversary", "--file", str(paste_file))
        assert rc != 0
        assert "invalid severity" in out.lower()

    def test_experimenter_missing_results_section(self, research_dir, tmp_path):
        paste_file = tmp_path / "paste.md"
        paste_file.write_text("# Experiment\n\nI ran some code and it worked. Here is the long enough output text.\n")
        rc, out, _ = run_manage(research_dir, "validate-paste", "--agent", "experimenter", "--file", str(paste_file))
        assert rc != 0
        assert "results" in out.lower()

    def test_valid_experimenter_paste(self, research_dir, tmp_path):
        paste_file = tmp_path / "paste.md"
        paste_file.write_text("# Experiment\n\n## Results\n\nAUROC = 0.87, p < 0.01. The hypothesis holds.\n")
        rc, _out, _ = run_manage(research_dir, "validate-paste", "--agent", "experimenter", "--file", str(paste_file))
        assert rc == 0


class TestCmdNextArbiterConfidence:
    def test_confidence_from_arbiter_dir(self, research_dir):
        """cmd_next extracts confidence from arbiter/ (not just judge/)."""
        # Create a flat claim with arbiter verdict
        claim_dir = research_dir / "claims" / "claim-1-test"
        for role in ("architect", "adversary", "experimenter", "arbiter"):
            (claim_dir / role).mkdir(parents=True, exist_ok=True)
        (claim_dir / "claim.md").write_text(
            "---\nid: test\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test\n"
        )
        # Complete the debate minimally
        a_dir = claim_dir / "architect" / "round-1"
        a_dir.mkdir(parents=True)
        (a_dir / "result.md").write_text(
            "---\nid: t\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Proposal\n"
        )
        r_dir = claim_dir / "adversary" / "round-1"
        r_dir.mkdir(parents=True)
        (r_dir / "result.md").write_text(
            "---\nid: r\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Attack\n\n**Severity**: minor\n"
        )
        (claim_dir / "experimenter" / "results").mkdir(parents=True)
        (claim_dir / "experimenter" / "results" / "output.md").write_text("# Evidence\n")
        # Write verdict with confidence in ARBITER dir
        (claim_dir / "arbiter" / "results").mkdir(parents=True, exist_ok=True)
        (claim_dir / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: v\ntype: verdict\nstatus: active\ndate: 2026-01-01\n"
            "---\n\n**Verdict**: PROVEN\n**Confidence**: high\n"
        )
        (claim_dir / ".post_verdict_done").write_text("")
        rc, out, _ = run_manage(research_dir, "next", "claims/claim-1-test")
        assert rc == 0
        import json

        state = json.loads(out)
        assert state.get("confidence") == "high", f"Expected 'high' but got {state.get('confidence')}"


class TestScaffoldClaimMetadata:
    def test_scaffold_with_falsification(self, research_dir):
        rc, _out, _ = run_manage(
            research_dir,
            "scaffold",
            "claim",
            "test-claim",
            "--falsification",
            "If AUROC < 0.7 on nested rings",
            "--maturity",
            "conjecture",
            "--confidence",
            "moderate",
            "--statement",
            "Persistent homology preserves topology.",
        )
        assert rc == 0
        claim_md = research_dir / "claims" / "claim-1-test-claim" / "claim.md"
        assert claim_md.exists()
        content = claim_md.read_text()
        assert "falsification: If AUROC < 0.7 on nested rings" in content
        assert "maturity: conjecture" in content
        assert "confidence: moderate" in content
        assert "Persistent homology preserves topology." in content

    def test_scaffold_without_metadata(self, research_dir):
        """Scaffold claim still works without optional flags."""
        rc, _out, _ = run_manage(research_dir, "scaffold", "claim", "basic-claim")
        assert rc == 0
        claim_md = research_dir / "claims" / "claim-1-basic-claim" / "claim.md"
        content = claim_md.read_text()
        assert "falsification" not in content


class TestClaimTypeInference:
    def test_scaffold_claim_type_is_claim(self, research_dir):
        """scaffold claim should create claim.md with type: claim, not verdict."""
        rc, _out, _ = run_manage(research_dir, "scaffold", "claim", "test-type")
        assert rc == 0
        claim_md = research_dir / "claims" / "claim-1-test-type" / "claim.md"
        content = claim_md.read_text()
        assert "type: claim" in content, f"Expected type: claim but got:\n{content}"
        assert "type: verdict" not in content


class TestPostVerdictFlatClaim:
    def test_post_verdict_updates_flat_claim(self, research_dir):
        """post-verdict should update claim.md status for flat claims."""
        # Scaffold a flat claim
        run_manage(research_dir, "scaffold", "claim", "pv-test")
        claim_dir = research_dir / "claims" / "claim-1-pv-test"

        # Create minimal debate + verdict
        a_dir = claim_dir / "architect" / "round-1"
        a_dir.mkdir(parents=True)
        (a_dir / "result.md").write_text(
            "---\nid: a\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Proposal\n"
        )
        r_dir = claim_dir / "adversary" / "round-1"
        r_dir.mkdir(parents=True)
        (r_dir / "result.md").write_text(
            "---\nid: r\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Attack\n\n**Severity**: minor\n"
        )
        (claim_dir / "experimenter" / "results").mkdir(parents=True)
        (claim_dir / "experimenter" / "results" / "output.md").write_text(
            "---\nid: e\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n# Evidence\n"
        )
        (claim_dir / "arbiter" / "results").mkdir(parents=True, exist_ok=True)
        (claim_dir / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: v\ntype: verdict\nstatus: active\n"
            "date: 2026-01-01\n---\n\n**Verdict**: PROVEN\n**Confidence**: high\n"
        )

        # Run build to populate DB
        run_manage(research_dir, "build")

        # Run post-verdict
        rc, out, _ = run_manage(research_dir, "post-verdict", "claims/claim-1-pv-test")
        assert rc == 0, f"post-verdict failed: {out}"

        # Verify claim.md was updated
        content = (claim_dir / "claim.md").read_text()
        assert "status: proven" in content, f"Expected status: proven but got:\n{content}"


class TestAutonomyConfig:
    """Test autonomy-config CLI command."""

    def test_autonomy_config_outputs_json(self, research_dir):
        """autonomy-config outputs valid JSON with mode and checkpoint_at."""
        rc, out, _ = run_manage(research_dir, "autonomy-config")
        assert rc == 0, f"autonomy-config failed: {out}"
        import json

        result = json.loads(out)
        assert result["mode"] == "checkpoints"
        assert "understand" in result["checkpoint_at"]


class TestExtendDebate:
    """Test extend-debate CLI command."""

    def test_extend_debate_writes_override(self, research_dir):
        """extend-debate creates .max_rounds_override in claim directory."""
        claim_dir = research_dir / "claims" / "claim-1-test"
        claim_dir.mkdir(parents=True)
        (claim_dir / "claim.md").write_text("---\nid: h1-test\ntype: claim\nstatus: active\n---\n")

        rc, out, _ = run_manage(research_dir, "extend-debate", "claims/claim-1-test", "--to", "6")
        assert rc == 0, f"extend-debate failed: {out}"
        assert "6 rounds" in out

        override = claim_dir / ".max_rounds_override"
        assert override.exists()
        assert override.read_text().strip() == "6"
