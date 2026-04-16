"""Contract wrapper tests: run `pp <op>` for every op declared in the
wrapper case-statement; assert each exits with code 0 or emits valid
JSON with schema_version 1 (for read-only ops against a fresh workspace).

These tests drift-check the wrapper against the core CLI.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
WRAPPER = REPO_ROOT / "plugins" / "claude" / "scripts" / "pp"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "principia"
    root.mkdir()
    (root / "claims").mkdir()
    (root / "context").mkdir()
    (root / "context" / "assumptions").mkdir()
    return root


def _pp(workspace: Path, *args: str) -> tuple[int, str, str]:
    env = {**os.environ, "PRINCIPIA_ROOT": str(workspace)}
    # Run from a parent of the workspace so pp's cwd doesn't shadow it.
    result = subprocess.run(
        [str(WRAPPER), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


class TestDiscoveryOps:
    def test_paths(self, workspace: Path) -> None:
        rc, out, err = _pp(workspace, "paths", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1

    def test_roles(self, workspace: Path) -> None:
        rc, out, err = _pp(workspace, "roles", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1

    def test_phases(self, workspace: Path) -> None:
        rc, out, err = _pp(workspace, "phases", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1

    def test_schema(self, workspace: Path) -> None:
        rc, out, err = _pp(workspace, "schema", "--json")
        assert rc == 0, err
        payload = json.loads(out)
        assert payload["schema_version"] == 1


class TestBasicOps:
    def test_build(self, workspace: Path) -> None:
        rc, _out, err = _pp(workspace, "build")
        assert rc == 0, err

    def test_validate(self, workspace: Path) -> None:
        _rc, out, _err = _pp(workspace, "validate", "--json")
        # validate may non-zero on an empty workspace; shape is the assertion
        payload = json.loads(out)
        assert payload["schema_version"] == 1


class TestUnknownOp:
    def test_unknown_op_fails_cleanly(self, workspace: Path) -> None:
        rc, _out, err = _pp(workspace, "nonexistent-operation")
        assert rc == 2
        assert "unknown operation" in err.lower()
