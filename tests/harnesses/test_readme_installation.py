from pathlib import Path


def test_readme_mentions_harness_selection() -> None:
    text = Path("README.md").read_text()

    assert "Choose a harness" in text
    assert "harnesses/claude/README.md" in text
    assert "harnesses/codex/README.md" in text
    assert "CHANGELOG.md" in text
    assert "shared Python engine" in text
    assert "full Principia checkout" in text


def test_changelog_tracks_recent_releases() -> None:
    text = Path("CHANGELOG.md").read_text()

    assert "## [0.4.0a2] - 2026-04-05" in text
    assert "## [0.3.3] - 2026-04-04" in text
    assert "### Features" in text
    assert "### Fixes" in text


def test_claude_harness_readme_describes_repo_model() -> None:
    text = Path("harnesses/claude/README.md").read_text()

    assert "shared Principia engine" in text
    assert "agents/" in text
    assert "skills/" in text
    assert "hooks/" in text


def test_codex_bundle_readme_describes_native_wrapper() -> None:
    text = Path("plugins/codex/README.md").read_text()

    assert "Principia Codex Bundle" in text
    assert "plugins/codex" in text
    assert "full Principia checkout" in text
    assert "shared repo content" in text
    assert "uv run python -m principia.cli.codex_runner --root design dashboard" in text
    assert "unsupported" in text
