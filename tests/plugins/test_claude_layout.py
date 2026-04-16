import json
from pathlib import Path


def test_claude_plugin_bundle_layout() -> None:
    bundle_root = Path("plugins/claude")

    assert bundle_root.exists()
    assert (bundle_root / ".claude-plugin/plugin.json").exists()
    assert not (bundle_root / ".claude-plugin/marketplace.json").exists()
    assert (bundle_root / "README.md").exists()
    assert (bundle_root / "agents").is_dir()
    assert (bundle_root / "skills").is_dir()
    assert (bundle_root / "hooks/hooks.json").exists()

    bundle_manifest = json.loads((bundle_root / ".claude-plugin/plugin.json").read_text())

    assert bundle_manifest["name"] == "principia"
    assert bundle_manifest["version"] == "0.5.0"
    assert bundle_manifest["repository"] == "https://github.com/Gavin-Qiao/principia"
    assert bundle_manifest["author"]["email"] == "mohan.qiao@mail.concordia.ca"
    assert bundle_manifest["homepage"] == "https://github.com/Gavin-Qiao/principia"


def test_root_marketplace_json() -> None:
    root_marketplace = Path(".claude-plugin/marketplace.json")
    assert root_marketplace.exists()

    marketplace = json.loads(root_marketplace.read_text())

    bundle_root = Path("plugins/claude")
    bundle_manifest = json.loads((bundle_root / ".claude-plugin/plugin.json").read_text())

    assert marketplace["name"] == "principia"
    assert marketplace["owner"]["name"] == "Mohan"
    assert len(marketplace["plugins"]) == 1

    plugin = marketplace["plugins"][0]
    assert plugin["name"] == "principia"
    assert plugin["source"] == "./plugins/claude"
    assert plugin["version"] == bundle_manifest["version"]
    assert plugin["license"] == bundle_manifest["license"]
    assert plugin["keywords"] == bundle_manifest["keywords"]


def test_legacy_claude_plugin_surfaces_are_removed() -> None:
    assert not Path("plugins/claude/.claude-plugin/marketplace.json").exists()
    assert not Path("harnesses/codex").exists()


def test_claude_compatibility_note_redirects_to_canonical_bundle() -> None:
    text = Path("harnesses/claude/README.md").read_text()

    assert "../../plugins/claude/README.md" in text
    assert "canonical Claude Code bundle" in text
