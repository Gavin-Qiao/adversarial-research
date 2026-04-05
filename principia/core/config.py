"""
Shared path globals and utility functions for Principia scripts.

All path globals are initialised to Path(".") and must be set by calling
init_paths() before use.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths (set by init_paths(), called from main())
# ---------------------------------------------------------------------------

RESEARCH_DIR: Path = Path(".")
DB_PATH: Path = Path(".")
CONTEXT_DIR: Path = Path(".")
PROGRESS_PATH: Path = Path(".")
FOUNDATIONS_PATH: Path = Path(".")


def init_paths(root: Path) -> None:
    """Configure all path globals from the given research root directory."""
    global RESEARCH_DIR, DB_PATH, CONTEXT_DIR, PROGRESS_PATH, FOUNDATIONS_PATH
    RESEARCH_DIR = root.resolve()
    DB_PATH = RESEARCH_DIR / ".db" / "research.db"
    CONTEXT_DIR = RESEARCH_DIR / "context"
    PROGRESS_PATH = RESEARCH_DIR / "PROGRESS.md"
    FOUNDATIONS_PATH = RESEARCH_DIR / "FOUNDATIONS.md"


def _emit_progress(
    phase: str,
    step: str,
    detail: str = "",
    total: int | None = None,
    current: int | None = None,
) -> None:
    """Emit structured progress to stderr for skill-level reporting."""
    progress: dict[str, Any] = {"type": "progress", "phase": phase, "step": step}
    if detail:
        progress["detail"] = detail
    if total is not None:
        progress["total"] = total
        progress["current"] = current
    print(json.dumps(progress), file=sys.stderr)


def _atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to path atomically via temp file + os.replace().

    Writes to a temporary file in the same directory, then uses
    os.replace() which is atomic on the same filesystem.  If the write
    or rename fails, the temp file is cleaned up and the original file
    is left intact.
    """
    fd = None
    tmp_path: Path | None = None
    try:
        fd = tempfile.NamedTemporaryFile(  # noqa: SIM115
            mode="w",
            encoding=encoding,
            dir=path.parent,
            suffix=".tmp",
            delete=False,
        )
        tmp_path = Path(fd.name)
        fd.write(content)
        fd.flush()
        os.fsync(fd.fileno())
        fd.close()
        fd = None
        os.replace(tmp_path, path)
    except BaseException:
        if fd is not None:
            fd.close()
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def rel_path_from_root(p: Path) -> str:
    """Return path relative to the research root."""
    return str(p.relative_to(RESEARCH_DIR))


# ---------------------------------------------------------------------------
# Plugin-level paths
# ---------------------------------------------------------------------------

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_plugin_root() -> Path:
    """Prefer the repo root, but fall back to packaged assets when present."""
    candidates = (_REPO_ROOT, _PACKAGE_ROOT)
    for candidate in candidates:
        if (candidate / "config" / "orchestration.yaml").exists() and (candidate / "agents").exists():
            return candidate
    return _REPO_ROOT


PLUGIN_ROOT = _resolve_plugin_root()
DEFAULT_ORCH_CONFIG = PLUGIN_ROOT / "config" / "orchestration.yaml"
