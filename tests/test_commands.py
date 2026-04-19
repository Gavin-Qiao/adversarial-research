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

    def test_detects_duplicate_ids(self, research_dir):
        """Validate must catch duplicate IDs across source files."""
        d1 = research_dir / "claims" / "claim-1-a" / "architect" / "round-1"
        d1.mkdir(parents=True)
        (d1 / "result.md").write_text("---\nid: same-id\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# A\n")
        d2 = research_dir / "claims" / "claim-2-b" / "architect" / "round-1"
        d2.mkdir(parents=True)
        (d2 / "result.md").write_text("---\nid: same-id\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# B\n")
        rc, out, _ = run_manage(research_dir, "validate")
        assert rc != 0
        assert "duplicate" in out.lower()

    def test_reports_invalid_utf8_instead_of_tracing_back(self, research_dir):
        claim = research_dir / "claims" / "claim-1-bad"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_bytes(b"---\nid: bad\ntype: claim\nstatus: pending\n---\n\n# Bad\xff\n")

        rc, out, err = run_manage(research_dir, "validate")
        combined = out + err

        assert rc != 0
        assert "utf-8" in combined.lower()
        assert "traceback" not in combined.lower()

    def test_reports_non_scalar_id_instead_of_tracing_back(self, research_dir):
        claim = research_dir / "claims" / "claim-1-bad-id"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: [oops]\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Bad ID\n"
        )

        rc, out, err = run_manage(research_dir, "validate")
        combined = out + err

        assert rc != 0
        assert "non-scalar" in combined.lower() or "invalid id" in combined.lower()
        assert "traceback" not in combined.lower()

    def test_reports_non_scalar_status_as_validation_error(self, research_dir):
        claim = research_dir / "claims" / "claim-1-bad-status"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: [pending]\ndate: 2026-01-01\n---\n\n# Bad Status\n"
        )

        rc, out, err = run_manage(research_dir, "validate")
        combined = out + err

        assert rc != 0
        assert "non-scalar" in combined.lower()
        assert "status" in combined.lower()
        assert "traceback" not in combined.lower()

    def test_reports_deleted_dependency_target_after_incremental_rebuild(self, research_dir):
        claim_a = research_dir / "claims" / "claim-1-a"
        claim_a.mkdir(parents=True)
        (claim_a / "claim.md").write_text("---\nid: a1\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# A\n")

        claim_b = research_dir / "claims" / "claim-2-b"
        claim_b.mkdir(parents=True)
        (claim_b / "claim.md").write_text(
            "---\nid: b1\ntype: claim\nstatus: pending\ndate: 2026-01-01\ndepends_on: [a1]\n---\n\n# B\n"
        )

        rc, _out, _err = run_manage(research_dir, "build")
        assert rc == 0

        (claim_a / "claim.md").unlink()

        rc, out, err = run_manage(research_dir, "validate")
        combined = out + err

        assert rc != 0
        assert "unknown target 'a1'" in combined.lower()
        assert "validation passed" not in combined.lower()
        assert "traceback" not in combined.lower()


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

    def test_rejects_unknown_evidence_id(self, populated_research):
        """--by must reference an existing node ID."""
        rc, out, _ = run_manage(populated_research, "falsify", "assumption-a1", "--by", "missing-evidence")
        assert rc != 0
        assert "not found" in out

        _rc, query_out, _ = run_manage(populated_research, "query", "SELECT status FROM nodes WHERE id='assumption-a1'")
        assert "pending" in query_out


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

    def test_includes_legacy_cycle_claims(self, research_dir):
        sub = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        sub.mkdir(parents=True)
        (sub / "frontier.md").write_text(
            "---\nid: s1a-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Probe\n"
        )

        rc, _out, _ = run_manage(research_dir, "status")
        assert rc == 0
        content = (research_dir / "PROGRESS.md").read_text()
        assert "s1a-frontier" in content
        assert "cycles/cycle-1/unit-1-test/sub-1a-probe/frontier.md" in content

    def test_excludes_verdict_artifacts_from_blockers_and_claim_log(self, research_dir):
        claim = research_dir / "claims" / "claim-1-test"
        verdict_dir = claim / "arbiter" / "results"
        verdict_dir.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Claim\n"
        )
        (verdict_dir / "verdict.md").write_text(
            "---\nid: h1-arbiter-verdict\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n# Verdict\n"
        )

        rc, _out, _ = run_manage(research_dir, "status")
        assert rc == 0
        content = (research_dir / "PROGRESS.md").read_text()
        assert "h1-claim" in content
        assert "claims/claim-1-test/claim.md" in content
        assert "h1-arbiter-verdict" not in content
        assert "claims/claim-1-test/arbiter/results/verdict.md" not in content

    def test_reports_assumption_blockers(self, research_dir):
        assumptions = research_dir / "context" / "assumptions"
        assumptions.mkdir(parents=True, exist_ok=True)
        (assumptions / "a.md").write_text(
            "---\nid: a1\ntype: assumption\nstatus: active\ndate: 2026-01-01\n---\n\n# A\n"
        )

        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: pending\ndate: 2026-01-01\nassumes: [a1]\n---\n\n# C\n"
        )

        rc, _out, _ = run_manage(research_dir, "status")
        assert rc == 0
        content = (research_dir / "PROGRESS.md").read_text()
        assert "a1" in content
        assert "blocks 1 pending node(s)" in content

    def test_reports_legacy_frontier_blocker_counts(self, research_dir):
        blocker = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        blocker.mkdir(parents=True)
        (blocker / "frontier.md").write_text(
            "---\nid: s1a-frontier\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n# Probe\n"
        )

        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: pending\ndate: 2026-01-01\n"
            "depends_on: [s1a-frontier]\n---\n\n# Claim\n"
        )

        rc, _out, _ = run_manage(research_dir, "status")
        assert rc == 0
        content = (research_dir / "PROGRESS.md").read_text()
        assert "s1a-frontier" in content
        assert "blocks 1 pending node(s)" in content


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

    def test_logs_structured_dispatch_metadata(self, research_dir):
        import json

        run_manage(research_dir, "build")
        rc, out, _ = run_manage(
            research_dir,
            "log-dispatch",
            "--cycle",
            "claim-1-test",
            "--agent",
            "architect",
            "--action",
            "dispatch",
            "--sub-unit",
            "claims/claim-1-test",
            "--dispatch-mode",
            "external",
            "--packet-path",
            "claims/claim-1-test/architect/round-1/packet.md",
            "--prompt-path",
            "claims/claim-1-test/architect/round-1/prompt.md",
            "--result-path",
            "claims/claim-1-test/architect/round-1/result.md",
        )
        assert rc == 0
        assert "Logged" in out

        rc, out, _ = run_manage(research_dir, "dispatch-log", "--json")
        assert rc == 0
        data = json.loads(out)
        assert data[0]["sub_unit"] == "claims/claim-1-test"
        assert data[0]["dispatch_mode"] == "external"
        assert data[0]["packet_path"].endswith("packet.md")

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

    def test_assumption_edges_order_waves(self, research_dir):
        import json

        assumptions = research_dir / "context" / "assumptions"
        assumptions.mkdir(parents=True, exist_ok=True)
        (assumptions / "a.md").write_text(
            "---\nid: a1\ntype: assumption\nstatus: pending\ndate: 2026-01-01\n---\n\n# A\n"
        )

        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: pending\ndate: 2026-01-01\nassumes: [a1]\n---\n\n# C\n"
        )

        run_manage(research_dir, "build")
        rc, out, _ = run_manage(research_dir, "waves", "--json")

        assert rc == 0
        waves = json.loads(out)
        assert [node["id"] for node in waves[0]] == ["a1"]
        assert [node["id"] for node in waves[1]] == ["h1-claim"]


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

    def test_scaffold_claim_stamps_north_star_version(self, research_dir):
        (research_dir / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
        run_manage(research_dir, "scaffold", "claim", "enrichment")
        claim_md = research_dir / "claims" / "claim-1-enrichment" / "claim.md"
        from frontmatter import parse_frontmatter

        meta = parse_frontmatter(claim_md.read_text())
        assert meta["north_star_version"]


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

    def test_results_shows_actual_verdict_not_frontmatter_status(self, research_dir):
        """Regression: RESULTS.md must show PROVEN/DISPROVEN, not frontmatter status like 'active'."""
        from config import init_paths

        init_paths(research_dir)
        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text("---\nid: h1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Test\n")
        arb = claim / "arbiter" / "results"
        arb.mkdir(parents=True)
        (arb / "verdict.md").write_text(
            "---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: PROVEN\n**Confidence**: high\n"
        )
        run_manage(research_dir, "results")
        content = (research_dir / "RESULTS.md").read_text()
        assert "PROVEN" in content, "RESULTS.md should show PROVEN, not 'ACTIVE'"
        assert "high" in content, "RESULTS.md should show confidence 'high'"
        assert "ACTIVE" not in content, "RESULTS.md should not show frontmatter status 'ACTIVE'"

    def test_results_includes_legacy_cycle_verdicts(self, research_dir):
        """Legacy cycles/ verdicts should still appear in RESULTS.md."""
        sub = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (sub / role).mkdir(parents=True, exist_ok=True)
        (sub / "frontier.md").write_text(
            "---\nid: s1a-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Probe\n"
        )
        (sub / "arbiter" / "results").mkdir(parents=True, exist_ok=True)
        (sub / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: PROVEN\n**Confidence**: high\n"
        )

        rc, _out, _ = run_manage(research_dir, "results")
        assert rc == 0
        content = (research_dir / "RESULTS.md").read_text()
        assert "sub-1a-probe" in content
        assert "PROVEN" in content

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

    def test_includes_packet_path_and_north_star_status(self, research_dir):
        import json

        (research_dir / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
        sub_path = self._make_sub_unit(research_dir)
        rc, out, _ = run_manage(research_dir, "next", sub_path)
        assert rc == 0
        state = json.loads(out)
        assert state["packet_path"].endswith("architect/round-1/packet.md")
        assert state["north_star"]["status"] in {"missing_version", "stale", "current"}

    def test_syncs_received_events_for_completed_results(self, research_dir):
        import json

        sub_path = self._make_sub_unit(research_dir)
        result_file = research_dir / sub_path / "architect" / "round-1" / "result.md"
        result_file.parent.mkdir(parents=True, exist_ok=True)
        result_file.write_text("---\nid: arch-r1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Proposal\n")

        rc, _out, _ = run_manage(research_dir, "next", sub_path)
        assert rc == 0

        rc, out, _ = run_manage(research_dir, "dispatch-log", "--json")
        assert rc == 0
        data = json.loads(out)
        received = next(
            row for row in data if row["action"] == "received" and row["agent"] == "architect" and row["round"] == 1
        )
        assert received["sub_unit"] == sub_path
        assert received["result_path"].endswith("architect/round-1/result.md")

    def test_auto_no_claims(self, research_dir):
        import json

        rc, out, _ = run_manage(research_dir, "next", "auto")
        assert rc == 0
        result = json.loads(out)
        assert result["status"] == "no_active_claims"
        assert "No active claim is selected." in result["message"]
        assert result["recommended_action"]["command"] == "principia:init"

    def test_auto_detects_legacy_cycle(self, research_dir):
        import json

        sub_path = self._make_sub_unit(research_dir)
        rc, out, _ = run_manage(research_dir, "next", "auto")
        assert rc == 0
        state = json.loads(out)
        assert state["sub_unit"] == sub_path
        assert state["action"] == "dispatch_architect"

    def test_auto_follows_dashboard_guidance_when_waiting_on_external_result(self, research_dir):
        import json

        from principia.core.orchestration import compute_north_star_version

        (research_dir / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
        (research_dir / ".context.md").write_text("# Context\n", encoding="utf-8")
        north_star_version = compute_north_star_version(research_dir)

        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: pending\ndate: 2026-01-01\n"
            f"north_star_version: {north_star_version}\n---\n\n# Claim\n",
            encoding="utf-8",
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (claim / role).mkdir()

        rc, _out, _ = run_manage(research_dir, "prompt", "claims/claim-1-test")
        assert rc == 0

        rc, out, _ = run_manage(research_dir, "next", "auto")
        assert rc == 0
        result = json.loads(out)
        assert result["status"] == "guided_next"
        assert result["active_claim"] == "claims/claim-1-test"
        assert result["recommended_action"]["command"] == "dispatch-log"
        assert result["recommended_action"]["cycle"] == "claim-1-test"


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
        packet_file = sub / "architect" / "round-1" / "packet.md"
        assert packet_file.exists()

    def test_prompt_auto_logs_dispatch(self, research_dir):
        import json

        sub = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        sub.mkdir(parents=True)
        (sub / "frontier.md").write_text(
            "---\nid: s1a-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Probe\n"
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (sub / role).mkdir()

        rc, _out, _ = run_manage(research_dir, "prompt", "cycles/cycle-1/unit-1-test/sub-1a-probe")
        assert rc == 0

        rc, out, _ = run_manage(research_dir, "dispatch-log", "--json")
        assert rc == 0
        data = json.loads(out)
        assert any(row["action"] == "dispatch" for row in data)
        logged = next(row for row in data if row["action"] == "dispatch")
        assert logged["sub_unit"] == "cycles/cycle-1/unit-1-test/sub-1a-probe"
        assert logged["prompt_path"].endswith("prompt.md")


class TestCmdPacket:
    def test_generates_packet_file(self, research_dir):
        sub = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        sub.mkdir(parents=True)
        (sub / "frontier.md").write_text(
            "---\nid: s1a-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Probe\n"
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (sub / role).mkdir()

        rc, out, _ = run_manage(research_dir, "packet", "cycles/cycle-1/unit-1-test/sub-1a-probe")
        assert rc == 0
        assert "Written:" in out
        packet_file = sub / "architect" / "round-1" / "packet.md"
        assert packet_file.exists()
        content = packet_file.read_text(encoding="utf-8")
        assert "Dispatch Packet" in content

    def test_packet_auto_logs_preparation(self, research_dir):
        import json

        sub = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        sub.mkdir(parents=True)
        (sub / "frontier.md").write_text(
            "---\nid: s1a-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Probe\n"
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (sub / role).mkdir()

        rc, _out, _ = run_manage(research_dir, "packet", "cycles/cycle-1/unit-1-test/sub-1a-probe")
        assert rc == 0

        rc, out, _ = run_manage(research_dir, "dispatch-log", "--json")
        assert rc == 0
        data = json.loads(out)
        assert any(row["action"] == "packet" for row in data)
        logged = next(row for row in data if row["action"] == "packet")
        assert logged["packet_path"].endswith("packet.md")
        assert logged["result_path"].endswith("result.md")


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

    def test_logs_recorded_dispatch_event(self, research_dir):
        import json

        sub_path = self._make_verdicted_sub_unit(research_dir, verdict="PROVEN")
        run_manage(research_dir, "build")
        rc, _out, _ = run_manage(research_dir, "post-verdict", sub_path)
        assert rc == 0

        rc, out, _ = run_manage(research_dir, "dispatch-log", "--json")
        assert rc == 0
        data = json.loads(out)
        recorded = next(row for row in data if row["action"] == "recorded" and row["agent"] == "arbiter")
        assert recorded["sub_unit"] == sub_path
        assert recorded["result_path"].endswith("arbiter/results/verdict.md")
        assert "PROVEN" in recorded["details"]

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

    def test_disproven_uses_verdict_frontmatter_id(self, research_dir):
        from frontmatter import parse_frontmatter

        sub_path = self._make_verdicted_sub_unit(research_dir, verdict="DISPROVEN")
        verdict_file = research_dir / sub_path / "arbiter" / "results" / "verdict.md"
        verdict_file.write_text(
            "---\nid: custom-verdict\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "# Verdict\n\n**Verdict**: DISPROVEN\n**Confidence**: high\n"
        )

        run_manage(research_dir, "build")
        rc, _out, _ = run_manage(research_dir, "post-verdict", sub_path)
        assert rc == 0

        meta = parse_frontmatter((research_dir / sub_path / "claim.md").read_text())
        assert meta["falsified_by"] == "custom-verdict"

        rc, _out, err = run_manage(research_dir, "build")
        assert rc == 0
        assert "orphan" not in err.lower()

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

    def test_rejects_verdict_only_directory_without_mutating(self, research_dir):
        sub = research_dir / "claims" / "claim-1-bad"
        verdict_dir = sub / "arbiter" / "results"
        verdict_dir.mkdir(parents=True)
        verdict_file = verdict_dir / "verdict.md"
        verdict_file.write_text(
            "---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: PROVEN\n**Confidence**: high\n"
        )

        rc, out, err = run_manage(research_dir, "post-verdict", "claims/claim-1-bad")
        combined = out + err

        assert rc != 0
        assert "claim" in combined.lower()
        assert verdict_file.exists()
        assert not (sub / ".post_verdict_done").exists()

        rc, query_out, _ = run_manage(research_dir, "query", "SELECT event FROM ledger")
        assert rc == 0
        assert "(no results)" in query_out

    def test_rejects_invalid_utf8_claim_file_without_traceback(self, research_dir):
        sub = research_dir / "claims" / "claim-1-bad"
        verdict_dir = sub / "arbiter" / "results"
        verdict_dir.mkdir(parents=True)
        claim_file = sub / "claim.md"
        claim_file.write_bytes(
            b"---\nid: h1-claim\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Claim\xff\n"
        )
        (verdict_dir / "verdict.md").write_text(
            "---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: PROVEN\n**Confidence**: high\n"
        )

        rc, out, err = run_manage(research_dir, "post-verdict", "claims/claim-1-bad")
        combined = out + err

        assert rc != 0
        assert "utf-8" in combined.lower()
        assert "traceback" not in combined.lower()
        assert not (sub / ".post_verdict_done").exists()

    def test_rejects_invalid_utf8_verdict_file_without_traceback(self, research_dir):
        sub = research_dir / "claims" / "claim-1-bad-verdict"
        verdict_dir = sub / "arbiter" / "results"
        verdict_dir.mkdir(parents=True)
        (sub / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Claim\n"
        )
        (verdict_dir / "verdict.md").write_bytes(
            b"---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            b"**Verdict**: PROVEN\n**Confidence**: high\xff\n"
        )

        rc, out, err = run_manage(research_dir, "post-verdict", "claims/claim-1-bad-verdict")
        combined = out + err

        assert rc != 0
        assert "verdict" in combined.lower()
        assert "traceback" not in combined.lower()
        assert not (sub / ".post_verdict_done").exists()

    def test_legacy_cycle_updates_frontier(self, research_dir):
        from frontmatter import parse_frontmatter

        sub = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        (sub / "arbiter" / "results").mkdir(parents=True)
        (sub / "frontier.md").write_text(
            "---\nid: s1a-frontier\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Probe\n"
        )
        (sub / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: PROVEN\n**Confidence**: high\n"
        )

        run_manage(research_dir, "build")
        rc, _out, _ = run_manage(research_dir, "post-verdict", "cycles/cycle-1/unit-1-test/sub-1a-probe")
        assert rc == 0

        meta = parse_frontmatter((sub / "frontier.md").read_text())
        assert meta["status"] == "proven"


class TestReplaceVerdictCascadeRevert:
    """Regression: replace-verdict must revert transitive cascade and reset confidence."""

    def test_transitive_cascade_reverted(self, research_dir):
        """Given root→b→c, disprove root, then replace-verdict: both b and c must revert."""
        from frontmatter import parse_frontmatter

        from config import init_paths

        init_paths(research_dir)

        # Create root claim (will be disproven)
        root = research_dir / "claims" / "claim-1-root"
        root.mkdir(parents=True)
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (root / role).mkdir()
        (root / "claim.md").write_text(
            "---\nid: h1-root\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Root\n"
        )
        # Architect + adversary + experimenter + verdict
        (root / "architect" / "round-1").mkdir()
        (root / "architect" / "round-1" / "result.md").write_text(
            "---\nid: a1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Proposal\n"
        )
        (root / "adversary" / "round-1").mkdir()
        (root / "adversary" / "round-1" / "result.md").write_text(
            "---\nid: r1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Attack\n\n**Severity**: Minor\n"
        )
        (root / "experimenter" / "results").mkdir()
        (root / "experimenter" / "results" / "output.md").write_text(
            "---\nid: e1\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n# Results\n"
        )
        (root / "arbiter" / "results").mkdir()
        (root / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: DISPROVEN\n**Confidence**: high\n"
        )

        # Create claim b (depends on root)
        b = research_dir / "claims" / "claim-2-b"
        b.mkdir(parents=True)
        (b / "claim.md").write_text(
            "---\nid: h2-b\ntype: claim\nstatus: active\ndate: 2026-01-01\n"
            "depends_on: [h1-root]\nconfidence: high\n---\n\n# B\n"
        )

        # Create claim c (depends on b — transitive dep on root)
        c = research_dir / "claims" / "claim-3-c"
        c.mkdir(parents=True)
        (c / "claim.md").write_text(
            "---\nid: h3-c\ntype: claim\nstatus: active\ndate: 2026-01-01\n"
            "depends_on: [h2-b]\nconfidence: high\n---\n\n# C\n"
        )

        # Build, then post-verdict to trigger cascade
        run_manage(research_dir, "build")
        run_manage(research_dir, "post-verdict", "claims/claim-1-root")

        # Verify cascade happened
        b_meta = parse_frontmatter((b / "claim.md").read_text())
        c_meta = parse_frontmatter((c / "claim.md").read_text())
        assert b_meta["status"] == "weakened"
        assert c_meta["status"] == "weakened"

        # Now replace-verdict — should restore both b and c to their prior state
        rc, _out, _ = run_manage(research_dir, "replace-verdict", "claims/claim-1-root")
        assert rc == 0

        # Both must be restored to active with their original confidence
        b_meta = parse_frontmatter((b / "claim.md").read_text())
        c_meta = parse_frontmatter((c / "claim.md").read_text())
        assert b_meta["status"] == "active", f"b should be active, got {b_meta['status']}"
        assert c_meta["status"] == "active", f"c should be active, got {c_meta['status']}"
        assert b_meta["confidence"] == "high"
        assert c_meta["confidence"] == "high"

        # Root itself should be active with falsified_by cleared
        root_meta = parse_frontmatter((root / "claim.md").read_text())
        assert root_meta["status"] == "active"
        assert not root_meta.get("falsified_by")

    def test_multi_disproval_preserves_other_weakening(self, research_dir):
        """Regression: node depending on two disproven claims stays weakened when only one is reverted."""
        from frontmatter import parse_frontmatter

        from config import init_paths

        init_paths(research_dir)

        def _make_disproven_claim(name, claim_num):
            d = research_dir / "claims" / f"claim-{claim_num}-{name}"
            d.mkdir(parents=True)
            for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
                (d / role).mkdir()
            (d / "claim.md").write_text(
                f"---\nid: h{claim_num}-{name}\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# {name}\n"
            )
            (d / "architect" / "round-1").mkdir()
            (d / "architect" / "round-1" / "result.md").write_text(
                "---\nid: a\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# P\n"
            )
            (d / "adversary" / "round-1").mkdir()
            (d / "adversary" / "round-1" / "result.md").write_text(
                "---\nid: r\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# A\n\n**Severity**: Minor\n"
            )
            (d / "experimenter" / "results").mkdir()
            (d / "experimenter" / "results" / "output.md").write_text(
                "---\nid: e\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n# R\n"
            )
            (d / "arbiter" / "results").mkdir()
            (d / "arbiter" / "results" / "verdict.md").write_text(
                "---\nid: v\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
                "**Verdict**: DISPROVEN\n**Confidence**: high\n"
            )
            return f"claims/claim-{claim_num}-{name}"

        # Two independent disproven claims
        path_a = _make_disproven_claim("alpha", 1)
        path_b = _make_disproven_claim("beta", 2)

        # A dependent that depends on BOTH
        dep = research_dir / "claims" / "claim-3-dep"
        dep.mkdir(parents=True)
        (dep / "claim.md").write_text(
            "---\nid: h3-dep\ntype: claim\nstatus: active\ndate: 2026-01-01\n"
            "depends_on: [h1-alpha, h2-beta]\n---\n\n# Dep\n"
        )

        # Disprove both
        run_manage(research_dir, "build")
        run_manage(research_dir, "post-verdict", path_a)
        run_manage(research_dir, "post-verdict", path_b)

        dep_meta = parse_frontmatter((dep / "claim.md").read_text())
        assert dep_meta["status"] == "weakened"

        # Revert only alpha — dep should STAY weakened because beta is still disproven
        run_manage(research_dir, "replace-verdict", path_a)

        dep_meta = parse_frontmatter((dep / "claim.md").read_text())
        assert dep_meta["status"] == "weakened", (
            f"dep should stay weakened (beta still disproven), got {dep_meta['status']}"
        )

    def test_legacy_cycle_resets_frontier(self, research_dir):
        """replace-verdict must reset legacy frontier.md claims too."""
        from frontmatter import parse_frontmatter

        sub = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        (sub / "arbiter" / "results").mkdir(parents=True)
        (sub / "frontier.md").write_text(
            "---\nid: s1a-frontier\ntype: claim\nstatus: disproven\n"
            "date: 2026-01-01\nfalsified_by: v1\n---\n\n# Probe\n"
        )
        (sub / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: DISPROVEN\n**Confidence**: high\n"
        )

        rc, _out, err = run_manage(research_dir, "replace-verdict", "cycles/cycle-1/unit-1-test/sub-1a-probe")
        assert rc == 0
        assert "orphan" not in err.lower()

        meta = parse_frontmatter((sub / "frontier.md").read_text())
        assert meta["status"] == "active"
        assert not meta.get("falsified_by")

    def test_replace_verdict_restores_previous_state(self, research_dir):
        """Rollback should restore the dependent's prior status/confidence."""
        from frontmatter import parse_frontmatter

        root = research_dir / "claims" / "claim-1-root"
        root.mkdir(parents=True)
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (root / role).mkdir()
        (root / "claim.md").write_text(
            "---\nid: h1-root\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Root\n"
        )
        (root / "architect" / "round-1").mkdir()
        (root / "architect" / "round-1" / "result.md").write_text(
            "---\nid: a1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Proposal\n"
        )
        (root / "adversary" / "round-1").mkdir()
        (root / "adversary" / "round-1" / "result.md").write_text(
            "---\nid: r1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Attack\n\n**Severity**: Minor\n"
        )
        (root / "experimenter" / "results").mkdir()
        (root / "experimenter" / "results" / "output.md").write_text(
            "---\nid: e1\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n# Results\n"
        )
        (root / "arbiter" / "results").mkdir()
        (root / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: verdict-1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: DISPROVEN\n**Confidence**: high\n"
        )

        dep = research_dir / "claims" / "claim-2-dep"
        dep.mkdir(parents=True)
        (dep / "claim.md").write_text(
            "---\nid: h2-dep\ntype: claim\nstatus: partial\ndate: 2026-01-01\n"
            "depends_on: [h1-root]\nconfidence: moderate\n---\n\n# Dep\n"
        )

        run_manage(research_dir, "build")
        run_manage(research_dir, "post-verdict", "claims/claim-1-root")

        rc, _out, _ = run_manage(research_dir, "replace-verdict", "claims/claim-1-root")
        assert rc == 0

        dep_meta = parse_frontmatter((dep / "claim.md").read_text())
        assert dep_meta["status"] == "partial"
        assert dep_meta["confidence"] == "moderate"

    def test_replace_verdict_preserves_preexisting_weakened_state(self, research_dir):
        """Rollback should restore a dependent that was already weakened before cascade."""
        from frontmatter import parse_frontmatter

        root = research_dir / "claims" / "claim-1-root"
        root.mkdir(parents=True)
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (root / role).mkdir()
        (root / "claim.md").write_text(
            "---\nid: h1-root\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Root\n"
        )
        (root / "architect" / "round-1").mkdir()
        (root / "architect" / "round-1" / "result.md").write_text(
            "---\nid: a1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Proposal\n"
        )
        (root / "adversary" / "round-1").mkdir()
        (root / "adversary" / "round-1" / "result.md").write_text(
            "---\nid: r1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Attack\n\n**Severity**: Minor\n"
        )
        (root / "experimenter" / "results").mkdir()
        (root / "experimenter" / "results" / "output.md").write_text(
            "---\nid: e1\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n# Results\n"
        )
        (root / "arbiter" / "results").mkdir()
        (root / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: verdict-1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: DISPROVEN\n**Confidence**: high\n"
        )

        dep = research_dir / "claims" / "claim-2-dep"
        dep.mkdir(parents=True)
        (dep / "claim.md").write_text(
            "---\nid: h2-dep\ntype: claim\nstatus: weakened\ndate: 2026-01-01\n"
            "depends_on: [h1-root]\nconfidence: low\n---\n\n# Dep\n"
        )

        run_manage(research_dir, "build")
        run_manage(research_dir, "post-verdict", "claims/claim-1-root")

        rc, _out, _ = run_manage(research_dir, "replace-verdict", "claims/claim-1-root")
        assert rc == 0

        dep_meta = parse_frontmatter((dep / "claim.md").read_text())
        assert dep_meta["status"] == "weakened"
        assert dep_meta["confidence"] == "low"

    def test_rejects_verdict_only_directory_without_deleting_verdict(self, research_dir):
        sub = research_dir / "claims" / "claim-1-bad"
        verdict_dir = sub / "arbiter" / "results"
        verdict_dir.mkdir(parents=True)
        verdict_file = verdict_dir / "verdict.md"
        verdict_file.write_text(
            "---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: DISPROVEN\n**Confidence**: high\n"
        )

        rc, out, err = run_manage(research_dir, "replace-verdict", "claims/claim-1-bad")
        combined = out + err

        assert rc != 0
        assert "claim" in combined.lower()
        assert verdict_file.exists()

        rc, query_out, _ = run_manage(research_dir, "query", "SELECT event FROM ledger")
        assert rc == 0
        assert "(no results)" in query_out

    def test_rejects_invalid_utf8_claim_file_without_deleting_verdict(self, research_dir):
        sub = research_dir / "claims" / "claim-1-bad"
        verdict_dir = sub / "arbiter" / "results"
        verdict_dir.mkdir(parents=True)
        claim_file = sub / "claim.md"
        claim_file.write_bytes(
            b"---\nid: h1-claim\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Claim\xff\n"
        )
        verdict_file = verdict_dir / "verdict.md"
        verdict_file.write_text(
            "---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: DISPROVEN\n**Confidence**: high\n"
        )

        rc, out, err = run_manage(research_dir, "replace-verdict", "claims/claim-1-bad")
        combined = out + err

        assert rc != 0
        assert "utf-8" in combined.lower()
        assert "traceback" not in combined.lower()
        assert verdict_file.exists()


class TestCmdReopen:
    def _make_disproven_claim_with_dep(self, research_dir):
        """Create a disproven claim with one weakened dependent."""
        from config import init_paths

        init_paths(research_dir)

        root = research_dir / "claims" / "claim-1-root"
        root.mkdir(parents=True)
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (root / role).mkdir()
        (root / "claim.md").write_text(
            "---\nid: h1-root\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Root\n"
        )
        (root / "architect" / "round-1").mkdir()
        (root / "architect" / "round-1" / "result.md").write_text(
            "---\nid: a1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# P\n"
        )
        (root / "adversary" / "round-1").mkdir()
        (root / "adversary" / "round-1" / "result.md").write_text(
            "---\nid: r1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n**Severity**: Minor\n"
        )
        (root / "experimenter" / "results").mkdir()
        (root / "experimenter" / "results" / "output.md").write_text(
            "---\nid: e1\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n# Results\n"
        )
        (root / "arbiter" / "results").mkdir()
        (root / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: DISPROVEN\n**Confidence**: high\n"
        )
        dep = research_dir / "claims" / "claim-2-dep"
        dep.mkdir(parents=True)
        (dep / "claim.md").write_text(
            "---\nid: h2-dep\ntype: claim\nstatus: active\ndate: 2026-01-01\n"
            "depends_on: [h1-root]\nconfidence: high\n---\n\n# Dep\n"
        )
        run_manage(research_dir, "build")
        run_manage(research_dir, "post-verdict", "claims/claim-1-root")
        return research_dir

    def test_reopen_disproven_clears_falsified_by(self, research_dir):
        """Reopen a disproven claim: falsified_by must be cleared."""
        from frontmatter import parse_frontmatter

        self._make_disproven_claim_with_dep(research_dir)
        rc, _out, _ = run_manage(research_dir, "reopen", "h1-root")
        assert rc == 0
        meta = parse_frontmatter((research_dir / "claims" / "claim-1-root" / "claim.md").read_text())
        assert meta["status"] == "active"
        assert not meta.get("falsified_by")

    def test_reopen_disproven_reverts_dependent(self, research_dir):
        """Reopen a disproven claim: weakened dependent must be restored."""
        from frontmatter import parse_frontmatter

        self._make_disproven_claim_with_dep(research_dir)
        run_manage(research_dir, "reopen", "h1-root")
        dep_meta = parse_frontmatter((research_dir / "claims" / "claim-2-dep" / "claim.md").read_text())
        assert dep_meta["status"] == "active", f"dep should be active, got {dep_meta['status']}"
        assert dep_meta["confidence"] == "high"

    def test_reopen_disproven_no_orphan_edges(self, research_dir):
        """After reopen + rebuild, no orphan edges should remain."""
        self._make_disproven_claim_with_dep(research_dir)
        run_manage(research_dir, "reopen", "h1-root")
        rc, _out, err = run_manage(research_dir, "build")
        assert rc == 0
        assert "orphan" not in err.lower()

    def test_reopen_proven_works(self, research_dir):
        """Reopen a proven claim: should reset to active."""
        from frontmatter import parse_frontmatter

        from config import init_paths

        init_paths(research_dir)
        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (claim / role).mkdir()
        (claim / "claim.md").write_text(
            "---\nid: h1-test\ntype: claim\nstatus: proven\ndate: 2026-01-01\n---\n\n# Test\n"
        )
        run_manage(research_dir, "build")
        rc, _out, _ = run_manage(research_dir, "reopen", "h1-test")
        assert rc == 0
        meta = parse_frontmatter((claim / "claim.md").read_text())
        assert meta["status"] == "active"

    def test_reopen_restores_previous_state(self, research_dir):
        """Reopen should restore the dependent's prior status/confidence."""
        from frontmatter import parse_frontmatter

        root = research_dir / "claims" / "claim-1-root"
        root.mkdir(parents=True)
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (root / role).mkdir()
        (root / "claim.md").write_text(
            "---\nid: h1-root\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Root\n"
        )
        (root / "architect" / "round-1").mkdir()
        (root / "architect" / "round-1" / "result.md").write_text(
            "---\nid: a1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# P\n"
        )
        (root / "adversary" / "round-1").mkdir()
        (root / "adversary" / "round-1" / "result.md").write_text(
            "---\nid: r1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n**Severity**: Minor\n"
        )
        (root / "experimenter" / "results").mkdir()
        (root / "experimenter" / "results" / "output.md").write_text(
            "---\nid: e1\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n# Results\n"
        )
        (root / "arbiter" / "results").mkdir()
        (root / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: verdict-1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: DISPROVEN\n**Confidence**: high\n"
        )

        dep = research_dir / "claims" / "claim-2-dep"
        dep.mkdir(parents=True)
        dep_path = dep / "claim.md"
        dep_path.write_text(
            "---\nid: h2-dep\ntype: claim\nstatus: partial\ndate: 2026-01-01\n"
            "depends_on: [h1-root]\nconfidence: moderate\n---\n\n# Dep\n"
        )

        run_manage(research_dir, "build")
        run_manage(research_dir, "post-verdict", "claims/claim-1-root")

        rc, _out, _ = run_manage(research_dir, "reopen", "h1-root")
        assert rc == 0

        dep_meta = parse_frontmatter(dep_path.read_text())
        assert dep_meta["status"] == "partial"
        assert dep_meta["confidence"] == "moderate"

    def test_reopen_preserves_preexisting_weakened_state(self, research_dir):
        """Reopen should restore a dependent that was already weakened before cascade."""
        from frontmatter import parse_frontmatter

        root = research_dir / "claims" / "claim-1-root"
        root.mkdir(parents=True)
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (root / role).mkdir()
        (root / "claim.md").write_text(
            "---\nid: h1-root\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Root\n"
        )
        (root / "architect" / "round-1").mkdir()
        (root / "architect" / "round-1" / "result.md").write_text(
            "---\nid: a1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# P\n"
        )
        (root / "adversary" / "round-1").mkdir()
        (root / "adversary" / "round-1" / "result.md").write_text(
            "---\nid: r1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n**Severity**: Minor\n"
        )
        (root / "experimenter" / "results").mkdir()
        (root / "experimenter" / "results" / "output.md").write_text(
            "---\nid: e1\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n# Results\n"
        )
        (root / "arbiter" / "results").mkdir()
        (root / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: verdict-1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "**Verdict**: DISPROVEN\n**Confidence**: high\n"
        )

        dep = research_dir / "claims" / "claim-2-dep"
        dep.mkdir(parents=True)
        dep_path = dep / "claim.md"
        dep_path.write_text(
            "---\nid: h2-dep\ntype: claim\nstatus: weakened\ndate: 2026-01-01\n"
            "depends_on: [h1-root]\nconfidence: low\n---\n\n# Dep\n"
        )

        run_manage(research_dir, "build")
        run_manage(research_dir, "post-verdict", "claims/claim-1-root")

        rc, _out, _ = run_manage(research_dir, "reopen", "h1-root")
        assert rc == 0

        dep_meta = parse_frontmatter(dep_path.read_text())
        assert dep_meta["status"] == "weakened"
        assert dep_meta["confidence"] == "low"

    def test_reopen_rejects_non_claim_nodes(self, research_dir):
        assumption_dir = research_dir / "context" / "assumptions"
        assumption_dir.mkdir(parents=True, exist_ok=True)
        (assumption_dir / "a.md").write_text(
            "---\nid: a1\ntype: assumption\nstatus: disproven\ndate: 2026-01-01\n---\n\n# A\n"
        )

        rc, out, err = run_manage(research_dir, "reopen", "a1")
        combined = out + err

        assert rc != 0
        assert "claim" in combined.lower()

        _rc, query_out, _ = run_manage(research_dir, "query", "SELECT status FROM nodes WHERE id='a1'")
        assert "disproven" in query_out


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

    def test_invalid_utf8_paste_reports_clean_error(self, research_dir, tmp_path):
        paste_file = tmp_path / "paste.md"
        paste_file.write_bytes(b"# Verdict\n\n**Verdict**: PROVEN\n**Confidence**: high\n\xff\n")

        rc, out, err = run_manage(research_dir, "validate-paste", "--agent", "arbiter", "--file", str(paste_file))
        combined = out + err

        assert rc != 0
        assert "utf-8" in combined.lower()
        assert "traceback" not in combined.lower()


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

    def test_autonomy_config_honors_repo_local_override(self, research_dir):
        import json

        (research_dir / ".config.md").write_text(
            "# Principia Configuration\n\n- Workflow Autonomy: yolo\n",
            encoding="utf-8",
        )

        rc, out, _ = run_manage(research_dir, "autonomy-config")
        assert rc == 0, f"autonomy-config failed: {out}"
        result = json.loads(out)
        assert result["mode"] == "yolo"
        assert "understand" in result["checkpoint_at"]


class TestCmdDashboard:
    def test_reports_missing_workspace_before_bootstrap(self, tmp_path):
        import json

        research_dir = tmp_path / "principia"
        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out[out.find("{") :])
        assert result["init"]["status"] == "missing_workspace"
        assert result["init"]["workspace_exists"] is False
        assert result["init"]["repo_scan"]["complete"] is False
        assert result["init"]["north_star_interview"]["complete"] is False
        assert result["init"]["north_star_interview"]["questions"]
        assert result["operator_guidance"]["recommended_action"]["command"] == "principia:init"
        assert "inspect the repo and lock the north star" in result["operator_guidance"]["summary"].lower()

    def test_reports_init_discussion_state_without_north_star(self, research_dir):
        import json

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        assert result["init"]["status"] == "discussion_in_progress"
        assert result["init"]["north_star_locked"] is False
        assert result["init"]["repo_scan"]["complete"] is False
        assert result["init"]["north_star_interview"]["complete"] is False
        assert len(result["init"]["north_star_interview"]["questions"]) == 6
        assert result["preferences"]["workflow_autonomy"] == "checkpoints"
        assert result["preferences"]["sidecars"]["deep-thinker"] == "ask"
        assert "inspect the repo and interview you" in result["operator_guidance"]["summary"].lower()

    def test_reports_ready_for_claims_after_north_star_is_locked(self, research_dir):
        import json

        (research_dir / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
        (research_dir / ".context.md").write_text("# Context\n", encoding="utf-8")

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        assert result["init"]["north_star_locked"] is True
        assert result["init"]["status"] in {"ready_for_claims", "north_star_locked"}
        assert result["patch_status"]["current_version"]
        assert result["warnings"] == []

    def test_keeps_init_blocked_until_repo_scan_summary_exists(self, research_dir):
        import json

        (research_dir / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        assert result["init"]["north_star_locked"] is True
        assert result["init"]["repo_scan"]["complete"] is False
        assert result["operator_guidance"]["recommended_action"]["command"] == "principia:init"
        assert "write principia/.context.md" in result["operator_guidance"]["summary"].lower()

    def test_reports_stale_patch_status_when_claim_version_lags(self, research_dir):
        import json

        (research_dir / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
        (research_dir / ".context.md").write_text("# Context\n", encoding="utf-8")
        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\n"
            "id: h1-claim\n"
            "type: claim\n"
            "status: pending\n"
            "date: 2026-01-01\n"
            "north_star_version: old-version\n"
            "---\n\n"
            "# Claim\n",
            encoding="utf-8",
        )

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        assert result["patch_status"]["stale_claim_count"] == 1
        assert result["patch_status"]["needs_review"][0]["id"] == "h1-claim"
        assert result["warnings"][0]["code"] == "north_star_drift"
        assert result["warnings"][0]["count"] == 1
        assert result["operator_guidance"]["recommended_action"]["command"] == "patch-status"

    def test_reports_active_claim_dispatch_lifecycle(self, research_dir):
        import json

        (research_dir / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
        (research_dir / ".context.md").write_text("# Context\n", encoding="utf-8")
        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Claim\n",
            encoding="utf-8",
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (claim / role).mkdir()

        rc, _out, _ = run_manage(research_dir, "prompt", "claims/claim-1-test")
        assert rc == 0

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        lifecycle = result["dispatch_lifecycle"]
        assert lifecycle["claim"] == "claims/claim-1-test"
        assert lifecycle["latest"]["action"] == "dispatch"
        assert lifecycle["latest"]["status"] == "waiting_result"
        assert lifecycle["outstanding"][0]["agent"] == "architect"
        assert lifecycle["outstanding"][0]["status"] == "waiting_result"
        assert lifecycle["outstanding"][0]["prompt_path"].endswith("architect/round-1/prompt.md")
        assert lifecycle["stale"] == []
        assert result["operator_guidance"]["recommended_action"]["command"] == "dispatch-log"
        assert result["operator_guidance"]["recommended_action"]["cycle"] == "claim-1-test"

    def test_reports_packet_as_ready_to_send(self, research_dir):
        import json

        from principia.core.orchestration import compute_north_star_version

        (research_dir / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
        (research_dir / ".context.md").write_text("# Context\n", encoding="utf-8")
        north_star_version = compute_north_star_version(research_dir)
        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: pending\ndate: 2026-01-01\n"
            f"north_star_version: {north_star_version}\n---\n\n# Claim\n",
            encoding="utf-8",
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (claim / role).mkdir()

        rc, _out, _ = run_manage(research_dir, "packet", "claims/claim-1-test")
        assert rc == 0

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        lifecycle = result["dispatch_lifecycle"]
        assert lifecycle["latest"]["status"] == "ready_to_send"
        assert lifecycle["outstanding"][0]["status"] == "ready_to_send"
        assert lifecycle["stale"] == []
        overview = result["dispatch_overview"]
        assert overview["ready_to_send_claim_count"] == 1
        assert overview["ready_to_send_handoff_count"] == 1
        assert overview["ready_to_send_claims"][0]["claim"] == "claims/claim-1-test"
        assert result["operator_guidance"]["recommended_action"]["command"] == "prompt"
        assert result["operator_guidance"]["recommended_action"]["claim_path"] == "claims/claim-1-test"

    def test_warns_when_dispatch_audit_is_stale(self, research_dir):
        import json

        (research_dir / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
        (research_dir / ".context.md").write_text("# Context\n", encoding="utf-8")
        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Claim\n",
            encoding="utf-8",
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (claim / role).mkdir()

        run_manage(research_dir, "build")
        rc, _out, _ = run_manage(
            research_dir,
            "log-dispatch",
            "--cycle",
            "claim-1-test",
            "--agent",
            "architect",
            "--action",
            "dispatch",
            "--sub-unit",
            "claims/claim-1-test",
            "--dispatch-mode",
            "external",
            "--packet-path",
            "claims/claim-1-test/architect/round-1/packet.md",
            "--prompt-path",
            "claims/claim-1-test/architect/round-1/prompt.md",
            "--result-path",
            "claims/claim-1-test/architect/round-1/result.md",
        )
        assert rc == 0

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        lifecycle = result["dispatch_lifecycle"]
        assert lifecycle["stale"][0]["agent"] == "architect"
        assert lifecycle["stale"][0]["status"] == "stale"
        overview = result["dispatch_overview"]
        assert overview["stale_claim_count"] == 1
        assert overview["stale_handoff_count"] == 1
        assert overview["stale_claims"][0]["claim"] == "claims/claim-1-test"
        warning = next(w for w in result["warnings"] if w["code"] == "dispatch_handoff_stale")
        assert warning["count"] == 1
        assert warning["claim_count"] == 1
        assert warning["claims"][0]["claim"] == "claims/claim-1-test"
        assert result["operator_guidance"]["recommended_action"]["command"] == "dispatch-log"
        assert result["operator_guidance"]["recommended_action"]["cycle"] == "claim-1-test"

    def test_workspace_warning_includes_non_active_stale_claims(self, research_dir):
        import json

        from principia.core.orchestration import compute_north_star_version

        (research_dir / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
        (research_dir / ".context.md").write_text("# Context\n", encoding="utf-8")
        (research_dir / "context" / "survey-topic.md").write_text("# Survey\n", encoding="utf-8")
        north_star_version = compute_north_star_version(research_dir)
        (research_dir / "blueprint.md").write_text(
            "# Blueprint\n\n```yaml\n# CLAIM_REGISTRY\nclaims:\n"
            '  - id: active\n    statement: "Active claim"\n    maturity: conjecture\n    confidence: low\n'
            '    depends_on: []\n    falsification: "Refute it"\n'
            '  - id: stale\n    statement: "Stale claim"\n    maturity: conjecture\n    confidence: low\n'
            '    depends_on: []\n    falsification: "Refute it"\n```\n',
            encoding="utf-8",
        )

        active_claim = research_dir / "claims" / "claim-1-active"
        stale_claim = research_dir / "claims" / "claim-2-stale"
        for claim_dir, claim_id in ((active_claim, "h1-active"), (stale_claim, "h2-stale")):
            claim_dir.mkdir(parents=True)
            (claim_dir / "claim.md").write_text(
                f"---\nid: {claim_id}\ntype: claim\nstatus: pending\ndate: 2026-01-01\n"
                f"north_star_version: {north_star_version}\n---\n\n# Claim\n",
                encoding="utf-8",
            )
            for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
                (claim_dir / role).mkdir()

        rc, _out, _ = run_manage(research_dir, "prompt", "claims/claim-1-active")
        assert rc == 0

        run_manage(research_dir, "build")
        rc, _out, _ = run_manage(
            research_dir,
            "log-dispatch",
            "--cycle",
            "claim-2-stale",
            "--agent",
            "architect",
            "--action",
            "dispatch",
            "--sub-unit",
            "claims/claim-2-stale",
            "--dispatch-mode",
            "external",
            "--packet-path",
            "claims/claim-2-stale/architect/round-1/packet.md",
            "--prompt-path",
            "claims/claim-2-stale/architect/round-1/prompt.md",
            "--result-path",
            "claims/claim-2-stale/architect/round-1/result.md",
        )
        assert rc == 0

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        assert result["dispatch_lifecycle"]["claim"] == "claims/claim-1-active"
        assert result["dispatch_lifecycle"]["stale"] == []
        overview = result["dispatch_overview"]
        assert overview["stale_claim_count"] == 1
        assert overview["waiting_result_claim_count"] == 1
        assert overview["stale_claims"][0]["claim"] == "claims/claim-2-stale"
        assert overview["waiting_result_claims"][0]["claim"] == "claims/claim-1-active"
        warning = next(w for w in result["warnings"] if w["code"] == "dispatch_handoff_stale")
        assert warning["claim_count"] == 1
        assert warning["claims"][0]["claim"] == "claims/claim-2-stale"
        assert result["operator_guidance"]["recommended_action"]["command"] == "dispatch-log"
        assert result["operator_guidance"]["recommended_action"]["cycle"] == "claim-2-stale"

    def test_counts_legacy_cycle_claims(self, research_dir):
        import json

        sub = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        sub.mkdir(parents=True)
        (sub / "frontier.md").write_text(
            "---\nid: s1a-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Probe\n"
        )

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        assert result["claims"].get("pending") == 1

    def test_excludes_verdict_artifacts_from_claim_counts(self, research_dir):
        import json

        claim = research_dir / "claims" / "claim-1-test"
        verdict_dir = claim / "arbiter" / "results"
        verdict_dir.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Claim\n"
        )
        (verdict_dir / "verdict.md").write_text(
            "---\nid: h1-arbiter-verdict\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n# Verdict\n"
        )

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        assert result["claims"].get("active") == 1

    def test_reports_assumption_blocked_claims(self, research_dir):
        import json

        assumptions = research_dir / "context" / "assumptions"
        assumptions.mkdir(parents=True, exist_ok=True)
        (assumptions / "a.md").write_text(
            "---\nid: a1\ntype: assumption\nstatus: active\ndate: 2026-01-01\n---\n\n# A\n"
        )

        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: pending\ndate: 2026-01-01\nassumes: [a1]\n---\n\n# C\n"
        )

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        assert result["blocked"] == [{"id": "h1-claim", "blocked_by": "a1"}]

    def test_last_verdict_ignores_non_claim_falsify_events(self, research_dir):
        import json

        assumptions = research_dir / "context" / "assumptions"
        assumptions.mkdir(parents=True, exist_ok=True)
        (assumptions / "a.md").write_text(
            "---\nid: a1\ntype: assumption\nstatus: pending\ndate: 2026-01-01\n---\n\n# A\n"
        )

        rc, _out, _ = run_manage(research_dir, "falsify", "a1")
        assert rc == 0

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        assert result["last_verdict"] is None

    def test_reports_pending_decisions_as_human_action(self, research_dir):
        import json

        from principia.core.orchestration import compute_north_star_version

        (research_dir / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
        (research_dir / ".context.md").write_text("# Context\n", encoding="utf-8")
        north_star_version = compute_north_star_version(research_dir)
        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: partial\ndate: 2026-01-01\n"
            f"north_star_version: {north_star_version}\n---\n\n# Claim\n",
            encoding="utf-8",
        )

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        assert result["pending_decisions"] == [
            {"id": "h1-claim", "status": "partial", "file": "claims/claim-1-test/claim.md"}
        ]
        assert result["operator_guidance"]["recommended_action"]["kind"] == "manual"
        assert result["operator_guidance"]["recommended_action"]["command"] == "review the claim outcome"
        assert result["operator_guidance"]["recommended_action"]["claim_path"] == "claims/claim-1-test"

    def test_reports_completed_claims_as_results_refresh(self, research_dir):
        import json

        from principia.core.orchestration import compute_north_star_version

        (research_dir / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
        (research_dir / ".context.md").write_text("# Context\n", encoding="utf-8")
        north_star_version = compute_north_star_version(research_dir)
        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: proven\ndate: 2026-01-01\n"
            f"north_star_version: {north_star_version}\n---\n\n# Claim\n",
            encoding="utf-8",
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (claim / role).mkdir()
        (claim / "arbiter" / "results").mkdir(parents=True, exist_ok=True)
        (claim / "arbiter" / "results" / "verdict.md").write_text(
            "---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n**Verdict**: PROVEN\n",
            encoding="utf-8",
        )
        (claim / ".post_verdict_done").write_text("2026-01-02", encoding="utf-8")
        run_manage(research_dir, "build")
        run_manage(research_dir, "post-verdict", "claims/claim-1-test")

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        assert result["operator_guidance"]["recommended_action"]["command"] == "results"

    def test_summarizes_delegation_policy_in_one_sentence(self, research_dir):
        import json

        (research_dir / ".config.md").write_text(
            "# Principia Configuration\n\n"
            "- Workflow Autonomy: checkpoints\n"
            "- Architect: external\n"
            "- Deep Thinker Sidecar: ask\n"
            "- Researcher Sidecar: auto\n"
            "- Coder Sidecar: off\n",
            encoding="utf-8",
        )

        rc, out, _ = run_manage(research_dir, "dashboard")
        assert rc == 0
        result = json.loads(out)
        summary = result["operator_guidance"]["autonomy"]["summary"]
        assert "Workflow runs in checkpoints mode" in summary
        assert "dispatch roles may hand off externally for architect" in summary
        assert "deep-thinker require approval" in summary
        assert "researcher auto-run" in summary
        assert "coder stay off" in summary


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
