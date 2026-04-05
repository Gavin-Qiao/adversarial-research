import subprocess
import sys
from pathlib import Path


def test_package_and_legacy_modules_share_build_function() -> None:
    from db import build_db as legacy_build_db

    from principia.core.db import build_db as package_build_db

    assert legacy_build_db is package_build_db


def test_flagged_shims_follow_import_star_pattern() -> None:
    project_root = Path(__file__).resolve().parents[2]

    assert "from principia.core.config import *  # noqa: F403" in (project_root / "scripts" / "config.py").read_text()
    assert "from principia.core.frontmatter import *  # noqa: F403" in (
        project_root / "scripts" / "frontmatter.py"
    ).read_text()
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

cfg.init_paths(Path.cwd() / "design")
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
