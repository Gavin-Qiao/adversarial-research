import json
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

    assert 'payload = getattr(engine, args.command)()' in runner_text
