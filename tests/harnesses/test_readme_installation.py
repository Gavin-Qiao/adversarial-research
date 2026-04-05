from pathlib import Path


def test_readme_mentions_harness_selection() -> None:
    text = Path("README.md").read_text()

    assert "choose the harness you want to use" in text.lower()
    assert "harnesses/claude/README.md" in text
    assert "harnesses/codex/README.md" in text
    assert "shared Python engine" in text


def test_claude_harness_readme_describes_repo_model() -> None:
    text = Path("harnesses/claude/README.md").read_text()

    assert "shared Principia engine" in text
    assert "agents/" in text
    assert "skills/" in text
    assert "hooks/" in text
