import json
import tomllib
from pathlib import Path


def test_readme_opening_mentions_plugin_bundle_choice() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    opening = text.split("## Installation", 1)[0]

    assert "plugins/claude/README.md" in opening
    assert "plugins/codex/README.md" in opening
    assert "harnesses/claude/README.md" not in opening
    assert "harnesses/codex/README.md" not in opening
    assert "same packaged Principia runtime under `principia/`" in opening
    assert "full Principia checkout" in opening
    assert "plugins/claude" in opening
    assert "plugins/codex" in opening
    assert "generated workflow workspace" in opening
    assert "CHANGELOG.md" in text
    assert "full Principia checkout" in text


def test_readme_installation_documents_verified_bundle_flows() -> None:
    text = Path("README.md").read_text(encoding="utf-8")

    assert "claude --plugin-dir ./plugins/claude" in text
    assert "codex marketplace add Gavin-Qiao/principia" in text
    assert "marketplace.json" in text
    assert ".agents/plugins/marketplace.json" in text
    assert "./plugins/codex" in text
    assert "install the `principia` plugin from either marketplace surface" in text
    assert "uv build --wheel" in text
    assert "uv pip install" in text


def test_changelog_tracks_recent_releases() -> None:
    text = Path("CHANGELOG.md").read_text(encoding="utf-8")
    current_version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]

    assert f"## [{current_version}] - 2026-04-17" in text
    assert "## [0.3.3] - 2026-04-04" in text
    assert "### Features" in text
    assert "### Fixes" in text


def test_release_metadata_versions_stay_aligned() -> None:
    expected_version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    codex_manifest = json.loads(Path("plugins/codex/.codex-plugin/plugin.json").read_text(encoding="utf-8"))

    assert f"## [{expected_version}] - 2026-04-17" in Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert codex_manifest["version"] == expected_version
    assert f'"version": "{expected_version}"' in Path("plugins/claude/.claude-plugin/plugin.json").read_text(encoding="utf-8")
    assert f'"version": "{expected_version}"' in Path("plugins/claude/.claude-plugin/marketplace.json").read_text(encoding="utf-8")
    assert f'version = "{expected_version}"' in Path("uv.lock").read_text(encoding="utf-8")


def test_claude_bundle_readme_describes_canonical_surface() -> None:
    text = Path("plugins/claude/README.md").read_text(encoding="utf-8")

    assert "Principia Claude Bundle" in text
    assert "Canonical Claude Code plugin bundle" in text
    assert "plugins/claude" in text
    assert "full Principia checkout" in text
    assert "canonical Claude bundle lives under" in text
    assert "claude --plugin-dir ./plugins/claude" in text
    assert "/help" in text


def test_codex_bundle_readme_describes_native_wrapper() -> None:
    text = Path("plugins/codex/README.md").read_text(encoding="utf-8")

    assert "Principia Codex Bundle" in text
    assert "plugins/codex" in text
    assert "full Principia checkout" in text
    assert "shared repo content" in text
    assert "codex marketplace add Gavin-Qiao/principia" in text
    assert "marketplace.json" in text
    assert "uv run python -m principia.cli.codex_runner --root principia dashboard" in text
    assert "uv run python -m principia.cli.codex_runner --root principia results" in text
    assert "uv run python -m principia.cli.codex_runner --root principia visualize" in text
    assert "unsupported" in text
    assert ".agents/plugins/marketplace.json" in text
    assert "install the `principia` plugin from the repo-local marketplace" in text
    assert "Ordered Codex flow" in text
    assert "First 10 minutes in Codex" in text
    assert "Artifact ladder" in text
    assert "stateful handoff tools" in text
