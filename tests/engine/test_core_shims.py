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


def test_manage_script_does_not_bootstrap_sys_path() -> None:
    project_root = Path(__file__).resolve().parents[2]
    manage_text = (project_root / "scripts" / "manage.py").read_text()

    assert "sys.path.insert" not in manage_text
