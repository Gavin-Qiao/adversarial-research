from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from principia.api.types import BuildResult, DashboardResult
from principia.core.commands import get_dashboard_payload
from principia.core.db import build_db
from principia.core.reports import generate_results_report
from principia.core.validation import ValidationResult, collect_validation_result


@dataclass
class PrincipiaEngine:
    root: Path

    def __post_init__(self) -> None:
        self.root = self.root.resolve()

    def build(self) -> dict[str, int]:
        result = self.build_result()
        return {"node_count": result.node_count, "edge_count": result.edge_count}

    def build_result(self) -> BuildResult:
        conn = build_db(root=self.root)
        try:
            node_count = conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
            edge_count = conn.execute("SELECT COUNT(*) AS c FROM edges").fetchone()["c"]
            return BuildResult(node_count=node_count, edge_count=edge_count)
        finally:
            conn.close()

    def dashboard(self) -> dict[str, object]:
        return dict(self.dashboard_result().payload)

    def dashboard_result(self) -> DashboardResult:
        return DashboardResult(payload=get_dashboard_payload(self.root))

    def validate(self) -> ValidationResult:
        return collect_validation_result(self.root)

    def results(self) -> dict[str, object]:
        results_path, message = generate_results_report(self.root)
        return {
            "results_path": str(results_path),
            "exists": results_path.exists(),
            "message": message,
        }
