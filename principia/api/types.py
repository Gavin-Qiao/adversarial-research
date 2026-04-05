from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BuildResult:
    node_count: int
    edge_count: int


@dataclass
class DashboardResult:
    payload: dict[str, Any]
