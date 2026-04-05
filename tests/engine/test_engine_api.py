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
