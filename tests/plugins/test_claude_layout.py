import json
from pathlib import Path

import tomllib


def test_claude_plugin_bundle_layout() -> None:
    bundle_root = Path("plugins/claude")

    assert bundle_root.exists()
    assert (bundle_root / ".claude-plugin/plugin.json").exists()
    assert (bundle_root / ".claude-plugin/marketplace.json").exists()
    assert (bundle_root / "README.md").exists()
    assert (bundle_root / "agents").is_dir()
    assert (bundle_root / "skills").is_dir()
    assert (bundle_root / "hooks/hooks.json").exists()

    repo_version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    bundle_manifest = json.loads((bundle_root / ".claude-plugin/plugin.json").read_text())
    marketplace = json.loads((bundle_root / ".claude-plugin/marketplace.json").read_text())

    assert bundle_manifest["name"] == "principia"
    assert bundle_manifest["version"] == repo_version
    assert bundle_manifest["repository"] == "https://github.com/Gavin-Qiao/principia"

    assert marketplace["name"] == "principia"
    assert marketplace["owner"]["name"] == "Mohan"
    assert marketplace["metadata"]["description"] == bundle_manifest["description"]
    assert len(marketplace["plugins"]) == 1

    plugin = marketplace["plugins"][0]
    assert plugin["name"] == "principia"
    assert plugin["source"] == "./"
    assert plugin["description"] == bundle_manifest["description"]
    assert plugin["version"] == bundle_manifest["version"]
    assert plugin["license"] == bundle_manifest["license"]
    assert plugin["keywords"] == bundle_manifest["keywords"]


def test_root_claude_surface_keeps_core_metadata_aligned() -> None:
    root_root = Path(".claude-plugin")
    bundle_root = Path("plugins/claude/.claude-plugin")

    root_manifest = json.loads((root_root / "plugin.json").read_text())
    bundle_manifest = json.loads((bundle_root / "plugin.json").read_text())

    core_fields = ("name", "description", "license", "keywords", "author", "repository")

    for field in core_fields:
        assert root_manifest[field] == bundle_manifest[field]

    root_marketplace = json.loads((root_root / "marketplace.json").read_text())
    bundle_marketplace = json.loads((bundle_root / "marketplace.json").read_text())

    assert root_marketplace["name"] == bundle_marketplace["name"]
    assert root_marketplace["owner"] == bundle_marketplace["owner"]
    assert root_marketplace["metadata"]["description"] == bundle_marketplace["metadata"]["description"]
    assert root_marketplace["plugins"][0]["name"] == bundle_marketplace["plugins"][0]["name"]
    assert root_marketplace["plugins"][0]["source"] == bundle_marketplace["plugins"][0]["source"]
