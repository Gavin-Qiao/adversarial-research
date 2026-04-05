from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_manage_entrypoint_delegates_to_package_main(monkeypatch) -> None:
    called: dict[str, bool] = {}

    def fake_main() -> None:
        called["ok"] = True

    monkeypatch.setattr("principia.cli.manage.main", fake_main)

    import scripts.manage as manage

    manage.main()

    assert called["ok"] is True


def test_package_manage_module_runs_help() -> None:
    project_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "principia.cli.manage", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Principia repository-centered design management system" in result.stdout
    assert "Path to Principia workspace root directory" in result.stdout


def test_manage_wrapper_prefers_local_package_over_pythonpath(tmp_path: Path) -> None:
    fake_package = tmp_path / "fake"
    fake_cli = fake_package / "principia" / "cli"
    fake_cli.mkdir(parents=True)
    (fake_package / "principia" / "__init__.py").write_text("", encoding="utf-8")
    (fake_cli / "__init__.py").write_text("", encoding="utf-8")
    (fake_cli / "manage.py").write_text(
        "def main() -> None:\n    print('EXTERNAL PRINCIPIA')\n",
        encoding="utf-8",
    )

    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(fake_package)
    result = subprocess.run(
        [sys.executable, "scripts/manage.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "Principia repository-centered design management system" in result.stdout
    assert "EXTERNAL PRINCIPIA" not in result.stdout
