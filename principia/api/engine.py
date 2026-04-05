from __future__ import annotations

import io
import json
from argparse import Namespace
from contextlib import redirect_stdout, suppress
from dataclasses import dataclass
from pathlib import Path

from principia.api.types import BuildResult, DashboardResult
from principia.core.commands import cmd_dashboard
from principia.core.config import init_paths
from principia.core.db import build_db
from principia.core.reports import cmd_results
from principia.core.validation import cmd_validate


@dataclass
class PrincipiaEngine:
    root: Path

    def __post_init__(self) -> None:
        init_paths(self.root)

    def build(self) -> dict[str, int]:
        result = self.build_result()
        return {"node_count": result.node_count, "edge_count": result.edge_count}

    def build_result(self) -> BuildResult:
        conn = build_db()
        try:
            node_count = conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
            edge_count = conn.execute("SELECT COUNT(*) AS c FROM edges").fetchone()["c"]
            return BuildResult(node_count=node_count, edge_count=edge_count)
        finally:
            conn.close()

    def dashboard(self) -> dict[str, object]:
        return dict(self.dashboard_result().payload)

    def dashboard_result(self) -> DashboardResult:
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_dashboard(Namespace())
        return DashboardResult(payload=json.loads(buf.getvalue()))

    def validate(self) -> dict[str, object]:
        buf = io.StringIO()
        with redirect_stdout(buf), suppress(SystemExit):
            cmd_validate(Namespace(json=True))
        return json.loads(buf.getvalue())

    def results(self) -> dict[str, object]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_results(Namespace())

        results_path = self.root / "RESULTS.md"
        return {
            "results_path": str(results_path),
            "exists": results_path.exists(),
            "message": buf.getvalue().strip(),
        }
