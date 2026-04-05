import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path


def test_package_and_legacy_modules_share_build_function() -> None:
    from db import build_db as legacy_build_db

    from principia.core.db import build_db as package_build_db

    assert legacy_build_db is package_build_db


def test_flagged_shims_follow_import_star_pattern() -> None:
    project_root = Path(__file__).resolve().parents[2]

    assert "from principia.core.config import *  # noqa: F403" in (project_root / "scripts" / "config.py").read_text()
    assert (
        "from principia.core.frontmatter import *  # noqa: F403"
        in (project_root / "scripts" / "frontmatter.py").read_text()
    )
    assert "from principia.core.db import *  # noqa: F403" in (project_root / "scripts" / "db.py").read_text()


def test_manage_script_does_not_bootstrap_legacy_scripts_path() -> None:
    project_root = Path(__file__).resolve().parents[2]
    manage_text = (project_root / "scripts" / "manage.py").read_text()

    assert '"scripts"' not in manage_text
    assert "sys.path.insert(0, project_root)" in manage_text


def test_legacy_shims_expose_private_helpers() -> None:
    from orchestration import _parse_yaml_value as legacy_parse_yaml_value
    from reports import _format_investigation_breadcrumb as legacy_format_breadcrumb
    from validation import _find_field as legacy_find_field

    from principia.core.orchestration import _parse_yaml_value as package_parse_yaml_value
    from principia.core.reports import _format_investigation_breadcrumb as package_format_breadcrumb
    from principia.core.validation import _find_field as package_find_field

    assert legacy_parse_yaml_value is package_parse_yaml_value
    assert legacy_format_breadcrumb is package_format_breadcrumb
    assert legacy_find_field is package_find_field


def test_package_modules_work_without_legacy_scripts_path(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    code = """
from argparse import Namespace
from pathlib import Path

from principia.core import config as cfg
from principia.core.commands import cmd_autonomy_config
from principia.core.reports import cmd_results

cfg.init_paths(Path.cwd() / "principia")
cmd_autonomy_config(Namespace())
cmd_results(Namespace())
"""
    env = {"PYTHONPATH": str(project_root)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr


def test_package_config_resolves_repo_assets() -> None:
    from principia.core import config as cfg
    from principia.core.orchestration import load_config

    assert cfg.DEFAULT_ORCH_CONFIG.exists()
    assert (cfg.PLUGIN_ROOT / "agents" / "architect.md").exists()

    roles = [r.get("name") for r in load_config(cfg.DEFAULT_ORCH_CONFIG).get("roles", []) if isinstance(r, dict)]
    assert {"architect", "adversary", "experimenter", "arbiter"} <= set(roles)


def test_prompt_generation_uses_repo_agent_instructions(tmp_path: Path) -> None:
    from principia.core.commands import cmd_prompt
    from principia.core.config import init_paths

    claim_dir = tmp_path / "claims" / "claim-1-test"
    claim_dir.mkdir(parents=True)
    (tmp_path / "context" / "assumptions").mkdir(parents=True)
    (tmp_path / ".db").mkdir()
    (claim_dir / "claim.md").write_text(
        "---\nid: h1-test\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Test claim\n",
        encoding="utf-8",
    )

    init_paths(tmp_path)
    cmd_prompt(Namespace(path="claims/claim-1-test"))

    prompt = (claim_dir / "architect" / "round-1" / "prompt.md").read_text(encoding="utf-8")
    assert "Do NOT attempt to read files from the codebase" in prompt


def test_package_only_distribution_resolves_packaged_assets(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    package_root = tmp_path / "package-only"
    shutil.copytree(project_root / "principia", package_root / "principia")

    code = """
from argparse import Namespace
from pathlib import Path

from principia.core import config as cfg
from principia.core.commands import cmd_prompt
from principia.core.orchestration import load_config

design_root = Path.cwd() / "principia"
claim_dir = design_root / "claims" / "claim-1-test"
claim_dir.mkdir(parents=True)
(design_root / "context" / "assumptions").mkdir(parents=True)
(design_root / ".db").mkdir()
(claim_dir / "claim.md").write_text(
    "---\\n"
    "id: h1-test\\n"
    "type: claim\\n"
    "status: active\\n"
    "date: 2026-01-01\\n"
    "---\\n\\n"
    "# Test claim\\n",
    encoding="utf-8",
)

cfg.init_paths(design_root)
cmd_prompt(Namespace(path="claims/claim-1-test"))
roles = [r.get("name") for r in load_config(cfg.DEFAULT_ORCH_CONFIG).get("roles", []) if isinstance(r, dict)]
prompt = (claim_dir / "architect" / "round-1" / "prompt.md").read_text(encoding="utf-8")

assert cfg.DEFAULT_ORCH_CONFIG.exists()
assert {"architect", "adversary", "experimenter", "arbiter"} <= set(roles)
assert "Do NOT attempt to read files from the codebase" in prompt
print("OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(package_root)},
    )

    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_runtime_resolved_agent_instructions_use_packaged_manage_entrypoint() -> None:
    experimenter_command = "uv run python -m principia.cli.manage --root principia codebook"
    conductor_command = "uv run python -m principia.cli.manage --root principia next <claim-path>"

    for path in (
        Path("agents/experimenter.md"),
        Path("principia/agents/experimenter.md"),
    ):
        text = path.read_text(encoding="utf-8")
        assert experimenter_command in text
        assert "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" not in text
        assert "python3 scripts/manage.py" not in text

    for path in (
        Path("agents/conductor.md"),
        Path("principia/agents/conductor.md"),
    ):
        text = path.read_text(encoding="utf-8")
        assert conductor_command in text
        assert "${CLAUDE_PLUGIN_ROOT}/scripts/manage.py" not in text
        assert "python3 scripts/manage.py" not in text


def test_packaged_protocol_doc_is_shipped_and_referenced() -> None:
    protocol_path = Path("principia/config/protocol.md")
    assert protocol_path.exists()

    for path in (
        Path("agents/conductor.md"),
        Path("principia/agents/conductor.md"),
        Path("agents/synthesizer.md"),
        Path("principia/agents/synthesizer.md"),
    ):
        assert "principia/config/protocol.md" in path.read_text(encoding="utf-8")
