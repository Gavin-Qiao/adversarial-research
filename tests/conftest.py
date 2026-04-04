"""Shared test fixtures and builders for principia tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from manage import build_db, init_paths, serialise_frontmatter

# ---------------------------------------------------------------------------
# Basic fixtures (backward-compatible with existing tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def research_dir(tmp_path):
    """Create a minimal research directory structure and configure paths."""
    claims = tmp_path / "claims"
    context = tmp_path / "context" / "assumptions"
    db = tmp_path / ".db"
    claims.mkdir(parents=True)
    context.mkdir(parents=True)
    db.mkdir()
    init_paths(tmp_path)
    return tmp_path


@pytest.fixture
def sample_node(research_dir):
    """Create a sample architect result file with frontmatter."""
    path = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
    path.mkdir(parents=True)
    f = path / "result.md"
    meta = {
        "id": "h1-architect-r1-result",
        "type": "claim",
        "status": "pending",
        "date": "2026-01-01",
        "depends_on": [],
        "assumes": [],
        "attack_type": None,
        "falsified_by": None,
        "counterfactual": None,
    }
    f.write_text(serialise_frontmatter(meta) + "\n\n# Test Hypothesis\n")
    return research_dir


@pytest.fixture
def populated_research(research_dir):
    """Research dir with multiple nodes and edges for cascade testing.

    Creates:
    - assumption-a1 (assumption, pending)
    - h1-architect-r1-result (claim, active, assumes: [assumption-a1])
    - h1-experimenter-output (evidence, active, depends_on: [h1-architect-r1-result])
    """
    assume_dir = research_dir / "context" / "assumptions"
    assume_file = assume_dir / "assumption-a1.md"
    assume_file.write_text(
        serialise_frontmatter(
            {
                "id": "assumption-a1",
                "type": "assumption",
                "status": "pending",
                "date": "2026-01-01",
                "depends_on": [],
                "assumes": [],
                "attack_type": None,
                "falsified_by": None,
                "counterfactual": "If this is false, the entire approach fails",
            }
        )
        + "\n\n# Homogeneity Assumption\n"
    )

    architect_dir = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
    architect_dir.mkdir(parents=True)
    (architect_dir / "result.md").write_text(
        serialise_frontmatter(
            {
                "id": "h1-architect-r1-result",
                "type": "claim",
                "status": "active",
                "date": "2026-01-01",
                "depends_on": [],
                "assumes": ["assumption-a1"],
                "attack_type": None,
                "falsified_by": None,
                "counterfactual": None,
            }
        )
        + "\n\n# Bottleneck Hypothesis\n"
    )

    experimenter_dir = research_dir / "claims" / "claim-1-test" / "experimenter" / "results"
    experimenter_dir.mkdir(parents=True)
    (experimenter_dir / "output.md").write_text(
        serialise_frontmatter(
            {
                "id": "h1-experimenter-output",
                "type": "evidence",
                "status": "active",
                "date": "2026-01-02",
                "depends_on": ["h1-architect-r1-result"],
                "assumes": [],
                "attack_type": None,
                "falsified_by": None,
                "counterfactual": None,
            }
        )
        + "\n\n# Experiment Results\n"
    )

    return research_dir


# ---------------------------------------------------------------------------
# ResearchBuilder — fluent builder for test scenarios
# ---------------------------------------------------------------------------


class ResearchBuilder:
    """Fluent builder for constructing research directories in tests.

    Usage:
        root = (ResearchBuilder(tmp_path)
            .with_claim("c1", status="active", maturity="conjecture")
            .with_claim("c2", status="pending", depends_on=["c1"])
            .with_thinker_result("sub-1a", round_num=1)
            .with_refutor_result("sub-1a", round_num=1, severity="Fatal")
            .build())
    """

    def __init__(self, tmp_path: Path):
        self.root = tmp_path
        self._claims: list[dict[str, Any]] = []
        self._sub_units: list[str] = []
        self._files: list[tuple[str, str]] = []  # (rel_path, content)
        self._artifacts: list[dict[str, str]] = []

        # Create base structure
        for d in ["cycles", "context/assumptions", ".db"]:
            (self.root / d).mkdir(parents=True, exist_ok=True)
        init_paths(self.root)

    def with_cycle(self, name: str = "test") -> ResearchBuilder:
        """Scaffold a cycle directory."""
        cycles = self.root / "cycles"
        existing = [d.name for d in cycles.iterdir() if d.is_dir() and d.name.startswith("cycle-")]
        n = len(existing) + 1
        d = cycles / f"cycle-{n}-{name}"
        d.mkdir(exist_ok=True)
        (d / "frontier.md").write_text(
            f"---\nid: c{n}-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# {name.title()}\n"
        )
        return self

    def with_sub_unit(self, name: str = "direct", cycle: str | None = None) -> ResearchBuilder:
        """Scaffold a sub-unit with role directories."""
        if cycle is None:
            # Find the first (or only) cycle
            cycles = self.root / "cycles"
            cycle_dirs = sorted(d for d in cycles.iterdir() if d.is_dir())
            if not cycle_dirs:
                self.with_cycle()
                cycle_dirs = sorted(d for d in cycles.iterdir() if d.is_dir())
            cycle_dir = cycle_dirs[0]
        else:
            cycle_dir = self.root / cycle

        # Create unit if none exists
        unit_dirs = sorted(d for d in cycle_dir.iterdir() if d.is_dir() and d.name.startswith("unit-"))
        if not unit_dirs:
            unit_dir = cycle_dir / "unit-1-investigation"
            unit_dir.mkdir()
            (unit_dir / "frontier.md").write_text(
                "---\nid: u1-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Investigation\n"
            )
        else:
            unit_dir = unit_dirs[0]

        sub_dirs = sorted(d for d in unit_dir.iterdir() if d.is_dir() and d.name.startswith("sub-"))
        letter = chr(ord("a") + len(sub_dirs))
        sub_dir = unit_dir / f"sub-1{letter}-{name}"
        sub_dir.mkdir()
        (sub_dir / "frontier.md").write_text(
            f"---\nid: s1{letter}-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# {name.title()}\n"
        )
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (sub_dir / role).mkdir()
        self._sub_units.append(str(sub_dir.relative_to(self.root)))
        return self

    def with_claim(
        self,
        node_id: str,
        *,
        node_type: str = "claim",
        status: str = "pending",
        maturity: str | None = None,
        confidence: str | None = None,
        depends_on: list[str] | None = None,
        assumes: list[str] | None = None,
        location: str | None = None,
    ) -> ResearchBuilder:
        """Create a node file with specified attributes."""
        meta: dict[str, Any] = {
            "id": node_id,
            "type": node_type,
            "status": status,
            "date": "2026-01-01",
            "depends_on": depends_on or [],
            "assumes": assumes or [],
        }
        if maturity:
            meta["maturity"] = maturity
        if confidence:
            meta["confidence"] = confidence

        path = self.root / location if location else self.root / "context" / f"{node_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialise_frontmatter(meta) + f"\n\n# {node_id}\n")
        return self

    def with_architect_result(
        self, sub_unit: str | None = None, *, round_num: int = 1, content: str = "# Hypothesis\n\nProposal."
    ) -> ResearchBuilder:
        """Create an architect result file."""
        sub = self._resolve_sub_unit(sub_unit)
        path = self.root / sub / "architect" / f"round-{round_num}"
        path.mkdir(parents=True, exist_ok=True)
        (path / "result.md").write_text(
            f"---\nid: architect-r{round_num}\ntype: claim\nstatus: active\ndate: 2026-01-01\n"
            f"depends_on: []\nassumes: []\n---\n\n{content}"
        )
        return self

    # Alias for backward compat with existing tests
    with_thinker_result = with_architect_result

    def with_adversary_result(
        self,
        sub_unit: str | None = None,
        *,
        round_num: int = 1,
        severity: str = "Minor (worth noting)",
        content: str | None = None,
    ) -> ResearchBuilder:
        """Create an adversary result file with specified severity."""
        sub = self._resolve_sub_unit(sub_unit)
        path = self.root / sub / "adversary" / f"round-{round_num}"
        path.mkdir(parents=True, exist_ok=True)
        body = content or f"# Attack\n\nCritique.\n\n**Severity**: {severity}\n"
        (path / "result.md").write_text(
            f"---\nid: adversary-r{round_num}\ntype: claim\nstatus: active\ndate: 2026-01-01\n"
            f"depends_on: []\nassumes: []\n---\n\n{body}"
        )
        return self

    # Alias for backward compat with existing tests
    with_refutor_result = with_adversary_result

    def with_experimenter_result(
        self, sub_unit: str | None = None, *, content: str = "# Results\n\nAUROC: 0.85"
    ) -> ResearchBuilder:
        """Create an experimenter output file."""
        sub = self._resolve_sub_unit(sub_unit)
        path = self.root / sub / "experimenter" / "results"
        path.mkdir(parents=True, exist_ok=True)
        (path / "output.md").write_text(
            f"---\nid: experimenter-output\ntype: evidence\nstatus: active\ndate: 2026-01-01\n"
            f"depends_on: []\nassumes: []\n---\n\n{content}"
        )
        return self

    # Alias for backward compat with existing tests
    with_coder_result = with_experimenter_result

    def with_verdict(
        self, sub_unit: str | None = None, *, verdict: str = "PROVEN", confidence: str = "high"
    ) -> ResearchBuilder:
        """Create an arbiter verdict file."""
        sub = self._resolve_sub_unit(sub_unit)
        path = self.root / sub / "arbiter" / "results"
        path.mkdir(parents=True, exist_ok=True)
        (path / "verdict.md").write_text(
            f"---\nid: verdict\ntype: verdict\nstatus: active\ndate: 2026-01-01\n"
            f"depends_on: []\nassumes: []\n---\n\n# Verdict\n\n**Verdict**: {verdict}\n**Confidence**: {confidence}\n"
        )
        return self

    def with_artifact(
        self, artifact_id: str, name: str, artifact_type: str = "function", file_path: str = "coder/gen.py"
    ) -> ResearchBuilder:
        """Register a coder artifact."""
        self._artifacts.append({"id": artifact_id, "name": name, "type": artifact_type, "path": file_path})
        return self

    def build(self) -> Path:
        """Finalize the research directory and build the database."""
        build_db(force=True)
        # Register artifacts
        if self._artifacts:
            import sqlite3

            from manage import DB_PATH

            conn = sqlite3.connect(str(DB_PATH))
            for art in self._artifacts:
                conn.execute(
                    "INSERT OR REPLACE INTO coder_artifacts "
                    "(id, name, artifact_type, file_path, description, dependencies, created_by, created_at) "
                    "VALUES (?, ?, ?, ?, '', '', '', '2026-01-01')",
                    (art["id"], art["name"], art["type"], art["path"]),
                )
            conn.commit()
            conn.close()
        return self.root

    def _resolve_sub_unit(self, sub_unit: str | None) -> str:
        """Resolve a sub-unit path, using the last created one as default."""
        if sub_unit:
            return sub_unit
        if self._sub_units:
            return self._sub_units[-1]
        # Auto-create one
        self.with_cycle().with_sub_unit()
        return self._sub_units[-1]


@pytest.fixture
def research(tmp_path):
    """Fluent builder for research directories. Usage: research.with_cycle().with_claim(...).build()"""
    return ResearchBuilder(tmp_path)
