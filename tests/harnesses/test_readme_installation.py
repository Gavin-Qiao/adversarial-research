from pathlib import Path

import tomllib


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


def test_changelog_tracks_recent_releases() -> None:
    text = Path("CHANGELOG.md").read_text()

    assert "## [0.4.0a3] - 2026-04-05" in text
    assert "## [0.3.3] - 2026-04-04" in text
    assert "### Features" in text
    assert "### Fixes" in text


def test_release_metadata_versions_stay_aligned() -> None:
    expected_version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]

    assert expected_version == "0.4.0a3"
    assert f'## [{expected_version}] - 2026-04-05' in Path("CHANGELOG.md").read_text()
    assert f'"version": "{expected_version}"' in Path("plugins/codex/.codex-plugin/plugin.json").read_text()
    assert f'"version": "{expected_version}"' in Path("plugins/claude/.claude-plugin/plugin.json").read_text()
    assert f'"version": "{expected_version}"' in Path("plugins/claude/.claude-plugin/marketplace.json").read_text()
    assert f'version = "{expected_version}"' in Path("uv.lock").read_text()


def test_claude_bundle_readme_describes_canonical_surface() -> None:
    text = Path("plugins/claude/README.md").read_text()

    assert "Principia Claude Bundle" in text
    assert "Canonical Claude Code plugin bundle" in text
    assert "plugins/claude" in text
    assert "full Principia checkout" in text
    assert "canonical Claude bundle lives under" in text


def test_codex_bundle_readme_describes_native_wrapper() -> None:
    text = Path("plugins/codex/README.md").read_text()

    assert "Principia Codex Bundle" in text
    assert "plugins/codex" in text
    assert "full Principia checkout" in text
    assert "shared repo content" in text
    assert "uv run python -m principia.cli.codex_runner --root design dashboard" in text
    assert "unsupported" in text
