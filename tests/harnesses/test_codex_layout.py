import json
from pathlib import Path


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

    assert "canonical Principia Codex skills" in readme
    assert "packaged runner" in readme
    assert "principia.cli.codex_runner" in readme
    assert "`patch-status`" in readme
    assert "legacy harness runner path" not in readme
    assert "packaged-runtime migration task" not in readme


def test_codex_bundle_readme_describes_skills_not_slash_commands() -> None:
    readme = Path("plugins/codex/README.md").read_text()

    assert "skills, not slash commands" in readme
    assert "`principia:init`" in readme
    assert "patch-status" in readme
    assert "packet --path" in readme
    assert "/principia:init" not in readme


def test_codex_skills_use_packaged_runner_commands() -> None:
    bundle_root = Path("plugins/codex/skills")
    runner_command = "uv run python -m principia.cli.codex_runner --root principia"

    skill_files = [
        "init/SKILL.md",
        "principia/SKILL.md",
        "status/SKILL.md",
        "validate/SKILL.md",
        "results/SKILL.md",
        "next-step/SKILL.md",
        "falsify/SKILL.md",
        "settle/SKILL.md",
        "reopen/SKILL.md",
        "post-verdict/SKILL.md",
        "replace-verdict/SKILL.md",
    ]

    for relative_path in skill_files:
        text = (bundle_root / relative_path).read_text()
        assert runner_command in text
        assert "harnesses/codex/scripts/engine_runner.py" not in text

    init_text = (bundle_root / "init/SKILL.md").read_text()
    status_text = (bundle_root / "status/SKILL.md").read_text()
    next_step_text = (bundle_root / "next-step/SKILL.md").read_text()

    assert "/principia:init" not in init_text
    assert "/principia:init" not in next_step_text
    assert "`principia:init`" in init_text
    assert "`principia:init`" in next_step_text
    assert "`warnings` first" in status_text
    assert "north_star_drift" in status_text
    assert "north_star_drift" in init_text
    assert "patch-status" in next_step_text
    assert "packet --path" in next_step_text


def test_codex_skills_have_expected_canonical_structure() -> None:
    bundle_root = Path("plugins/codex/skills")
    expected_files = {
        Path("README.md"),
        Path("init/SKILL.md"),
        Path("principia/SKILL.md"),
        Path("status/SKILL.md"),
        Path("validate/SKILL.md"),
        Path("results/SKILL.md"),
        Path("next-step/SKILL.md"),
        Path("falsify/SKILL.md"),
        Path("settle/SKILL.md"),
        Path("reopen/SKILL.md"),
        Path("post-verdict/SKILL.md"),
        Path("replace-verdict/SKILL.md"),
    }

    actual_files = {path.relative_to(bundle_root) for path in bundle_root.rglob("*") if path.is_file()}

    assert actual_files == expected_files


def test_marketplace_exposes_principia_plugin() -> None:
    marketplace = json.loads(Path(".agents/plugins/marketplace.json").read_text())
    assert marketplace["interface"]["displayName"] == "Principia"

    plugin = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == "principia")
    assert plugin["source"]["source"] == "local"
    assert plugin["source"]["path"] == "./plugins/codex"
    assert plugin["policy"]["installation"] == "AVAILABLE"
    assert plugin["policy"]["authentication"] == "ON_INSTALL"
    assert plugin["category"] == "Productivity"
