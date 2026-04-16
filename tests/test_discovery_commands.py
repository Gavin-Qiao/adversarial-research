"""Tests for the discovery CLI commands: paths, roles, phases, schema."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    """Run manage.py with args; return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-m", "principia.cli.manage", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_paths_json_shape(tmp_path: Path) -> None:
    """paths --json returns schema_version and workspace paths."""
    rc, out, err = _run("--root", str(tmp_path / "principia"), "paths", "--json")
    assert rc == 0, f"paths --json failed: {err}"
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    data = payload["data"]
    for key in ("root", "db", "claims_dir", "context_dir", "progress", "foundations", "config"):
        assert key in data, f"paths --json missing key: {key}"


def test_roles_json_shape(tmp_path: Path) -> None:
    """roles --json returns the list of roles from orchestration.yaml."""
    rc, out, err = _run("--root", str(tmp_path / "principia"), "roles", "--json")
    assert rc == 0, f"roles --json failed: {err}"
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    roles = payload["data"]
    assert isinstance(roles, list)
    assert len(roles) > 0, "expected at least one role"
    names = {r["name"] for r in roles}
    assert "architect" in names
    assert "adversary" in names
    for r in roles:
        assert "name" in r
        assert isinstance(r["name"], str)


def test_phases_json_shape(tmp_path: Path) -> None:
    """phases --json returns the list of phases with their roles."""
    rc, out, err = _run("--root", str(tmp_path / "principia"), "phases", "--json")
    assert rc == 0, f"phases --json failed: {err}"
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    phases = payload["data"]
    assert isinstance(phases, list)
    names = {p["name"] for p in phases}
    assert "debate" in names or "test" in names or "experiment" in names, f"expected known phases, got {names}"
    for p in phases:
        assert "name" in p
        assert "roles" in p
        assert isinstance(p["roles"], list)


def test_schema_json_shape(tmp_path: Path) -> None:
    """schema --json returns the frontmatter value sets."""
    rc, out, err = _run("--root", str(tmp_path / "principia"), "schema", "--json")
    assert rc == 0, f"schema --json failed: {err}"
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    data = payload["data"]
    for key in ("types", "statuses", "maturities", "confidences"):
        assert key in data, f"schema missing key: {key}"
        assert isinstance(data[key], list)
        assert len(data[key]) > 0


def test_validate_json_includes_schema_version(tmp_path: Path) -> None:
    """validate --json wraps payload in schema_version envelope."""
    _rc, out, _err = _run("--root", str(tmp_path / "principia"), "validate", "--json")
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    assert "data" in payload
    assert "valid" in payload["data"]


def test_query_json_includes_schema_version(tmp_path: Path) -> None:
    """query --json wraps payload in schema_version envelope."""
    rc, out, err = _run("--root", str(tmp_path / "principia"), "query", "--json", "SELECT 1 as x")
    assert rc == 0, f"query --json failed: {err}"
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    assert "data" in payload
    assert isinstance(payload["data"], list)


def test_list_json_includes_schema_version(tmp_path: Path) -> None:
    """list --json wraps payload in schema_version envelope."""
    rc, out, err = _run("--root", str(tmp_path / "principia"), "list", "--json")
    assert rc == 0, f"list --json failed: {err}"
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    assert "data" in payload
    assert isinstance(payload["data"], list)


def test_waves_json_includes_schema_version(tmp_path: Path) -> None:
    """waves --json wraps payload in schema_version envelope."""
    rc, out, err = _run("--root", str(tmp_path / "principia"), "waves", "--json")
    assert rc == 0, f"waves --json failed: {err}"
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    assert "data" in payload


def test_dispatch_log_json_includes_schema_version(tmp_path: Path) -> None:
    """dispatch-log --json wraps payload in schema_version envelope."""
    rc, out, err = _run("--root", str(tmp_path / "principia"), "dispatch-log", "--json")
    assert rc == 0, f"dispatch-log --json failed: {err}"
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    assert "data" in payload


def test_next_json_includes_schema_version(tmp_path: Path) -> None:
    """next output is wrapped in schema_version envelope."""
    root = tmp_path / "principia"
    root.mkdir()
    (root / "claims").mkdir()
    (root / "context").mkdir()
    (root / "context" / "assumptions").mkdir()
    # Build empty workspace first
    _run("--root", str(root), "build")
    # `next` without a claim path may still emit something; accept any exit code
    _rc, out, _err = _run("--root", str(root), "next")
    if out.strip():
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload


def test_investigate_next_json_includes_schema_version(tmp_path: Path) -> None:
    """investigate-next output is wrapped in schema_version envelope."""
    root = tmp_path / "principia"
    root.mkdir()
    (root / "claims").mkdir()
    (root / "context").mkdir()
    (root / "context" / "assumptions").mkdir()
    _run("--root", str(root), "build")
    _rc, out, _err = _run("--root", str(root), "investigate-next")
    if out.strip():
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload


def test_dashboard_json_includes_schema_version(tmp_path: Path) -> None:
    """dashboard output is wrapped in schema_version envelope."""
    root = tmp_path / "principia"
    root.mkdir()
    (root / "claims").mkdir()
    (root / "context").mkdir()
    (root / "context" / "assumptions").mkdir()
    _run("--root", str(root), "build")
    _rc, out, _err = _run("--root", str(root), "dashboard")
    if out.strip():
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert "data" in payload
