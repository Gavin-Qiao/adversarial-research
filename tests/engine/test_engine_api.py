import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import init_paths


def test_engine_import_and_root_binding(tmp_path: Path) -> None:
    from principia.api.engine import PrincipiaEngine

    (tmp_path / "claims").mkdir(parents=True)
    (tmp_path / "context" / "assumptions").mkdir(parents=True)
    (tmp_path / ".db").mkdir()
    init_paths(tmp_path)

    engine = PrincipiaEngine(root=tmp_path)

    assert engine.root == tmp_path
    assert engine.build()["node_count"] == 0


def test_engine_instances_stay_bound_to_their_own_roots(tmp_path: Path) -> None:
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
        "---\n"
        "id: h1-test\n"
        "type: claim\n"
        "status: active\n"
        "date: 2026-01-01\n"
        "---\n\n"
        "# Test claim\n",
        encoding="utf-8",
    )

    engine_a = PrincipiaEngine(root=root_a)
    engine_b = PrincipiaEngine(root=root_b)

    assert engine_a.build()["node_count"] == 1
    assert engine_b.build()["node_count"] == 0


def test_engine_relative_root_stays_bound_after_cwd_change(tmp_path: Path) -> None:
    from principia.api.engine import PrincipiaEngine

    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"

    for workspace in (workspace_a, workspace_b):
        design_root = workspace / "design"
        (design_root / "claims").mkdir(parents=True)
        (design_root / "context" / "assumptions").mkdir(parents=True)
        (design_root / ".db").mkdir()

    claim_dir = workspace_a / "design" / "claims" / "claim-1-test"
    claim_dir.mkdir(parents=True)
    (claim_dir / "claim.md").write_text(
        "---\n"
        "id: h1-test\n"
        "type: claim\n"
        "status: active\n"
        "date: 2026-01-01\n"
        "---\n\n"
        "# Test claim\n",
        encoding="utf-8",
    )

    old_cwd = Path.cwd()
    try:
        os.chdir(workspace_a)
        engine = PrincipiaEngine(root=Path("design"))
        assert engine.build()["node_count"] == 1

        os.chdir(workspace_b)
        assert engine.build()["node_count"] == 1
    finally:
        os.chdir(old_cwd)


def test_engine_instances_are_isolated_under_concurrent_use(tmp_path: Path) -> None:
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
        "---\n"
        "id: h1-test\n"
        "type: claim\n"
        "status: active\n"
        "date: 2026-01-01\n"
        "---\n\n"
        "# Test claim\n",
        encoding="utf-8",
    )

    engine_a = PrincipiaEngine(root=root_a)
    engine_b = PrincipiaEngine(root=root_b)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(engine_a.build)
        future_b = executor.submit(engine_b.build)

    assert future_a.result()["node_count"] == 1
    assert future_b.result()["node_count"] == 0
