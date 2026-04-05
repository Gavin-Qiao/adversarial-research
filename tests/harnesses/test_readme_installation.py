from pathlib import Path


def test_readme_mentions_harness_selection() -> None:
    text = Path("README.md").read_text()

    assert "Choose a harness" in text
    assert "harnesses/claude/README.md" in text
    assert "harnesses/codex/README.md" in text
    assert "shared Python engine" in text


def test_claude_harness_readme_describes_repo_model() -> None:
    text = Path("harnesses/claude/README.md").read_text()

    assert "shared Principia engine" in text
    assert "agents/" in text
    assert "skills/" in text
    assert "hooks/" in text


def test_codex_harness_readme_describes_native_wrapper() -> None:
    text = Path("harnesses/codex/README.md").read_text()

    assert "Install Principia in Codex" in text
    assert "Codex-native" in text
    assert "shared Principia engine" in text
