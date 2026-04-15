import json
import os
import subprocess
import sys
from pathlib import Path

import principia.cli.codex_runner as codex_runner
from principia.api.engine import PrincipiaEngine


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

    for command in ("build", "dashboard", "next", "packet", "prompt", "dispatch_log", "patch_status", "validate", "results"):
        method = getattr(engine, command, None)
        assert callable(method), f"PrincipiaEngine is missing {command}()"


def test_engine_runner_exposes_extended_codex_commands():
    runner_path = Path("principia/cli/codex_runner.py")
    runner_text = runner_path.read_text(encoding="utf-8")

    assert '"next"' in runner_text
    assert '"packet"' in runner_text
    assert '"prompt"' in runner_text
    assert '"dispatch-log"' in runner_text
    assert '"patch-status"' in runner_text


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
