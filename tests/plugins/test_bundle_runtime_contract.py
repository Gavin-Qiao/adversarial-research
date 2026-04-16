from pathlib import Path

BUNDLE_ROOT = Path("plugins/claude")
LEGACY_MANAGE_PATHS = ("${CLAUDE_PLUGIN_ROOT}/scripts/manage.py", "scripts/manage.py")
PP_WRAPPER = "${CLAUDE_PLUGIN_ROOT}/scripts/pp"
# Commands and skills now route through the pp wrapper; agents retain direct
# manage calls (they are spawned with codebase access and require it).
COMMAND_FILES = (
    "commands/design.md",
    "commands/falsify.md",
    "commands/impact.md",
    "commands/init.md",
    "commands/new.md",
    "commands/query.md",
    "commands/scaffold.md",
    "commands/settle.md",
    "commands/status.md",
    "commands/step.md",
    "commands/validate.md",
)
SKILL_FILES = (
    "skills/help/SKILL.md",
    "skills/methodology/SKILL.md",
)


def test_claude_bundle_uses_packaged_manage_entrypoint() -> None:
    # Commands and skills must use the pp wrapper (not raw manage entrypoints).
    for relative_path in (*COMMAND_FILES, *SKILL_FILES):
        text = (BUNDLE_ROOT / relative_path).read_text()

        assert PP_WRAPPER in text, f"pp wrapper not found in {relative_path}"
        for legacy_path in LEGACY_MANAGE_PATHS:
            assert legacy_path not in text


def test_claude_bundle_has_no_legacy_manage_references() -> None:
    bundle_text_files = [path for path in BUNDLE_ROOT.rglob("*") if path.is_file() and path.suffix in {".md", ".json"}]

    for path in bundle_text_files:
        text = path.read_text()
        for legacy_path in LEGACY_MANAGE_PATHS:
            assert legacy_path not in text, f"{legacy_path} unexpectedly found in {path}"
