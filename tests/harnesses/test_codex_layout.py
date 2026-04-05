import json
from pathlib import Path


def _assert_tree_parity(bundle_dir: Path, source_dir: Path) -> None:
    bundle_files = sorted(
        path.relative_to(bundle_dir) for path in bundle_dir.rglob("*") if path.is_file() and path.name != "README.md"
    )
    source_files = sorted(
        path.relative_to(source_dir) for path in source_dir.rglob("*") if path.is_file() and path.name != "README.md"
    )

    assert bundle_files == source_files

    for relative_path in bundle_files:
        assert (bundle_dir / relative_path).read_bytes() == (source_dir / relative_path).read_bytes()


def test_codex_plugin_manifest_exists() -> None:
    plugin_path = Path("plugins/codex/.codex-plugin/plugin.json")
    assert plugin_path.exists()

    manifest = json.loads(plugin_path.read_text())
    assert manifest["name"] == "principia"
    assert manifest["skills"] == "./skills/"
    assert manifest["interface"]["displayName"] == "Principia"
    assert manifest["interface"]["category"] == "Productivity"
    assert "Canonical" in manifest["interface"]["shortDescription"]
    assert "plugins/codex" in manifest["interface"]["shortDescription"]
    assert "canonical `plugins/codex` bundle" in manifest["interface"]["longDescription"]
    assert "unsupported" in manifest["interface"]["longDescription"]


def test_codex_skills_readme_matches_current_bundle_content() -> None:
    readme = Path("plugins/codex/skills/README.md").read_text()

    assert "mirrored Principia Codex skills" in readme
    assert "canonical `plugins/codex` bundle" in readme
    assert "preserved here during the migration from `harnesses/codex`" in readme
    assert "legacy harness runner path" in readme
    assert "packaged-runtime migration task" in readme


def test_codex_skills_mirror_legacy_tree() -> None:
    bundle_root = Path("plugins/codex/skills")
    legacy_root = Path("harnesses/codex/skills")

    _assert_tree_parity(bundle_root, legacy_root)


def test_marketplace_exposes_principia_plugin() -> None:
    marketplace = json.loads(Path(".agents/plugins/marketplace.json").read_text())
    assert marketplace["interface"]["displayName"] == "Principia"

    plugin = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == "principia")
    assert plugin["source"]["source"] == "local"
    assert plugin["source"]["path"] == "./plugins/codex"
    assert plugin["policy"]["installation"] == "AVAILABLE"
    assert plugin["policy"]["authentication"] == "ON_INSTALL"
    assert plugin["category"] == "Productivity"
