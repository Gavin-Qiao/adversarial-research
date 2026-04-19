from __future__ import annotations

from pathlib import Path


def test_engine_dashboard_returns_structured_data(research_dir) -> None:
    from principia.api.engine import PrincipiaEngine

    engine = PrincipiaEngine(root=research_dir)
    dashboard = engine.dashboard()

    assert set(dashboard.keys()) >= {
        "phase",
        "claims",
        "blocked",
        "last_verdict",
        "dispatch_overview",
        "operator_guidance",
    }
    assert "summary" in dashboard["operator_guidance"]
    assert "recommended_action" in dashboard["operator_guidance"]


def test_engine_validate_and_results_stay_bound_to_root(tmp_path: Path) -> None:
    from principia.api.engine import PrincipiaEngine

    root_a = tmp_path / "workspace-a"
    root_b = tmp_path / "workspace-b"

    for root in (root_a, root_b):
        (root / "claims").mkdir(parents=True)
        (root / "context" / "assumptions").mkdir(parents=True)
        (root / ".db").mkdir()

    claim_dir = root_a / "claims" / "claim-1-test"
    claim_dir.mkdir(parents=True)
    (claim_dir / "claim.md").write_text(
        "---\nid: h1-test\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Test claim\n",
        encoding="utf-8",
    )

    engine_a = PrincipiaEngine(root=root_a)
    engine_b = PrincipiaEngine(root=root_b)

    validation_a = engine_a.validate()
    validation_b = engine_b.validate()
    results_a = engine_a.results()
    results_b = engine_b.results()

    assert validation_a["valid"] is True
    assert validation_a["node_count"] == 1
    assert validation_b["valid"] is True
    assert validation_b["node_count"] == 0
    assert results_a["results_path"] == str(root_a / "RESULTS.md")
    assert results_b["results_path"] == str(root_b / "RESULTS.md")
    assert results_a["exists"] is True
    assert results_b["exists"] is True
    assert results_a["results_summary"]["claim_count"] == 0
    assert results_b["results_summary"]["claim_count"] == 0
    assert "topline" in results_a["results_summary"]
    assert "open_claim_count" in results_a["results_summary"]
    assert "confidence_counts" in results_a["results_summary"]
    assert "limitation_preview" in results_a["results_summary"]


def test_engine_visualize_generates_workspace_bound_explorer(tmp_path: Path) -> None:
    from principia.api.engine import PrincipiaEngine

    root = tmp_path / "workspace"
    claim_dir = root / "claims" / "claim-1-test"
    (root / "context" / "assumptions").mkdir(parents=True)
    (root / ".db").mkdir(parents=True)
    claim_dir.mkdir(parents=True)
    (claim_dir / "claim.md").write_text(
        "---\nid: h1-claim\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test claim\n\nA live summary.\n",
        encoding="utf-8",
    )
    for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
        (claim_dir / role).mkdir()

    engine = PrincipiaEngine(root=root)
    result = engine.visualize()

    assert result["html_path"] == str(root / "WORKSPACE_EXPLORER.html")
    assert result["json_path"] == str(root / "WORKSPACE_EXPLORER.json")
    assert result["claim_count"] == 1
    assert Path(result["html_path"]).exists()
    assert Path(result["json_path"]).exists()
