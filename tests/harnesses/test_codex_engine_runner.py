import json
import os
import subprocess
import sys
from pathlib import Path

import principia.cli.codex_runner as codex_runner
from principia.api.engine import PrincipiaEngine


def _run_codex_runner(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "principia.cli.codex_runner",
            "--root",
            str(root),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _make_claim_workspace(
    root: Path,
    *,
    claim_name: str = "claim-1-test",
    claim_id: str = "h1-test",
    status: str = "pending",
    extra_frontmatter: str = "",
    body: str = "Readable summary.\n",
) -> Path:
    claim_dir = root / "claims" / claim_name
    claim_dir.mkdir(parents=True)
    (root / "context" / "assumptions").mkdir(parents=True, exist_ok=True)
    (root / ".db").mkdir(exist_ok=True)
    if (root / ".north-star.md").exists() and "north_star_version:" not in extra_frontmatter:
        from principia.core.orchestration import compute_north_star_version

        version = compute_north_star_version(root)
        if version:
            extra_frontmatter += f"north_star_version: {version}\n"
    (claim_dir / "claim.md").write_text(
        "---\n"
        f"id: {claim_id}\n"
        "type: claim\n"
        f"status: {status}\n"
        "date: 2026-01-01\n"
        f"{extra_frontmatter}"
        "---\n\n"
        "# Test claim\n\n"
        f"{body}",
        encoding="utf-8",
    )
    for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
        (claim_dir / role).mkdir(exist_ok=True)
    return claim_dir


def test_engine_runner_build_command(tmp_path):
    (tmp_path / "claims").mkdir(parents=True)
    (tmp_path / "context" / "assumptions").mkdir(parents=True)
    (tmp_path / ".db").mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "principia.cli.codex_runner",
            "--root",
            str(tmp_path),
            "build",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["node_count"] == 0


def test_engine_runner_validate_command_exits_nonzero_on_invalid_workspace(tmp_path):
    claim_dir = tmp_path / "claims" / "claim-1-invalid"
    claim_dir.mkdir(parents=True)
    (tmp_path / "context" / "assumptions").mkdir(parents=True)
    (tmp_path / ".db").mkdir()
    (claim_dir / "claim.md").write_text(
        "---\nstatus: broken\ndate: 2026-01-01\n---\n\n# Invalid claim\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "principia.cli.codex_runner",
            "--root",
            str(tmp_path),
            "validate",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert payload["error_count"] > 0


def test_engine_exposes_all_runner_commands(tmp_path):
    (tmp_path / "claims").mkdir(parents=True)
    (tmp_path / "context" / "assumptions").mkdir(parents=True)
    (tmp_path / ".db").mkdir()

    engine = PrincipiaEngine(root=tmp_path)

    commands = (
        "build",
        "dashboard",
        "next",
        "packet",
        "prompt",
        "dispatch_log",
        "patch_status",
        "validate",
        "results",
        "visualize",
    )
    for command in commands:
        method = getattr(engine, command, None)
        assert callable(method), f"PrincipiaEngine is missing {command}()"


def test_engine_runner_exposes_extended_codex_commands():
    runner_path = Path("principia/cli/codex_runner.py")
    runner_text = runner_path.read_text(encoding="utf-8")

    assert '"dashboard"' in runner_text
    assert '"next"' in runner_text
    assert '"packet"' in runner_text
    assert '"prompt"' in runner_text
    assert '"dispatch-log"' in runner_text
    assert '"patch-status"' in runner_text
    assert '"results"' in runner_text
    assert '"visualize"' in runner_text
    assert "Codex-friendly Principia control plane." in runner_text
    assert "Common flow: dashboard -> next." in runner_text
    assert "patch-status" in runner_text


def test_codex_runner_module_exposes_main():
    assert callable(codex_runner.main)


def test_codex_runner_build_uses_repository_principia_package(tmp_path):
    fake_package = tmp_path / "fake"
    fake_api = fake_package / "principia" / "api"
    fake_api.mkdir(parents=True)
    (fake_package / "principia" / "__init__.py").write_text("", encoding="utf-8")
    (fake_api / "__init__.py").write_text("", encoding="utf-8")
    (fake_api / "engine.py").write_text(
        "class PrincipiaEngine:\n"
        "    def __init__(self, root):\n"
        "        self.root = root\n"
        "    def build(self):\n"
        "        return {'node_count': 999, 'edge_count': 111}\n",
        encoding="utf-8",
    )

    design_root = tmp_path / "design"
    (design_root / "claims").mkdir(parents=True)
    (design_root / "context" / "assumptions").mkdir(parents=True)
    (design_root / ".db").mkdir()

    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(fake_package), str(project_root)])
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "principia.cli.codex_runner",
            "--root",
            str(design_root),
            "build",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["node_count"] == 0
    assert payload["edge_count"] == 0


def test_engine_runner_next_command_accepts_path_argument(tmp_path):
    claim_dir = tmp_path / "claims" / "claim-1-test"
    claim_dir.mkdir(parents=True)
    (tmp_path / "context" / "assumptions").mkdir(parents=True)
    (tmp_path / ".db").mkdir()
    (claim_dir / "claim.md").write_text(
        "---\nid: h1-test\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test claim\n",
        encoding="utf-8",
    )
    for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
        (claim_dir / role).mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "principia.cli.codex_runner",
            "--root",
            str(tmp_path),
            "next",
            "--path",
            "claims/claim-1-test",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["action"] == "dispatch_architect"
    assert payload["packet_path"].endswith("architect/round-1/packet.md")


def test_engine_runner_next_command_follows_operator_guidance_for_waiting_handoff(tmp_path):
    (tmp_path / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
    (tmp_path / ".context.md").write_text("# Context\n", encoding="utf-8")
    from principia.core.orchestration import compute_north_star_version

    version = compute_north_star_version(tmp_path)
    _make_claim_workspace(tmp_path, extra_frontmatter=f"north_star_version: {version}\n")

    prompt_result = _run_codex_runner(tmp_path, "prompt", "--path", "claims/claim-1-test")
    assert prompt_result.returncode == 0

    result = _run_codex_runner(tmp_path, "next")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "guided_next"
    assert payload["active_claim"] == "claims/claim-1-test"
    assert payload["recommended_action"]["command"] == "dispatch-log"
    assert payload["recommended_action"]["cycle"] == "claim-1-test"


def test_engine_runner_prompt_command_writes_prompt_artifact(tmp_path):
    claim_dir = tmp_path / "claims" / "claim-1-test"
    claim_dir.mkdir(parents=True)
    (tmp_path / "context" / "assumptions").mkdir(parents=True)
    (tmp_path / ".db").mkdir()
    (claim_dir / "claim.md").write_text(
        "---\nid: h1-test\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test claim\n",
        encoding="utf-8",
    )
    for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
        (claim_dir / role).mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "principia.cli.codex_runner",
            "--root",
            str(tmp_path),
            "prompt",
            "--path",
            "claims/claim-1-test",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["relative_path"].endswith("architect/round-1/prompt.md")
    assert (claim_dir / "architect" / "round-1" / "prompt.md").exists()


def test_engine_runner_dashboard_command_returns_structured_payload(tmp_path):
    (tmp_path / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
    (tmp_path / ".context.md").write_text("# Context\n", encoding="utf-8")
    _make_claim_workspace(tmp_path)

    result = _run_codex_runner(tmp_path, "dashboard")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert set(payload.keys()) >= {
        "phase",
        "action",
        "claims",
        "dispatch_overview",
        "patch_status",
        "operator_guidance",
        "init",
    }
    assert payload["dispatch_overview"]["claim_count"] == 0
    assert "current_version" in payload["patch_status"]
    assert payload["init"]["repo_scan"]["complete"] is True
    assert payload["init"]["north_star_interview"]["complete"] is True
    assert payload["operator_guidance"]["recommended_action"]["command"] == "next"


def test_engine_runner_dashboard_keeps_init_blocked_until_repo_scan_is_written(tmp_path):
    (tmp_path / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
    (tmp_path / "claims").mkdir(parents=True)
    (tmp_path / "context" / "assumptions").mkdir(parents=True)
    (tmp_path / ".db").mkdir()

    result = _run_codex_runner(tmp_path, "dashboard")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["init"]["north_star_locked"] is True
    assert payload["init"]["repo_scan"]["complete"] is False
    assert payload["operator_guidance"]["recommended_action"]["command"] == "principia:init"
    assert "principia/.context.md" in payload["operator_guidance"]["summary"]


def test_engine_runner_dispatch_log_command_returns_logged_rows(tmp_path):
    _make_claim_workspace(tmp_path)
    prompt_result = _run_codex_runner(tmp_path, "prompt", "--path", "claims/claim-1-test")

    assert prompt_result.returncode == 0
    result = _run_codex_runner(tmp_path, "dispatch-log")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert len(payload) == 1
    assert payload[0]["cycle_id"] == "claim-1-test"
    assert payload[0]["agent"] == "architect"
    assert payload[0]["action"] == "dispatch"


def test_engine_runner_patch_status_command_reports_alignment(tmp_path):
    (tmp_path / ".north-star.md").write_text("# Locked principle\n", encoding="utf-8")
    _make_claim_workspace(tmp_path, extra_frontmatter="north_star_version: old-version\n")

    result = _run_codex_runner(tmp_path, "patch-status")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["stale_claim_count"] == 1
    assert payload["needs_review_count"] == 1
    assert payload["needs_review"][0]["id"] == "h1-test"


def test_engine_runner_results_command_writes_results_report(tmp_path):
    claim_dir = _make_claim_workspace(tmp_path, status="proven")
    (claim_dir / "arbiter" / "results").mkdir(parents=True)
    (claim_dir / "arbiter" / "results" / "verdict.md").write_text(
        "---\n"
        "id: v1\n"
        "type: verdict\n"
        "status: active\n"
        "date: 2026-01-01\n"
        "---\n\n"
        "**Verdict**: PROVEN\n"
        "**Confidence**: high\n",
        encoding="utf-8",
    )
    (claim_dir / ".post_verdict_done").write_text("2026-01-02", encoding="utf-8")

    result = _run_codex_runner(tmp_path, "results")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["exists"] is True
    assert payload["message"].startswith("Generated:")
    assert Path(payload["results_path"]).exists()
    assert payload["results_summary"]["claim_count"] == 1
    assert payload["results_summary"]["verdict_counts"]["PROVEN"] == 1
    assert payload["results_summary"]["latest_verdict"]["verdict"] == "PROVEN"
    assert payload["results_summary"]["topline"]
    assert payload["results_summary"]["open_claim_count"] == 0
    assert payload["results_summary"]["confidence_counts"]["high"] == 1
    assert isinstance(payload["results_summary"]["limitation_preview"], list)
    report_text = Path(payload["results_path"]).read_text(encoding="utf-8")
    assert "## Executive Summary" in report_text
    assert "### Test" in report_text or "### H1 Test" in report_text or "### claim-1-test" in report_text


def test_engine_runner_help_describes_operator_flow(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "principia.cli.codex_runner",
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Codex-friendly Principia control plane." in result.stdout
    assert "dashboard" in result.stdout
    assert "results" in result.stdout
    assert "generated workflow" in result.stdout
    assert "workspace" in result.stdout
    assert "patch-status" in result.stdout


def test_engine_runner_visualize_command_writes_explorer(tmp_path):
    claim_dir = tmp_path / "claims" / "claim-1-test"
    claim_dir.mkdir(parents=True)
    (tmp_path / "context" / "assumptions").mkdir(parents=True)
    (tmp_path / ".db").mkdir()
    (tmp_path / ".north-star.md").write_text("# Locked\n", encoding="utf-8")
    (tmp_path / ".context.md").write_text("# Context\n", encoding="utf-8")
    (claim_dir / "claim.md").write_text(
        "---\nid: h1-test\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test claim\n\nReadable summary.\n",
        encoding="utf-8",
    )
    for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
        (claim_dir / role).mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "principia.cli.codex_runner",
            "--root",
            str(tmp_path),
            "visualize",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["claim_count"] == 1
    assert payload["phase"] in {"understand", "divide", "test"}
    assert Path(payload["html_path"]).exists()
    assert Path(payload["json_path"]).exists()
