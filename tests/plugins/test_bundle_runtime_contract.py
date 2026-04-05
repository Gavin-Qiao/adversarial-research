from pathlib import Path

BUNDLE_ROOT = Path("plugins/claude")
PACKAGED_MANAGE = "uv run python -m principia.cli.manage --root design"
LEGACY_MANAGE_PATHS = ("${CLAUDE_PLUGIN_ROOT}/scripts/manage.py", "scripts/manage.py")
REPRESENTATIVE_FILES = (
    "README.md",
    "agents/conductor.md",
    "agents/experimenter.md",
    "hooks/hooks.json",
    "skills/design/SKILL.md",
    "skills/falsify/SKILL.md",
    "skills/help/SKILL.md",
    "skills/impact/SKILL.md",
    "skills/init/SKILL.md",
    "skills/new/SKILL.md",
    "skills/query/SKILL.md",
    "skills/scaffold/SKILL.md",
    "skills/settle/SKILL.md",
    "skills/status/SKILL.md",
    "skills/step/SKILL.md",
    "skills/validate/SKILL.md",
)


def test_claude_bundle_uses_packaged_manage_entrypoint() -> None:
    for relative_path in REPRESENTATIVE_FILES:
        text = (BUNDLE_ROOT / relative_path).read_text()

        assert PACKAGED_MANAGE in text
        for legacy_path in LEGACY_MANAGE_PATHS:
            assert legacy_path not in text


def test_claude_bundle_has_no_legacy_manage_references() -> None:
    bundle_text_files = [path for path in BUNDLE_ROOT.rglob("*") if path.is_file() and path.suffix in {".md", ".json"}]

    for path in bundle_text_files:
        text = path.read_text()
        for legacy_path in LEGACY_MANAGE_PATHS:
            assert legacy_path not in text, f"{legacy_path} unexpectedly found in {path}"
