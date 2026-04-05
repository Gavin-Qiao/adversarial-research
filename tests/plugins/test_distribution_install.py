import json
import os
import subprocess
import sys
from pathlib import Path


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _build_and_install_wheel(project_root: Path, tmp_path: Path) -> Path:
    dist_dir = tmp_path / "dist"
    build_result = subprocess.run(
        [
            "uv",
            "build",
            "--wheel",
            "--out-dir",
            str(dist_dir),
            "--python",
            sys.executable,
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build_result.returncode == 0, build_result.stderr

    wheel_path = next(dist_dir.glob("principia-*.whl"))
    venv_dir = tmp_path / "venv"
    venv_result = subprocess.run(
        [
            "uv",
            "venv",
            "--python",
            sys.executable,
            str(venv_dir),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert venv_result.returncode == 0, venv_result.stderr

    python_path = _venv_python(venv_dir)
    install_result = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python_path),
            str(wheel_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install_result.returncode == 0, install_result.stderr
    return python_path


def test_built_wheel_installs_and_runs_packaged_runtime(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    python_path = _build_and_install_wheel(project_root, tmp_path)

    design_root = tmp_path / "design"
    claim_dir = design_root / "claims" / "claim-1-test"
    claim_dir.mkdir(parents=True)
    (design_root / "context" / "assumptions").mkdir(parents=True)
    (design_root / ".db").mkdir()
    (claim_dir / "claim.md").write_text(
        "---\nid: h1-test\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Test claim\n",
        encoding="utf-8",
    )

    build_result = subprocess.run(
        [
            str(python_path),
            "-m",
            "principia.cli.codex_runner",
            "--root",
            str(design_root),
            "build",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build_result.returncode == 0, build_result.stderr
    payload = json.loads(build_result.stdout)
    assert payload["node_count"] == 1

    code = """
from argparse import Namespace
from pathlib import Path

from principia.core import config as cfg
from principia.core.commands import cmd_prompt
from principia.core.orchestration import load_config

design_root = Path.cwd() / "design"
claim_dir = design_root / "claims" / "claim-1-test"

cfg.init_paths(design_root)
cmd_prompt(Namespace(path="claims/claim-1-test"))
roles = [r.get("name") for r in load_config(cfg.DEFAULT_ORCH_CONFIG).get("roles", []) if isinstance(r, dict)]
prompt = (claim_dir / "architect" / "round-1" / "prompt.md").read_text(encoding="utf-8")

assert cfg.DEFAULT_ORCH_CONFIG.exists()
assert {"architect", "adversary", "experimenter", "arbiter"} <= set(roles)
assert "Do NOT attempt to read files from the codebase" in prompt
assert (Path(__import__("principia").__file__).resolve().parent / "config" / "protocol.md").exists()
print("OK")
"""
    prompt_result = subprocess.run(
        [str(python_path), "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert prompt_result.returncode == 0, prompt_result.stderr
    assert "OK" in prompt_result.stdout
