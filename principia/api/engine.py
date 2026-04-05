from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import init_paths
from db import build_db


@dataclass
class PrincipiaEngine:
    root: Path

    def __post_init__(self) -> None:
        init_paths(self.root)

    def build(self) -> dict[str, int]:
        conn = build_db()
        node_count = conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
        edge_count = conn.execute("SELECT COUNT(*) AS c FROM edges").fetchone()["c"]
        return {"node_count": node_count, "edge_count": edge_count}
