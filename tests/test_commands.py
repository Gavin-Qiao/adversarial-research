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
        rc, out, _ = run_manage(research_dir, "new", "cycles/cycle-1/unit-1-test/thinker/round-1/result.md")
        assert rc == 0
        assert "Created" in out
        f = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "thinker" / "round-1" / "result.md"
        assert f.exists()
        content = f.read_text()
        assert "id: c1-u1-thinker-r1-result" in content
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
        from manage import serialise_frontmatter

        path = research_dir / "cycles" / "cycle-1" / "unit-1" / "thinker" / "round-1"
        path.mkdir(parents=True)
        (path / "result.md").write_text(
            serialise_frontmatter(
                {
                    "id": "c1-u1-thinker-r1-result",
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
        assert "Falsified: assumption-a1" in out
        # The thinker claim that assumes it should be set to undermined
        assert "undermined" in out

    def test_records_ledger(self, populated_research):
        run_manage(populated_research, "falsify", "assumption-a1")
        rc, out, _ = run_manage(populated_research, "query", "SELECT * FROM ledger WHERE event='falsified'")
        assert rc == 0
        assert "assumption-a1" in out

    def test_skips_already_falsified(self, populated_research):
        run_manage(populated_research, "falsify", "assumption-a1")
        _rc, out, _ = run_manage(populated_research, "falsify", "assumption-a1")
        assert "already falsified" in out.lower()

    def test_multi_level_cascade(self, research_dir):
        """A → B → C: falsify A, both B and C should be undermined."""
        from manage import serialise_frontmatter

        assume_dir = research_dir / "context" / "assumptions"
        assume_dir.mkdir(parents=True, exist_ok=True)
        (assume_dir / "a.md").write_text(
            serialise_frontmatter(
                {"id": "a", "type": "assumption", "status": "active", "date": "2026-01-01",
                 "depends_on": [], "assumes": []}
            ) + "\n# A\n"
        )
        cycles_dir = research_dir / "cycles" / "cycle-1" / "unit-1" / "thinker" / "round-1"
        cycles_dir.mkdir(parents=True)
        (cycles_dir / "result.md").write_text(
            serialise_frontmatter(
                {"id": "b", "type": "claim", "status": "active", "date": "2026-01-01",
                 "depends_on": [], "assumes": ["a"]}
            ) + "\n# B\n"
        )
        coder_dir = research_dir / "cycles" / "cycle-1" / "unit-1" / "coder" / "results"
        coder_dir.mkdir(parents=True)
        (coder_dir / "output.md").write_text(
            serialise_frontmatter(
                {"id": "c", "type": "evidence", "status": "active", "date": "2026-01-01",
                 "depends_on": ["b"], "assumes": []}
            ) + "\n# C\n"
        )
        rc, out, _ = run_manage(research_dir, "falsify", "a")
        assert rc == 0
        assert "undermined" in out
        # Verify both b and c are undermined via DB query
        _rc2, out2, _ = run_manage(
            research_dir, "query", "SELECT id, status FROM nodes WHERE status='undermined'"
        )
        assert "b" in out2
        assert "c" in out2

    def test_cascade_attenuates_confidence(self, research_dir):
        """Cascade should downgrade confidence on undermined nodes."""
        from manage import serialise_frontmatter

        assume_dir = research_dir / "context" / "assumptions"
        assume_dir.mkdir(parents=True, exist_ok=True)
        (assume_dir / "base.md").write_text(
            serialise_frontmatter(
                {"id": "base", "type": "assumption", "status": "active", "date": "2026-01-01",
                 "depends_on": [], "assumes": []}
            ) + "\n# Base\n"
        )
        cycles_dir = research_dir / "cycles" / "cycle-1" / "unit-1" / "thinker" / "round-1"
        cycles_dir.mkdir(parents=True)
        (cycles_dir / "result.md").write_text(
            serialise_frontmatter(
                {"id": "dep", "type": "claim", "status": "active", "date": "2026-01-01",
                 "depends_on": [], "assumes": ["base"], "confidence": "high"}
            ) + "\n# Dep\n"
        )
        rc, _out, _ = run_manage(research_dir, "falsify", "base")
        assert rc == 0
        # Check that confidence was attenuated: high → moderate
        _rc2, out2, _ = run_manage(
            research_dir, "query", "SELECT id, confidence FROM nodes WHERE id='dep'"
        )
        assert "moderate" in out2


class TestCmdSettle:
    def test_marks_settled(self, sample_node):
        rc, out, _ = run_manage(sample_node, "settle", "c1-u1-thinker-r1-result")
        assert rc == 0
        assert "Settled" in out

    def test_rejects_falsified(self, populated_research):
        run_manage(populated_research, "falsify", "assumption-a1")
        rc, out, _ = run_manage(populated_research, "settle", "assumption-a1")
        assert rc != 0
        assert "falsified" in out.lower()


class TestCmdStatus:
    def test_generates_frontier(self, populated_research):
        rc, out, _ = run_manage(populated_research, "status")
        assert rc == 0
        assert "Generated" in out
        frontier = populated_research / "FRONTIER.md"
        assert frontier.exists()
        content = frontier.read_text()
        assert "Research Frontier" in content


class TestCmdAssumptions:
    def test_generates_file(self, populated_research):
        rc, _out, _ = run_manage(populated_research, "assumptions")
        assert rc == 0
        assumptions = populated_research / "ASSUMPTIONS.md"
        assert assumptions.exists()
        content = assumptions.read_text()
        assert "assumption-a1" in content


class TestCmdCascade:
    def test_dry_run(self, populated_research):
        rc, out, _ = run_manage(populated_research, "cascade", "assumption-a1")
        assert rc == 0
        assert "Cascade analysis" in out
        # Should show the thinker claim as affected
        assert "c1-u1-thinker-r1-result" in out


class TestCmdScaffold:
    def test_creates_cycle(self, research_dir):
        rc, out, _ = run_manage(research_dir, "scaffold", "cycle", "enrichment")
        assert rc == 0
        assert "Created" in out
        d = research_dir / "cycles" / "cycle-1-enrichment"
        assert d.exists()
        assert (d / "frontier.md").exists()

    def test_creates_unit(self, research_dir):
        run_manage(research_dir, "scaffold", "cycle", "enrichment")
        rc, _out, _ = run_manage(
            research_dir, "scaffold", "unit", "bottleneck", "--parent", "cycles/cycle-1-enrichment"
        )
        assert rc == 0
        d = research_dir / "cycles" / "cycle-1-enrichment" / "unit-1-bottleneck"
        assert d.exists()

    def test_creates_sub_unit_with_role_dirs(self, research_dir):
        run_manage(research_dir, "scaffold", "cycle", "enrichment")
        run_manage(research_dir, "scaffold", "unit", "bottleneck", "--parent", "cycles/cycle-1-enrichment")
        rc, _out, _ = run_manage(
            research_dir,
            "scaffold",
            "sub-unit",
            "ratio-test",
            "--parent",
            "cycles/cycle-1-enrichment/unit-1-bottleneck",
        )
        assert rc == 0
        base = research_dir / "cycles" / "cycle-1-enrichment" / "unit-1-bottleneck" / "sub-1a-ratio-test"
        assert base.exists()
        for role in ("thinker", "refutor", "coder", "judge", "researcher"):
            assert (base / role).exists()

    def test_auto_numbering(self, research_dir):
        run_manage(research_dir, "scaffold", "cycle", "first")
        run_manage(research_dir, "scaffold", "cycle", "second")
        assert (research_dir / "cycles" / "cycle-1-first").exists()
        assert (research_dir / "cycles" / "cycle-2-second").exists()

    def test_requires_parent_for_unit(self, research_dir):
        rc, out, _ = run_manage(research_dir, "scaffold", "unit", "test")
        assert rc != 0
        assert "parent" in out.lower() or "error" in out.lower()


class TestCmdLogDispatch:
    def test_logs_dispatch(self, research_dir):
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(
            research_dir,
            "log-dispatch",
            "--cycle", "cycle-1-test",
            "--agent", "thinker",
            "--action", "dispatch",
            "--round", "1",
        )
        assert rc == 0
        assert "Logged" in out

    def test_logs_side_dispatch(self, research_dir):
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(
            research_dir,
            "log-dispatch",
            "--cycle", "cycle-1-test",
            "--agent", "coder",
            "--action", "side_dispatch",
            "--details", "checking empirical claim",
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
            "--cycle", "cycle-1",
            "--agent", "thinker",
            "--action", "dispatch",
            "--round", "1",
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
            "--cycle", "cycle-1",
            "--agent", "refutor",
            "--action", "dispatch",
            "--round", "1",
        )
        rc, out, _ = run_manage(research_dir, "dispatch-log", "--json")
        assert rc == 0
        # The build output may precede the JSON — find the JSON array
        json_start = out.index("[")
        data = json.loads(out[json_start:])
        assert len(data) == 1
        assert data[0]["agent"] == "refutor"

    def test_filter_by_cycle(self, research_dir):
        run_manage(research_dir, "build")
        run_manage(
            research_dir, "log-dispatch",
            "--cycle", "cycle-1", "--agent", "thinker", "--action", "dispatch",
        )
        run_manage(
            research_dir, "log-dispatch",
            "--cycle", "cycle-2", "--agent", "refutor", "--action", "dispatch",
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
    def test_empty_research_returns_gather_context(self, research_dir):
        rc, out, _ = run_manage(research_dir, "investigate-next")
        assert rc == 0
        import json
        state = json.loads(out)
        assert state["action"] == "gather_context"


class TestCmdParseFramework:
    def test_no_framework_exits_with_error(self, research_dir):
        rc, _out, _ = run_manage(research_dir, "parse-framework")
        assert rc != 0

    def test_with_valid_framework(self, research_dir):
        (research_dir / "framework.md").write_text("""\
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
            "--id", "ring-gen",
            "--name", "Ring Generator",
            "--type", "function",
            "--path", "code/ring.py",
            "--description", "Generates test rings",
            "--cycle", "cycle-1",
        )
        assert rc == 0
        assert "Registered" in out
        assert "ring-gen" in out

    def test_register_overwrites(self, research_dir):
        run_manage(research_dir, "build")
        run_manage(
            research_dir, "register",
            "--id", "dup", "--name", "V1", "--type", "function", "--path", "v1.py",
        )
        rc, out, _ = run_manage(
            research_dir, "register",
            "--id", "dup", "--name", "V2", "--type", "script", "--path", "v2.py",
        )
        assert rc == 0
        assert "Registered" in out


class TestCmdArtifacts:
    def test_empty_list(self, research_dir):
        run_manage(research_dir, "build")
        rc, out, _ = run_manage(research_dir, "artifacts")
        assert rc == 0
        assert "No coder artifacts" in out

    def test_lists_registered(self, research_dir):
        run_manage(research_dir, "build")
        run_manage(
            research_dir, "register",
            "--id", "bench-1", "--name", "Benchmark", "--type", "script", "--path", "bench.py",
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
        codebook = research_dir / "CODEBOOK.md"
        assert codebook.exists()
        assert "No artifacts" in codebook.read_text()

    def test_generates_codebook_with_artifacts(self, research_dir):
        run_manage(research_dir, "build")
        run_manage(
            research_dir, "register",
            "--id", "gen-1", "--name", "Generator", "--type", "function",
            "--path", "gen.py", "--description", "Generates data",
        )
        rc, _out, _ = run_manage(research_dir, "codebook")
        assert rc == 0
        codebook = research_dir / "CODEBOOK.md"
        content = codebook.read_text()
        assert "gen-1" in content
        assert "Generator" in content
        assert "Generates data" in content
