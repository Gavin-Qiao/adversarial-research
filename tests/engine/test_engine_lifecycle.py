from __future__ import annotations


def test_engine_dashboard_returns_structured_data(research_dir) -> None:
    from principia.api.engine import PrincipiaEngine

    engine = PrincipiaEngine(root=research_dir)
    dashboard = engine.dashboard()

    assert set(dashboard.keys()) >= {"phase", "claims", "blocked", "last_verdict"}
