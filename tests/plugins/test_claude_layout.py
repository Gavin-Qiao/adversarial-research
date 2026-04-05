import json
from pathlib import Path

import tomllib


def _assert_tree_parity(bundle_dir: Path, source_dir: Path) -> None:
    bundle_files = sorted(path.relative_to(bundle_dir) for path in bundle_dir.rglob("*") if path.is_file())
    source_files = sorted(path.relative_to(source_dir) for path in source_dir.rglob("*") if path.is_file())

    assert bundle_files == source_files

    for relative_path in bundle_files:
        assert (bundle_dir / relative_path).read_bytes() == (source_dir / relative_path).read_bytes()


def test_claude_plugin_bundle_layout() -> None:
    bundle_root = Path("plugins/claude")

    assert bundle_root.exists()
    assert (bundle_root / ".claude-plugin/plugin.json").exists()
    assert (bundle_root / "README.md").exists()
    assert (bundle_root / "agents").is_dir()
    assert (bundle_root / "skills").is_dir()
    assert (bundle_root / "hooks/hooks.json").exists()

    repo_version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]

    _assert_tree_parity(bundle_root / "agents", Path("agents"))
    _assert_tree_parity(bundle_root / "skills", Path("skills"))
    assert (bundle_root / "hooks/hooks.json").read_bytes() == Path("hooks/hooks.json").read_bytes()

    root_manifest_path = Path(".claude-plugin/plugin.json")
    bundle_manifest_path = bundle_root / ".claude-plugin/plugin.json"
    root_manifest = json.loads(root_manifest_path.read_text())
    bundle_manifest = json.loads(bundle_manifest_path.read_text())

    assert bundle_manifest["name"] == "principia"
    assert bundle_manifest["version"] == repo_version
    assert bundle_manifest["repository"] == "https://github.com/Gavin-Qiao/principia"
    assert root_manifest["name"] == bundle_manifest["name"]
    assert root_manifest["description"] == bundle_manifest["description"]
    assert root_manifest["license"] == bundle_manifest["license"]
    assert root_manifest["keywords"] == bundle_manifest["keywords"]
    assert root_manifest["author"] == bundle_manifest["author"]
    assert root_manifest["repository"] == bundle_manifest["repository"]
    assert root_manifest["version"] != bundle_manifest["version"]
    root_manifest["version"] = repo_version
    assert root_manifest == bundle_manifest
