import json
from pathlib import Path


def test_codex_plugin_manifest_exists() -> None:
    plugin_path = Path("plugins/codex/.codex-plugin/plugin.json")
    assert plugin_path.exists()

    manifest = json.loads(plugin_path.read_text(encoding="utf-8"))
    assert manifest["name"] == "principia"
    assert manifest["description"] == "Principia workflow for Codex."
    assert manifest["skills"] == "./skills/"
    assert manifest["interface"]["displayName"] == "Principia"
    assert manifest["interface"]["category"] == "Productivity"
    assert manifest["interface"]["shortDescription"] == "Principia skills for Codex."
    assert "plugins/codex" in manifest["interface"]["longDescription"]
    assert "principia:init" in manifest["interface"]["longDescription"]
    assert "principia:status" in manifest["interface"]["longDescription"]
    assert "full Principia checkout" in manifest["interface"]["longDescription"]
    assert "unsupported" in manifest["interface"]["longDescription"]
    assert manifest["interface"]["defaultPrompt"]
    assert "principia:init" in manifest["interface"]["defaultPrompt"][0]
    assert "principia:status" in manifest["interface"]["defaultPrompt"][1]


def test_codex_skills_readme_matches_current_bundle_content() -> None:
    readme = Path("plugins/codex/skills/README.md").read_text(encoding="utf-8")

    assert "Canonical Codex skills" in readme
    assert "packaged runner" in readme
    assert "principia.cli.codex_runner" in readme
    assert "User-intent map" in readme
    assert "`status`" in readme
    assert "`next-step`" in readme
    assert "`results`" in readme
    assert "`patch-status`" in readme
    assert "`packet`, `prompt`, `dispatch-log`" in readme
    assert "legacy harness runner path" not in readme
    assert "packaged-runtime migration task" not in readme


def test_codex_bundle_readme_describes_skills_not_slash_commands() -> None:
    readme = Path("plugins/codex/README.md").read_text(encoding="utf-8")

    assert "skills, not slash commands" in readme
    assert "plugins/codex" in readme
    assert "`principia:init`" in readme
    assert "`principia:status`" in readme
    assert "`principia:next-step`" in readme
    assert "`principia:results`" in readme
    assert "Ordered Codex flow" in readme
    assert "First 10 minutes in Codex" in readme
    assert "patch-status" in readme
    assert "visualize" in readme
    assert "packet --path" in readme
    assert "dispatch-log --cycle" in readme
    assert "Use `principia.cli.manage` only for state-changing operations" in readme
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
        text = (bundle_root / relative_path).read_text(encoding="utf-8")
        assert runner_command in text
        assert "description: Use when " in text
        assert "harnesses/codex/scripts/engine_runner.py" not in text

    init_text = (bundle_root / "init/SKILL.md").read_text(encoding="utf-8")
    principia_text = (bundle_root / "principia/SKILL.md").read_text(encoding="utf-8")
    status_text = (bundle_root / "status/SKILL.md").read_text(encoding="utf-8")
    next_step_text = (bundle_root / "next-step/SKILL.md").read_text(encoding="utf-8")
    results_text = (bundle_root / "results/SKILL.md").read_text(encoding="utf-8")

    assert "/principia:init" not in init_text
    assert "/principia:init" not in next_step_text
    assert "`principia:init`" in init_text
    assert "`principia:init`" in next_step_text
    assert "Summarize warnings first." in status_text
    assert "patch-status" in status_text
    assert "patch-status" in init_text
    assert "patch-status" in next_step_text
    assert "packet --path" in next_step_text
    assert "README.md" in init_text
    assert "AGENTS.md" in init_text
    assert ".context.md" in init_text
    assert "next --path [claim-path]" in next_step_text
    assert "dispatch-log --cycle [claim-slug]" in next_step_text
    assert "dispatch-log --cycle [claim-slug]" in status_text
    assert "human decision" in status_text
    assert "verdict was already recorded" in status_text
    assert "operator_guidance.recommended_action" not in next_step_text
    assert "operator_guidance.summary" not in status_text
    assert "results_summary" in results_text
    assert "`results_path`" in results_text
    assert "`message`" in results_text
    assert "plugins/codex" in principia_text
    assert "generated workspace" in init_text
    assert "generated workflow workspace" in status_text
    assert "asking what to do next" in next_step_text
    assert "investigate-next" not in next_step_text


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
    repo_marketplace = json.loads(Path(".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
    remote_marketplace = json.loads(Path("marketplace.json").read_text(encoding="utf-8"))

    assert repo_marketplace["interface"]["displayName"] == "Principia"
    assert remote_marketplace["interface"]["displayName"] == "Principia"
    assert repo_marketplace["plugins"] == remote_marketplace["plugins"]

    plugin = next(plugin for plugin in remote_marketplace["plugins"] if plugin["name"] == "principia")
    assert plugin["source"]["source"] == "local"
    assert plugin["source"]["path"] == "./plugins/codex"
    assert plugin["policy"]["installation"] == "AVAILABLE"
    assert plugin["policy"]["authentication"] == "ON_INSTALL"
    assert plugin["category"] == "Productivity"


def test_codex_surface_keeps_principia_plugin_identity() -> None:
    manifest = json.loads(Path("plugins/codex/.codex-plugin/plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads(Path("marketplace.json").read_text(encoding="utf-8"))

    plugin = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == "principia")

    assert manifest["name"] == "principia"
    assert plugin["name"] == "principia"
    assert plugin["source"]["path"] == "./plugins/codex"
