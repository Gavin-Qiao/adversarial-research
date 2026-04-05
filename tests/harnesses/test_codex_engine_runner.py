import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from principia.api.engine import PrincipiaEngine


def test_engine_runner_build_command(tmp_path):
    (tmp_path / "claims").mkdir(parents=True)
    (tmp_path / "context" / "assumptions").mkdir(parents=True)
    (tmp_path / ".db").mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "harnesses/codex/scripts/engine_runner.py",
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
            "harnesses/codex/scripts/engine_runner.py",
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

    for command in ("build", "dashboard", "validate", "results"):
        method = getattr(engine, command, None)
        assert callable(method), f"PrincipiaEngine is missing {command}()"


def test_engine_runner_uses_uniform_engine_dispatch():
    runner_path = Path("harnesses/codex/scripts/engine_runner.py")
    runner_text = runner_path.read_text(encoding="utf-8")

    assert "payload = getattr(engine, args.command)()" in runner_text


def test_engine_runner_prefers_repo_local_principia_over_pythonpath(tmp_path):
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
            "harnesses/codex/scripts/engine_runner.py",
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


def test_engine_runner_errors_cleanly_for_standalone_harness_copy(tmp_path):
    standalone_root = tmp_path / "standalone"
    harness_root = standalone_root / "harnesses" / "codex"
    shutil.copytree(Path("harnesses/codex"), harness_root)

    design_root = standalone_root / "design"
    (design_root / "claims").mkdir(parents=True)
    (design_root / "context" / "assumptions").mkdir(parents=True)
    (design_root / ".db").mkdir()

    result = subprocess.run(
        [
            sys.executable,
            str(harness_root / "scripts" / "engine_runner.py"),
            "--root",
            str(design_root),
            "build",
        ],
        cwd=standalone_root,
        capture_output=True,
        text=True,
        check=False,
        env={},
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "full Principia repository checkout" in result.stderr
    assert "harnesses/codex" in result.stderr
