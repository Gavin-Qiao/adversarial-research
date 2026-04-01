"""Tests for DB v2 features: incremental builds, migrations, coder registry, ResearchBuilder."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from manage import (
    _get_or_create_db,
    _get_schema_version,
    _migrate_db,
    build_db,
    init_paths,
    serialise_frontmatter,
)


def _insert_artifact(
    conn: sqlite3.Connection,
    art_id: str,
    name: str,
    art_type: str,
    file_path: str,
    *,
    description: str = "",
    created_by: str = "",
) -> None:
    """Helper to insert a coder artifact."""
    conn.execute(
        "INSERT INTO coder_artifacts "
        "(id, name, artifact_type, file_path, description, "
        "dependencies, created_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, '', ?, '2026-01-01')",
        (art_id, name, art_type, file_path, description, created_by),
    )


# ---------------------------------------------------------------------------
# Schema migration tests
# ---------------------------------------------------------------------------


class TestMigrations:
    def test_fresh_db_gets_current_version(self, research_dir):
        conn = _get_or_create_db()
        assert _get_schema_version(conn) == 2

    def test_v2_has_new_tables(self, research_dir):
        conn = _get_or_create_db()
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "dispatches" in tables
        assert "coder_artifacts" in tables
        assert "file_tracker" in tables
        assert "schema_version" in tables

    def test_v2_nodes_has_new_columns(self, research_dir):
        conn = _get_or_create_db()
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(nodes)").fetchall()}
        assert "maturity" in cols
        assert "wave" in cols
        assert "cycle_status" in cols
        assert "confidence" in cols
        assert "file_mtime" in cols

    def test_migration_is_idempotent(self, research_dir):
        """Running migration twice should not error."""
        conn = _get_or_create_db()
        _migrate_db(conn)  # Run again
        assert _get_schema_version(conn) == 2

    def test_v1_to_v2_migration(self, tmp_path):
        """Create a v1-style DB and verify migration adds new columns."""
        db_dir = tmp_path / ".db"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "research.db"
        init_paths(tmp_path)

        # Create a bare v1 DB
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE nodes (id TEXT PRIMARY KEY, type TEXT NOT NULL, status TEXT NOT NULL,
                date TEXT, file_path TEXT NOT NULL, title TEXT, counterfactual TEXT, attack_type TEXT);
            CREATE TABLE edges (source_id TEXT NOT NULL, target_id TEXT NOT NULL, relation TEXT NOT NULL);
            CREATE TABLE ledger (timestamp TEXT NOT NULL, event TEXT NOT NULL, node_id TEXT, details TEXT);
            CREATE TABLE schema_version (version INTEGER NOT NULL);
            INSERT INTO schema_version VALUES (1);
            INSERT INTO nodes VALUES ('test', 'claim', 'pending', '2026-01-01', 'test.md', 'Test', NULL, NULL);
        """)
        conn.commit()
        conn.close()

        # Run migration
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        _migrate_db(conn)

        # Verify new columns exist
        assert _get_schema_version(conn) == 2
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(nodes)").fetchall()}
        assert "maturity" in cols
        assert "confidence" in cols

        # Verify existing data survived
        row = conn.execute("SELECT * FROM nodes WHERE id='test'").fetchone()
        assert row is not None
        assert row["status"] == "pending"
        conn.close()


# ---------------------------------------------------------------------------
# Incremental build tests
# ---------------------------------------------------------------------------


class TestIncrementalBuild:
    def _make_file(self, research_dir: Path, rel: str, node_id: str, status: str = "pending") -> None:
        path = research_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            serialise_frontmatter({"id": node_id, "type": "claim", "status": status, "date": "2026-01-01"})
            + "\n# Test\n"
        )

    def test_initial_build(self, research_dir):
        self._make_file(research_dir, "cycles/cycle-1/unit-1/thinker/round-1/result.md", "c1-u1-t-r1")
        conn = build_db(force=True)
        assert conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"] == 1

    def test_unchanged_files_not_reparsed(self, research_dir, capsys):
        self._make_file(research_dir, "cycles/cycle-1/unit-1/thinker/round-1/result.md", "c1-u1-t-r1")
        build_db(force=True)
        # Second build — nothing changed
        build_db()
        output = capsys.readouterr().out
        assert "0 new" in output
        assert "0 changed" in output
        assert "1 unchanged" in output

    def test_changed_file_reparsed(self, research_dir, capsys):
        path = research_dir / "cycles/cycle-1/unit-1/thinker/round-1/result.md"
        self._make_file(research_dir, "cycles/cycle-1/unit-1/thinker/round-1/result.md", "c1-u1-t-r1")
        build_db(force=True)
        # Modify the file (ensure mtime advances)
        time.sleep(0.1)
        path.write_text(
            serialise_frontmatter({"id": "c1-u1-t-r1", "type": "claim", "status": "active", "date": "2026-01-01"})
            + "\n# Updated\n"
        )
        build_db()
        output = capsys.readouterr().out
        assert "1 changed" in output
        # Verify the status was updated
        conn = _get_or_create_db()
        row = conn.execute("SELECT status FROM nodes WHERE id='c1-u1-t-r1'").fetchone()
        assert row["status"] == "active"

    def test_new_file_detected(self, research_dir, capsys):
        self._make_file(research_dir, "cycles/cycle-1/unit-1/thinker/round-1/result.md", "c1-u1-t-r1")
        build_db(force=True)
        # Add a new file
        self._make_file(research_dir, "cycles/cycle-1/unit-1/refutor/round-1/result.md", "c1-u1-r-r1")
        build_db()
        output = capsys.readouterr().out
        assert "1 new" in output
        conn = _get_or_create_db()
        assert conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"] == 2

    def test_deleted_file_removed(self, research_dir, capsys):
        self._make_file(research_dir, "cycles/cycle-1/unit-1/thinker/round-1/result.md", "c1-u1-t-r1")
        self._make_file(research_dir, "cycles/cycle-1/unit-1/refutor/round-1/result.md", "c1-u1-r-r1")
        build_db(force=True)
        # Delete one file
        (research_dir / "cycles/cycle-1/unit-1/refutor/round-1/result.md").unlink()
        build_db()
        output = capsys.readouterr().out
        assert "1 deleted" in output
        conn = _get_or_create_db()
        assert conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"] == 1

    def test_force_always_rebuilds(self, research_dir, capsys):
        self._make_file(research_dir, "cycles/cycle-1/unit-1/thinker/round-1/result.md", "c1-u1-t-r1")
        build_db(force=True)
        build_db(force=True)
        # Force should say "from N files" not "N unchanged"
        output = capsys.readouterr().out
        assert "from" in output


# ---------------------------------------------------------------------------
# Coder registry tests
# ---------------------------------------------------------------------------


class TestCoderRegistry:
    def test_register_and_query(self, research_dir):
        conn = _get_or_create_db()
        _insert_artifact(
            conn,
            "ring-gen",
            "Ring Generator",
            "function",
            "coder/gen.py",
            description="Generates rings",
            created_by="c1",
        )
        conn.commit()
        rows = conn.execute("SELECT * FROM coder_artifacts WHERE id='ring-gen'").fetchall()
        assert len(rows) == 1
        assert rows[0]["name"] == "Ring Generator"

    def test_artifacts_survive_rebuild(self, research_dir):
        """Coder artifacts should survive a full DB rebuild."""
        conn = _get_or_create_db()
        _insert_artifact(conn, "ring-gen", "Ring Generator", "function", "coder/gen.py")
        conn.commit()
        conn.close()
        # Force rebuild
        build_db(force=True)
        conn = _get_or_create_db()
        rows = conn.execute("SELECT * FROM coder_artifacts").fetchall()
        assert len(rows) == 1
        assert rows[0]["id"] == "ring-gen"


# ---------------------------------------------------------------------------
# ResearchBuilder tests
# ---------------------------------------------------------------------------


class TestResearchBuilder:
    def test_basic_build(self, research):
        root = research.build()
        assert (root / "cycles").exists()
        assert (root / ".db").exists()

    def test_with_cycle(self, research):
        root = research.with_cycle("enrichment").build()
        assert (root / "cycles" / "cycle-1-enrichment" / "frontier.md").exists()

    def test_with_sub_unit(self, research):
        root = research.with_cycle("test").with_sub_unit("direct").build()
        # Find the sub-unit
        sub_dirs = list((root / "cycles").rglob("sub-*"))
        assert len(sub_dirs) == 1
        for role in ("thinker", "refutor", "coder", "judge", "researcher"):
            assert (sub_dirs[0] / role).exists()

    def test_with_claim(self, research):
        research.with_claim("test-claim", maturity="conjecture", status="active").build()
        conn = _get_or_create_db()
        row = conn.execute("SELECT * FROM nodes WHERE id='test-claim'").fetchone()
        assert row is not None
        assert row["maturity"] == "conjecture"

    def test_with_debate_round(self, research):
        root = (
            research.with_cycle("test")
            .with_sub_unit("direct")
            .with_thinker_result(round_num=1)
            .with_refutor_result(round_num=1, severity="Fatal")
            .build()
        )
        # Verify files exist
        sub = next(iter((root / "cycles").rglob("sub-*")))
        assert (sub / "thinker" / "round-1" / "result.md").exists()
        assert (sub / "refutor" / "round-1" / "result.md").exists()
        # Verify severity is in the refutor output
        text = (sub / "refutor" / "round-1" / "result.md").read_text()
        assert "Fatal" in text

    def test_with_artifact(self, research):
        research.with_artifact("gen1", "Ring Generator").build()
        conn = _get_or_create_db()
        rows = conn.execute("SELECT * FROM coder_artifacts WHERE id='gen1'").fetchall()
        assert len(rows) == 1

    def test_chaining(self, research):
        """Test that the full fluent chain works."""
        (
            research.with_cycle("test")
            .with_sub_unit("approach-a")
            .with_thinker_result(round_num=1)
            .with_refutor_result(round_num=1, severity="Minor")
            .with_coder_result()
            .with_verdict(verdict="SETTLED")
            .with_artifact("bench1", "AUROC Benchmark", artifact_type="script")
            .build()
        )
        conn = _get_or_create_db()
        # Should have nodes from the files
        node_count = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        assert node_count > 0
        # Should have the artifact
        art_count = conn.execute("SELECT COUNT(*) as c FROM coder_artifacts").fetchone()["c"]
        assert art_count == 1


# ---------------------------------------------------------------------------
# New frontmatter fields tests
# ---------------------------------------------------------------------------


class TestNewFrontmatterFields:
    def test_maturity_persists(self, research_dir):
        path = research_dir / "cycles" / "cycle-1" / "frontier.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            "---\nid: c1\ntype: claim\nstatus: pending\ndate: 2026-01-01\n"
            "maturity: conjecture\nconfidence: moderate\n---\n\n# Test\n"
        )
        conn = build_db(force=True)
        row = conn.execute("SELECT maturity, confidence FROM nodes WHERE id='c1'").fetchone()
        assert row["maturity"] == "conjecture"
        assert row["confidence"] == "moderate"

    def test_wave_persists(self, research_dir):
        path = research_dir / "cycles" / "cycle-1" / "frontier.md"
        path.parent.mkdir(parents=True)
        path.write_text("---\nid: c1\ntype: claim\nstatus: pending\ndate: 2026-01-01\nwave: 1\n---\n\n# Test\n")
        conn = build_db(force=True)
        row = conn.execute("SELECT wave FROM nodes WHERE id='c1'").fetchone()
        assert row["wave"] is not None
