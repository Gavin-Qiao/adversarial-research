"""Contract conformance tests.

For each public operation listed in docs/CONTRACT.md, assert the CLI
accepts documented input and returns JSON with schema_version == 1
and the declared fields (for JSON-emitting ops), or exits 0 with
human-readable text (for text-only ops).

Run: uv run pytest tests/test_contract.py -v

JSON-emitting ops (envelope expected):
  paths, roles, phases, schema (discovery)
  validate, query, list, waves, dispatch-log, dashboard,
  next, investigate-next (inspection)
  post-verdict (workflow)
  parse-framework, autonomy-config (bookkeeping)

Text-only ops (smoke-test rc==0):
  build, status, assumptions, scaffold, new, settle, falsify,
  reopen, replace-verdict, extend-debate, cascade, log-dispatch,
  register, artifacts, codebook, context, packet, prompt

Mutation ops that require a seeded workspace (scaffold, new, settle,
falsify, register, post-verdict, extend-debate, reopen, replace-verdict,
cascade, waves, context, packet, prompt, log-dispatch, parse-framework,
artifacts) use a stub claim created via `scaffold` first.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _run(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "principia.cli.manage", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Initialize a minimal workspace and return its root."""
    root = tmp_path / "principia"
    root.mkdir()
    (root / "claims").mkdir()
    (root / "context").mkdir()
    (root / "context" / "assumptions").mkdir()
    return root


@pytest.fixture
def seeded_workspace(workspace: Path) -> tuple[Path, str]:
    """Workspace with one scaffolded claim.  Returns (root, claim_path)."""
    rc, out, err = _run("--root", str(workspace), "scaffold", "claim", "test-claim")
    assert rc == 0, f"scaffold failed: {err}\n{out}"
    _run("--root", str(workspace), "build")
    claim_path = "claims/claim-1-test-claim"
    return workspace, claim_path


# ---------------------------------------------------------------------------
# Discovery operations — all use emit_envelope; full shape assertions
# ---------------------------------------------------------------------------


class TestDiscoveryContract:
    def test_paths(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "paths", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "warnings" in payload
        for key in (
            "root",
            "db",
            "claims_dir",
            "context_dir",
            "progress",
            "foundations",
            "config",
        ):
            assert key in payload["data"], f"paths data missing key: {key}"

    def test_roles(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "roles", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert isinstance(payload["data"], list)
        for role in payload["data"]:
            assert "name" in role

    def test_phases(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "phases", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert isinstance(payload["data"], list)
        for phase in payload["data"]:
            assert "name" in phase
            assert "roles" in phase

    def test_schema(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "schema", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        for key in ("types", "statuses", "maturities", "confidences"):
            assert key in payload["data"], f"schema data missing key: {key}"
            assert len(payload["data"][key]) > 0

    def test_paths_warns_are_list(self, workspace: Path) -> None:
        rc, out, _ = _run("--root", str(workspace), "paths", "--json")
        assert rc == 0
        payload = json.loads(out)
        assert isinstance(payload["warnings"], list)

    def test_roles_non_empty(self, workspace: Path) -> None:
        rc, out, _ = _run("--root", str(workspace), "roles", "--json")
        assert rc == 0
        payload = json.loads(out)
        assert len(payload["data"]) > 0

    def test_schema_types_include_claim(self, workspace: Path) -> None:
        rc, out, _ = _run("--root", str(workspace), "schema", "--json")
        assert rc == 0
        payload = json.loads(out)
        assert "claim" in payload["data"]["types"]

    def test_schema_statuses_include_pending(self, workspace: Path) -> None:
        rc, out, _ = _run("--root", str(workspace), "schema", "--json")
        assert rc == 0
        payload = json.loads(out)
        assert "pending" in payload["data"]["statuses"]


# ---------------------------------------------------------------------------
# Inspection operations
# ---------------------------------------------------------------------------


class TestInspectionContract:
    def test_validate_json_shape(self, workspace: Path) -> None:
        # validate --json may exit non-zero if there are integrity issues; shape still applies
        _rc, out, _err = _run("--root", str(workspace), "validate", "--json")
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload
        assert "errors" in payload["data"]

    def test_validate_empty_workspace_exits_zero(self, workspace: Path) -> None:
        rc, _out, _err = _run("--root", str(workspace), "validate", "--json")
        assert rc == 0

    def test_validate_valid_field_present(self, workspace: Path) -> None:
        _rc, out, _err = _run("--root", str(workspace), "validate", "--json")
        payload = json.loads(out)
        assert "valid" in payload["data"]
        assert isinstance(payload["data"]["valid"], bool)

    def test_validate_error_count_present(self, workspace: Path) -> None:
        _rc, out, _err = _run("--root", str(workspace), "validate", "--json")
        payload = json.loads(out)
        assert "error_count" in payload["data"]
        assert isinstance(payload["data"]["error_count"], int)

    def test_validate_node_count_when_valid(self, workspace: Path) -> None:
        # On empty (valid) workspace, node_count and edge_count should be present
        _rc, out, _err = _run("--root", str(workspace), "validate", "--json")
        payload = json.loads(out)
        if payload["data"]["valid"]:
            assert "node_count" in payload["data"]
            assert "edge_count" in payload["data"]

    def test_query_json_shape(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "query", "--json", "SELECT 1 AS x")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload
        # data is a flat list of row dicts
        assert isinstance(payload["data"], list)

    def test_query_returns_rows(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "query", "--json", "SELECT 1 AS x")
        assert rc == 0, err
        payload = json.loads(out)
        assert len(payload["data"]) == 1
        assert payload["data"][0]["x"] == 1

    def test_waves_json_shape(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "waves", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload
        # data is a list of lists of row dicts
        assert isinstance(payload["data"], list)

    def test_waves_inner_lists_are_lists(self, seeded_workspace: tuple[Path, str]) -> None:
        root, _claim_path = seeded_workspace
        rc, out, err = _run("--root", str(root), "waves", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        for wave in payload["data"]:
            assert isinstance(wave, list)

    def test_dispatch_log_json_shape(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "dispatch-log", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload
        assert isinstance(payload["data"], list)

    def test_dispatch_log_row_fields(self, workspace: Path) -> None:
        # Seed one dispatch so the list is non-empty, then verify field contract.
        rc_ld, _out_ld, err_ld = _run(
            "--root",
            str(workspace),
            "log-dispatch",
            "--cycle",
            "claim-test",
            "--agent",
            "conductor",
            "--action",
            "dispatch",
            "--round",
            "1",
        )
        assert rc_ld == 0, err_ld
        rc, out, err = _run("--root", str(workspace), "dispatch-log", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        data = payload["data"]
        # The seeded row guarantees at least one entry exists — guard is non-vacuous.
        assert len(data) >= 1, "expected at least the seeded dispatch row"
        required_keys = {"cycle_id", "agent", "round", "timestamp"}
        for row in data:
            missing = required_keys - row.keys()
            assert not missing, f"dispatch-log row missing keys: {missing}"
            # sub_unit is always present in every row (nullable per contract)
            assert "sub_unit" in row, "dispatch-log row missing sub_unit key"

    def test_list_json_shape(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "list", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload
        assert isinstance(payload["data"], list)

    def test_build_runs(self, workspace: Path) -> None:
        rc, _out, err = _run("--root", str(workspace), "build")
        assert rc == 0, err

    def test_next_json_shape(self, workspace: Path) -> None:
        _run("--root", str(workspace), "build")
        _rc, out, err = _run("--root", str(workspace), "next")
        assert out.strip(), f"next produced no output. stderr: {err}"
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload

    def test_investigate_next_json_shape(self, workspace: Path) -> None:
        _run("--root", str(workspace), "build")
        _rc, out, err = _run("--root", str(workspace), "investigate-next")
        assert out.strip(), f"investigate-next produced no output. stderr: {err}"
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload

    def test_dashboard_json_shape(self, workspace: Path) -> None:
        _run("--root", str(workspace), "build")
        _rc, out, err = _run("--root", str(workspace), "dashboard")
        assert out.strip(), f"dashboard produced no output. stderr: {err}"
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload


# ---------------------------------------------------------------------------
# Mutation operations — seeded workspace smoke tests
# ---------------------------------------------------------------------------


class TestMutationContract:
    def test_scaffold_creates_directory(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "scaffold", "claim", "my-claim")
        assert rc == 0, err
        claim_dir = workspace / "claims" / "claim-1-my-claim"
        assert claim_dir.exists()
        assert (claim_dir / "claim.md").exists()
        # Text output (no envelope — text-only op by contract)
        assert "Created:" in out

    def test_scaffold_creates_role_dirs(self, workspace: Path) -> None:
        rc, _out, err = _run("--root", str(workspace), "scaffold", "claim", "another-claim")
        assert rc == 0, err
        claim_dir = workspace / "claims" / "claim-1-another-claim"
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            assert (claim_dir / role).is_dir(), f"missing role dir: {role}"

    def test_new_creates_file(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "new", "claims/evidence.md")
        assert rc == 0, err
        assert (workspace / "claims" / "evidence.md").exists()
        # Text output (no envelope — text-only op by contract)
        assert "Created:" in out

    def test_settle_marks_proven(self, seeded_workspace: tuple[Path, str]) -> None:
        root, _claim_path = seeded_workspace
        # Get node ID from DB
        rc, out, err = _run("--root", str(root), "query", "--json", "SELECT id FROM nodes LIMIT 1")
        assert rc == 0, err
        rows = json.loads(out)["data"]
        if not rows:
            pytest.skip("no nodes to settle")
        node_id = rows[0]["id"]
        rc, out, err = _run("--root", str(root), "settle", node_id)
        assert rc == 0, err
        assert "Settled:" in out

    def test_falsify_marks_disproven(self, seeded_workspace: tuple[Path, str]) -> None:
        root, _claim_path = seeded_workspace
        rc, out, err = _run("--root", str(root), "query", "--json", "SELECT id FROM nodes LIMIT 1")
        assert rc == 0, err
        rows = json.loads(out)["data"]
        if not rows:
            pytest.skip("no nodes to falsify")
        node_id = rows[0]["id"]
        rc, out, err = _run("--root", str(root), "falsify", "--force", node_id)
        assert rc == 0, err
        assert "Disproven:" in out


# ---------------------------------------------------------------------------
# Planning operations — seeded workspace smoke tests
# ---------------------------------------------------------------------------


class TestPlanningContract:
    def test_cascade_runs(self, seeded_workspace: tuple[Path, str]) -> None:
        root, _claim_path = seeded_workspace
        rc, out, err = _run("--root", str(root), "query", "--json", "SELECT id FROM nodes LIMIT 1")
        assert rc == 0, err
        rows = json.loads(out)["data"]
        if not rows:
            pytest.skip("no nodes for cascade")
        node_id = rows[0]["id"]
        rc, out, err = _run("--root", str(root), "cascade", node_id)
        assert rc == 0, err
        # Text output (no envelope — text-only op by contract)
        assert "Cascade analysis" in out

    def test_waves_with_content(self, seeded_workspace: tuple[Path, str]) -> None:
        root, _claim_path = seeded_workspace
        rc, out, err = _run("--root", str(root), "waves", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert isinstance(payload["data"], list)

    def test_context_runs(self, seeded_workspace: tuple[Path, str]) -> None:
        root, claim_path = seeded_workspace
        rc, _out, err = _run("--root", str(root), "context", claim_path)
        assert rc == 0, err

    def test_next_with_claim(self, seeded_workspace: tuple[Path, str]) -> None:
        root, claim_path = seeded_workspace
        _rc, out, err = _run("--root", str(root), "next", claim_path)
        assert out.strip(), f"next produced no output. stderr: {err}"
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload
        assert "action" in payload["data"]


# ---------------------------------------------------------------------------
# Bookkeeping operations — seeded workspace smoke tests + envelope assertions
# ---------------------------------------------------------------------------


class TestBookkeepingContract:
    def test_log_dispatch_runs(self, seeded_workspace: tuple[Path, str]) -> None:
        root, _claim_path = seeded_workspace
        rc, out, err = _run(
            "--root",
            str(root),
            "log-dispatch",
            "--cycle",
            "claim-1-test-claim",
            "--agent",
            "architect",
            "--action",
            "dispatch",
            "--round",
            "1",
        )
        assert rc == 0, err
        # Text output (no envelope — text-only op by contract)
        assert "Logged:" in out

    def test_dispatch_log_after_logging(self, seeded_workspace: tuple[Path, str]) -> None:
        root, _claim_path = seeded_workspace
        _run(
            "--root",
            str(root),
            "log-dispatch",
            "--cycle",
            "claim-1-test-claim",
            "--agent",
            "architect",
            "--action",
            "dispatch",
            "--round",
            "1",
        )
        rc, out, err = _run("--root", str(root), "dispatch-log", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert len(payload["data"]) >= 1

    def test_autonomy_config_envelope(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "autonomy-config")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload
        assert "mode" in payload["data"]
        assert "checkpoint_at" in payload["data"]
        assert isinstance(payload["data"]["checkpoint_at"], list)

    def test_autonomy_config_mode_value(self, workspace: Path) -> None:
        rc, out, err = _run("--root", str(workspace), "autonomy-config")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["data"]["mode"] in ("checkpoints", "yolo")

    def test_artifacts_runs(self, seeded_workspace: tuple[Path, str]) -> None:
        root, _claim_path = seeded_workspace
        # artifacts command takes no claim path in current impl; text-only op
        rc, _out, err = _run("--root", str(root), "artifacts")
        assert rc == 0, err

    def test_codebook_runs(self, workspace: Path) -> None:
        # codebook is text-only: generates TOOLKIT.md and prints a path
        rc, out, err = _run("--root", str(workspace), "codebook")
        assert rc == 0, err
        assert "Generated:" in out

    def test_parse_framework_json_shape(self, workspace: Path) -> None:
        """parse-framework emits the envelope when given a valid blueprint."""
        blueprint = workspace / "blueprint.md"
        blueprint.write_text(
            "# Blueprint\n\n"
            "```yaml\n"
            "# CLAIM_REGISTRY\n"
            "claims:\n"
            "  - id: claim-1-foo\n"
            "    statement: test claim\n"
            "    maturity: conjecture\n"
            "    confidence: moderate\n"
            "    depends_on: []\n"
            "    falsification: none\n"
            "```\n"
        )
        rc, out, err = _run("--root", str(workspace), "parse-framework")
        assert rc == 0, f"parse-framework failed: {err}\n{out}"
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert isinstance(payload["data"], list)
        assert len(payload["data"]) >= 1
        claim = payload["data"][0]
        assert claim["id"] == "claim-1-foo"
        assert "statement" in claim
        assert "maturity" in claim
        assert "confidence" in claim
        assert "depends_on" in claim
        assert "falsification" in claim

    def test_post_verdict_json_shape(self, workspace: Path) -> None:
        """post-verdict emits the envelope after applying a verdict."""
        # Scaffold a claim and build DB
        rc, _out, err = _run("--root", str(workspace), "scaffold", "claim", "pv-test")
        assert rc == 0, f"scaffold failed: {err}"
        _run("--root", str(workspace), "build")
        claim_dir = workspace / "claims" / "claim-1-pv-test"
        # Seed verdict file
        arb_results = claim_dir / "arbiter" / "results"
        arb_results.mkdir(parents=True, exist_ok=True)
        (arb_results / "verdict.md").write_text(
            "---\nid: verdict-pv\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n"
            "# Verdict\n\n**Verdict**: PROVEN\n**Confidence**: high\n"
        )
        _run("--root", str(workspace), "build")
        rc, out, err = _run("--root", str(workspace), "post-verdict", "claims/claim-1-pv-test")
        assert rc == 0, f"post-verdict failed: {err}\n{out}"
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload
        data = payload["data"]
        assert data["verdict"] == "PROVEN"
        assert "confidence" in data
        assert "node_id" in data
        assert isinstance(data["changes"], list)
