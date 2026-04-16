import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PLUGIN = REPO_ROOT / "plugins" / "claude"


def test_claude_plugin_bundle_layout() -> None:
    assert PLUGIN.exists()
    assert (PLUGIN / ".claude-plugin/plugin.json").exists()
    assert not (PLUGIN / ".claude-plugin/marketplace.json").exists()
    assert (PLUGIN / "README.md").exists()
    assert (PLUGIN / "agents").is_dir()
    assert (PLUGIN / "skills").is_dir()
    assert (PLUGIN / "hooks/hooks.json").exists()

    bundle_manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())

    assert bundle_manifest["name"] == "principia"
    assert bundle_manifest["version"] == "0.5.0"
    assert bundle_manifest["repository"] == "https://github.com/Gavin-Qiao/principia"
    assert bundle_manifest["author"]["email"] == "mohan.qiao@mail.concordia.ca"
    assert bundle_manifest["homepage"] == "https://github.com/Gavin-Qiao/principia"


def test_root_marketplace_json() -> None:
    root_marketplace = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    assert root_marketplace.exists()

    marketplace = json.loads(root_marketplace.read_text())

    bundle_manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())

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
    assert not (PLUGIN / ".claude-plugin" / "marketplace.json").exists()
    assert not (REPO_ROOT / "harnesses" / "codex").exists()


def test_claude_compatibility_note_redirects_to_canonical_bundle() -> None:
    text = (REPO_ROOT / "harnesses" / "claude" / "README.md").read_text()

    assert "../../plugins/claude/README.md" in text
    assert "canonical Claude Code bundle" in text


def test_plugin_has_11_commands() -> None:
    commands = list((PLUGIN / "commands").glob("*.md"))
    assert len(commands) == 11, f"expected 11 commands, got {len(commands)}: {[c.name for c in commands]}"


def test_plugin_has_2_skills() -> None:
    skills = [d for d in (PLUGIN / "skills").iterdir() if d.is_dir()]
    names = {d.name for d in skills}
    assert names == {"help", "methodology"}, f"expected 2 skills (help, methodology), got {names}"


def test_plugin_has_8_agents() -> None:
    agents = list((PLUGIN / "agents").glob("*.md"))
    assert len(agents) == 8


def test_wrapper_is_executable() -> None:
    pp = PLUGIN / "scripts" / "pp"
    assert pp.exists()
    assert os.access(pp, os.X_OK), "scripts/pp must be executable"


def test_hook_script_is_executable() -> None:
    hook = PLUGIN / "hooks" / "on-session-start.sh"
    assert hook.exists()
    assert os.access(hook, os.X_OK)


def test_nested_marketplace_is_deleted() -> None:
    assert not (PLUGIN / ".claude-plugin" / "marketplace.json").exists(), (
        "nested marketplace.json should have been moved to repo root"
    )


def test_root_marketplace_exists() -> None:
    root_mp = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    assert root_mp.exists()
    data = json.loads(root_mp.read_text())
    assert data["name"] == "principia"
    assert data["plugins"][0]["source"] == "./plugins/claude"
