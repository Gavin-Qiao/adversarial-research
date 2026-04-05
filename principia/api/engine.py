from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PrincipiaEngine:
    root: Path

    def __post_init__(self) -> None:
        from config import init_paths

        init_paths(self.root)

    def build(self) -> dict[str, int]:
        from db import build_db

        conn = build_db()
        try:
            node_count = conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
            edge_count = conn.execute("SELECT COUNT(*) AS c FROM edges").fetchone()["c"]
            return {"node_count": node_count, "edge_count": edge_count}
        finally:
            conn.close()
