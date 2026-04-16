import tomllib
from pathlib import Path


def test_readme_opening_mentions_plugin_bundle_choice() -> None:
    text = Path("README.md").read_text()
    opening = text.split("## Installation", 1)[0]

    assert "plugins/claude/README.md" in opening
    assert "plugins/codex/README.md" in opening
    assert "harnesses/claude/README.md" not in opening
    assert "harnesses/codex/README.md" not in opening
    assert "same packaged Principia runtime under `principia/`" in opening
    assert "full Principia checkout" in opening
    assert "CHANGELOG.md" in text
    assert "full Principia checkout" in text


def test_readme_installation_documents_verified_bundle_flows() -> None:
    text = Path("README.md").read_text()

    # Claude Code section now uses the local marketplace install flow (plugin 0.5.0).
    assert "/plugin marketplace add" in text
    assert "/plugin install principia@principia" in text
    assert "plugins/claude/README.md" in text
    assert ".agents/plugins/marketplace.json" in text
    assert "./plugins/codex" in text
    assert "install the `principia` plugin from the repo-local marketplace" in text
    assert "uv build --wheel" in text
    assert "uv pip install" in text


def test_changelog_tracks_recent_releases() -> None:
    text = Path("CHANGELOG.md").read_text()
    current_version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]

    assert f"## [{current_version}] - 2026-04-15" in text
    assert "## [0.3.3] - 2026-04-04" in text
    assert "### Features" in text
    assert "### Fixes" in text


def test_release_metadata_versions_stay_aligned() -> None:
    expected_version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]

    assert f"## [{expected_version}] - 2026-04-15" in Path("CHANGELOG.md").read_text()
    assert f'"version": "{expected_version}"' in Path("plugins/codex/.codex-plugin/plugin.json").read_text()
    assert f'version = "{expected_version}"' in Path("uv.lock").read_text()

    # The Claude plugin uses its own independent version (bumped to 0.5.0 in T7).
    # Verify the root marketplace.json and plugin.json agree with each other.
    import json as _json

    plugin = _json.loads(Path("plugins/claude/.claude-plugin/plugin.json").read_text())
    root_mkt = _json.loads(Path(".claude-plugin/marketplace.json").read_text())
    assert plugin["version"] == root_mkt["plugins"][0]["version"]


def test_claude_bundle_readme_describes_canonical_surface() -> None:
    text = Path("plugins/claude/README.md").read_text()

    # Plugin 0.5.0: marketplace-based install; pp wrapper; CONTRACT.md reference.
    assert "Principia — Claude Code Plugin" in text
    assert "Canonical Claude Code plugin bundle" in text
    assert "plugins/claude" in text
    assert "/plugin marketplace add" in text
    assert "/plugin install principia@principia" in text
    assert "/principia:help" in text
    assert "docs/CONTRACT.md" in text
    assert "claude --plugin-dir ./plugins/claude" in text


def test_codex_bundle_readme_describes_native_wrapper() -> None:
    text = Path("plugins/codex/README.md").read_text()

    assert "Principia Codex Bundle" in text
    assert "plugins/codex" in text
    assert "full Principia checkout" in text
    assert "shared repo content" in text
    assert "uv run python -m principia.cli.codex_runner --root principia dashboard" in text
    assert "unsupported" in text
    assert ".agents/plugins/marketplace.json" in text
    assert "install the `principia` plugin from the repo-local marketplace" in text
