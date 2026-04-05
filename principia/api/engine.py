from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


def _ensure_legacy_scripts_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    scripts_path = str(scripts_dir)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)


@dataclass
class PrincipiaEngine:
    root: Path

    def __post_init__(self) -> None:
        _ensure_legacy_scripts_path()

        from config import init_paths

        init_paths(self.root)

    def build(self) -> dict[str, int]:
        _ensure_legacy_scripts_path()

        from db import build_db

        conn = build_db()
        try:
            node_count = conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
            edge_count = conn.execute("SELECT COUNT(*) AS c FROM edges").fetchone()["c"]
            return {"node_count": node_count, "edge_count": edge_count}
        finally:
            conn.close()
