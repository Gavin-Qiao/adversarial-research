from db import (
    _find_cascade_targets,
    _parse_and_upsert,
    _update_frontmatter_in_file,
    build_db,
    discover_md_files,
    init_db,
)
from frontmatter import parse_frontmatter


class TestInitDb:
    def test_creates_tables(self, research_dir):
        conn = init_db()
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "nodes" in tables
        assert "edges" in tables
        assert "ledger" in tables

    def test_preserves_ledger(self, research_dir):
        conn = init_db()
        conn.execute(
            "INSERT INTO ledger (timestamp, event, node_id, details) VALUES (?, ?, ?, ?)",
            ("2026-01-01", "test", "node-1", "test entry"),
        )
        conn.commit()
        conn.close()
        # Rebuild
        conn2 = init_db()
        rows = conn2.execute("SELECT * FROM ledger").fetchall()
        assert len(rows) == 1
        assert rows[0]["event"] == "test"


class TestBuildDb:
    def test_empty(self, research_dir):
        conn = build_db()
        count = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        assert count == 0

    def test_with_files(self, sample_node):
        conn = build_db()
        count = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        assert count == 1
        node = conn.execute("SELECT * FROM nodes WHERE id = 'h1-architect-r1-result'").fetchone()
        assert node is not None
        assert node["type"] == "claim"
        assert node["status"] == "pending"

    def test_edges(self, populated_research):
        conn = build_db()
        edges = conn.execute("SELECT * FROM edges").fetchall()
        relations = {(e["source_id"], e["target_id"], e["relation"]) for e in edges}
        assert ("h1-architect-r1-result", "assumption-a1", "assumes") in relations
        assert ("h1-experimenter-output", "h1-architect-r1-result", "depends_on") in relations

    def test_with_legacy_cycle_files(self, research_dir):
        sub = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
        sub.mkdir(parents=True)
        (sub / "frontier.md").write_text(
            "---\nid: s1a-frontier\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Probe\n"
        )

        conn = build_db()
        node = conn.execute("SELECT * FROM nodes WHERE id = 's1a-frontier'").fetchone()
        assert node is not None
        assert node["file_path"] == "cycles/cycle-1/unit-1-test/sub-1a-probe/frontier.md"

    def test_missing_frontmatter(self, research_dir):
        """Files without frontmatter should use path-derived defaults."""
        path = research_dir / "claims" / "claim-1-test" / "experimenter" / "results"
        path.mkdir(parents=True)
        (path / "output.md").write_text("# No frontmatter here\n\nJust content.")
        conn = build_db()
        count = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        assert count == 1


class TestDiscoverMdFiles:
    def test_finds_in_claims(self, sample_node):
        files = discover_md_files()
        assert len(files) == 1
        assert files[0].name == "result.md"

    def test_finds_in_context(self, research_dir):
        (research_dir / "context" / "distillation-test.md").write_text("---\nid: test\n---\n")
        files = discover_md_files()
        assert len(files) == 1


class TestUpdateFrontmatter:
    def test_updates_status(self, sample_node):
        fpath = sample_node / "claims" / "claim-1-test" / "architect" / "round-1" / "result.md"
        result = _update_frontmatter_in_file(fpath, {"status": "proven"})
        assert result is True
        meta = parse_frontmatter(fpath.read_text())
        assert meta["status"] == "proven"

    def test_preserves_body(self, sample_node):
        fpath = sample_node / "claims" / "claim-1-test" / "architect" / "round-1" / "result.md"
        _update_frontmatter_in_file(fpath, {"status": "active"})
        text = fpath.read_text()
        assert "# Test Hypothesis" in text

    def test_missing_file(self, research_dir):
        fpath = research_dir / "nonexistent.md"
        result = _update_frontmatter_in_file(fpath, {"status": "active"})
        assert result is False


class TestBuildDbEdgeCases:
    def test_duplicate_ids_first_wins(self, research_dir, capsys):
        """When two files derive the same ID, the first one parsed wins and a warning is printed."""
        d1 = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        d1.mkdir(parents=True)
        (d1 / "result.md").write_text("---\nid: dupe\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# First\n")

        d2 = research_dir / "claims" / "claim-1-test" / "experimenter" / "results"
        d2.mkdir(parents=True)
        (d2 / "output.md").write_text(
            "---\nid: dupe\ntype: evidence\nstatus: active\ndate: 2026-01-02\n---\n\n# Second\n"
        )

        conn = build_db()
        rows = conn.execute("SELECT * FROM nodes WHERE id = 'dupe'").fetchall()
        assert len(rows) == 1
        # First file wins — type should be 'claim' from the first file, not 'evidence'
        assert rows[0]["type"] == "claim"
        err = capsys.readouterr().err
        assert "duplicate" in err.lower() or "ERROR" in err

    def test_duplicate_ids_remain_stable_across_incremental_builds(self, research_dir, capsys):
        """A second incremental build must not let the skipped duplicate overwrite the winner."""
        d1 = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        d1.mkdir(parents=True)
        (d1 / "result.md").write_text("---\nid: dupe\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# First\n")

        d2 = research_dir / "claims" / "claim-1-test" / "experimenter" / "results"
        d2.mkdir(parents=True)
        (d2 / "output.md").write_text(
            "---\nid: dupe\ntype: evidence\nstatus: active\ndate: 2026-01-02\n---\n\n# Second\n"
        )

        conn = build_db()
        row = conn.execute("SELECT type, file_path FROM nodes WHERE id = 'dupe'").fetchone()
        assert row["type"] == "claim"
        assert row["file_path"].endswith("architect/round-1/result.md")

        conn = build_db()
        row = conn.execute("SELECT type, file_path FROM nodes WHERE id = 'dupe'").fetchone()
        assert row["type"] == "claim"
        assert row["file_path"].endswith("architect/round-1/result.md")

        err = capsys.readouterr().err
        assert "forcing full rebuild" in err.lower()

    def test_non_scalar_id_falls_back_to_derived_id(self, research_dir, capsys):
        claim = research_dir / "claims" / "claim-1-bad-id"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: [oops]\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Bad ID\n"
        )

        conn = build_db()
        node = conn.execute(
            "SELECT id, file_path FROM nodes WHERE file_path = 'claims/claim-1-bad-id/claim.md'"
        ).fetchone()

        assert node is not None
        assert node["id"] == "h1-claim"
        err = capsys.readouterr().err
        assert "non-scalar" in err.lower() or "invalid id" in err.lower()

    def test_duplicate_scan_tolerates_non_scalar_id(self, research_dir, capsys):
        first = research_dir / "claims" / "claim-1-good"
        first.mkdir(parents=True)
        (first / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Good\n"
        )

        second = research_dir / "claims" / "claim-2-bad"
        second.mkdir(parents=True)
        (second / "claim.md").write_text(
            "---\nid: [oops]\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Bad\n"
        )

        conn = build_db()
        rows = conn.execute("SELECT id FROM nodes ORDER BY file_path").fetchall()

        assert [row["id"] for row in rows] == ["h1-claim", "h2-claim"]
        err = capsys.readouterr().err
        assert "traceback" not in err.lower()

    def test_non_scalar_status_falls_back_to_default(self, research_dir, capsys):
        claim = research_dir / "claims" / "claim-1-bad-status"
        claim.mkdir(parents=True)
        (claim / "claim.md").write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: [pending]\ndate: 2026-01-01\n---\n\n# Bad Status\n"
        )

        conn = build_db()
        node = conn.execute(
            "SELECT status, file_path FROM nodes WHERE file_path = 'claims/claim-1-bad-status/claim.md'"
        ).fetchone()

        assert node is not None
        assert node["status"] == "pending"
        err = capsys.readouterr().err
        assert "non-scalar" in err.lower()

    def test_incremental_build_removes_stale_row_when_file_becomes_invalid_utf8(self, research_dir, capsys):
        claim = research_dir / "claims" / "claim-1-test"
        claim.mkdir(parents=True)
        claim_file = claim / "claim.md"
        claim_file.write_text(
            "---\nid: h1-claim\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Claim\n"
        )

        conn = build_db(force=True)
        node = conn.execute("SELECT id FROM nodes WHERE file_path = 'claims/claim-1-test/claim.md'").fetchone()
        assert node is not None

        claim_file.write_bytes(
            b"---\nid: h1-claim\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# Claim\xff\n"
        )

        conn = build_db()
        node = conn.execute("SELECT id FROM nodes WHERE file_path = 'claims/claim-1-test/claim.md'").fetchone()
        assert node is None

        err = capsys.readouterr().err
        assert "not valid utf-8" in err.lower()

    def test_incremental_build_preserves_incoming_edges_when_file_becomes_invalid_utf8(self, research_dir):
        claim_a = research_dir / "claims" / "claim-1-a"
        claim_a.mkdir(parents=True)
        claim_a_file = claim_a / "claim.md"
        claim_a_file.write_text(
            "---\nid: a1\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# A\n"
        )

        claim_b = research_dir / "claims" / "claim-2-b"
        claim_b.mkdir(parents=True)
        (claim_b / "claim.md").write_text(
            "---\nid: b1\ntype: claim\nstatus: pending\ndate: 2026-01-01\n"
            "depends_on: [a1]\n---\n\n# B\n"
        )

        build_db(force=True)

        claim_a_file.write_bytes(
            b"---\nid: a1\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# A\xff\n"
        )

        conn = build_db()
        edges = conn.execute("SELECT source_id, target_id, relation FROM edges").fetchall()

        assert conn.execute("SELECT 1 FROM nodes WHERE id = 'a1'").fetchone() is None
        assert [tuple(row) for row in edges] == [("b1", "a1", "depends_on")]

    def test_incremental_build_preserves_orphan_edges_when_target_id_changes(self, research_dir):
        claim_a = research_dir / "claims" / "claim-1-a"
        claim_a.mkdir(parents=True)
        claim_a_file = claim_a / "claim.md"
        claim_a_file.write_text(
            "---\nid: a1\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# A\n"
        )

        claim_b = research_dir / "claims" / "claim-2-b"
        claim_b.mkdir(parents=True)
        (claim_b / "claim.md").write_text(
            "---\nid: b1\ntype: claim\nstatus: pending\ndate: 2026-01-01\n"
            "depends_on: [a1]\n---\n\n# B\n"
        )

        build_db(force=True)

        claim_a_file.write_text(
            "---\nid: a2\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n\n# A\n"
        )

        conn = build_db()
        edge_rows = conn.execute(
            "SELECT source_id, target_id, relation FROM edges ORDER BY source_id, target_id"
        ).fetchall()

        assert conn.execute("SELECT 1 FROM nodes WHERE id = 'a1'").fetchone() is None
        assert conn.execute("SELECT 1 FROM nodes WHERE id = 'a2'").fetchone() is not None
        assert [tuple(row) for row in edge_rows] == [("b1", "a1", "depends_on")]

    def test_frontmatter_only_no_body(self, research_dir):
        d = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        d.mkdir(parents=True)
        (d / "result.md").write_text("---\nid: no-body\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n")

        conn = build_db()
        node = conn.execute("SELECT * FROM nodes WHERE id = 'no-body'").fetchone()
        assert node is not None
        assert node["title"] is None

    def test_file_at_root_of_context(self, research_dir):
        (research_dir / "context" / "overview.md").write_text(
            "---\nid: overview\ntype: reference\nstatus: pending\ndate: 2026-01-01\n---\n\n# Overview\n"
        )
        conn = build_db()
        node = conn.execute("SELECT * FROM nodes WHERE id = 'overview'").fetchone()
        assert node is not None
        assert node["type"] == "reference"

    def test_self_referential_dependency(self, research_dir):
        """A node that depends_on itself should still be inserted (validate catches it)."""
        d = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        d.mkdir(parents=True)
        (d / "result.md").write_text(
            "---\nid: self-ref\ntype: claim\nstatus: pending\ndate: 2026-01-01\ndepends_on: [self-ref]\n---\n\n# Self\n"
        )
        conn = build_db()
        edges = conn.execute("SELECT * FROM edges WHERE source_id = 'self-ref' AND target_id = 'self-ref'").fetchall()
        assert len(edges) == 1  # edge stored; validation catches the cycle

    def test_dependency_on_nonexistent_node(self, research_dir):
        """Edges to non-existent nodes are stored (validate catches dangling refs)."""
        d = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        d.mkdir(parents=True)
        (d / "result.md").write_text(
            "---\nid: orphan-dep\ntype: claim\nstatus: pending\ndate: 2026-01-01\n"
            "depends_on: [does-not-exist]\n---\n\n# Orphan\n"
        )
        conn = build_db()
        edges = conn.execute("SELECT * FROM edges WHERE target_id = 'does-not-exist'").fetchall()
        assert len(edges) == 1


class TestDiscoverMdFilesEdgeCases:
    def test_nested_subdirectories(self, research_dir):
        deep = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        deep.mkdir(parents=True)
        (deep / "result.md").write_text("---\nid: deep\n---\n")
        files = discover_md_files()
        assert any(f.name == "result.md" for f in files)

    def test_non_md_files_ignored(self, research_dir):
        d = research_dir / "claims" / "claim-1-test"
        d.mkdir(parents=True)
        (d / "notes.txt").write_text("not markdown")
        (d / "data.json").write_text("{}")
        files = discover_md_files()
        assert len(files) == 0

    def test_empty_directories(self, research_dir):
        (research_dir / "claims" / "claim-1-test" / "empty").mkdir(parents=True)
        files = discover_md_files()
        assert len(files) == 0


class TestUpdateFrontmatterEdgeCases:
    def test_add_new_key(self, sample_node):
        fpath = sample_node / "claims" / "claim-1-test" / "architect" / "round-1" / "result.md"
        result = _update_frontmatter_in_file(fpath, {"maturity": "conjecture"})
        assert result is True
        meta = parse_frontmatter(fpath.read_text())
        assert meta["maturity"] == "conjecture"
        assert meta["status"] == "pending"  # original preserved

    def test_empty_updates_noop(self, sample_node):
        fpath = sample_node / "claims" / "claim-1-test" / "architect" / "round-1" / "result.md"
        _update_frontmatter_in_file(fpath, {})
        meta = parse_frontmatter(fpath.read_text())
        assert meta["status"] == "pending"

    def test_file_without_frontmatter_gets_one(self, research_dir):
        """A file with no frontmatter should get auto-generated frontmatter."""
        d = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        d.mkdir(parents=True)
        fpath = d / "result.md"
        fpath.write_text("# Just a heading\n\nNo frontmatter here.\n")
        result = _update_frontmatter_in_file(fpath, {"status": "active"})
        assert result is True
        meta = parse_frontmatter(fpath.read_text())
        assert meta["status"] == "active"
        assert "id" in meta  # auto-derived
        assert "# Just a heading" in fpath.read_text()  # body preserved


class TestParseAndUpsert:
    def test_basic_upsert(self, research_dir):
        d = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        d.mkdir(parents=True)
        fpath = d / "result.md"
        fpath.write_text("---\nid: test-node\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Title\n")
        conn = init_db()
        node_id = _parse_and_upsert(conn, fpath)
        conn.commit()
        assert node_id == "test-node"
        row = conn.execute("SELECT * FROM nodes WHERE id = 'test-node'").fetchone()
        assert row is not None
        assert row["title"] == "Title"

    def test_no_frontmatter_uses_defaults(self, research_dir):
        d = research_dir / "claims" / "claim-1-test" / "experimenter" / "results"
        d.mkdir(parents=True)
        fpath = d / "output.md"
        fpath.write_text("# No Frontmatter\n\nJust body content.\n")
        conn = init_db()
        node_id = _parse_and_upsert(conn, fpath)
        conn.commit()
        assert node_id is not None
        row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        assert row is not None
        assert row["status"] == "pending"  # default

    def test_edges_created(self, research_dir):
        d = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        d.mkdir(parents=True)
        fpath = d / "result.md"
        fpath.write_text(
            "---\nid: dep-node\ntype: claim\nstatus: active\ndate: 2026-01-01\n"
            "depends_on: [target-a]\nassumes: [assumption-b]\n---\n\n# Node\n"
        )
        conn = init_db()
        conn.execute("PRAGMA foreign_keys=OFF")  # targets don't exist as nodes
        _parse_and_upsert(conn, fpath)
        conn.commit()
        edges = conn.execute("SELECT * FROM edges WHERE source_id = 'dep-node'").fetchall()
        relations = {(e["target_id"], e["relation"]) for e in edges}
        assert ("target-a", "depends_on") in relations
        assert ("assumption-b", "assumes") in relations

    def test_id_collision_warns(self, research_dir, capsys):
        d1 = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        d1.mkdir(parents=True)
        (d1 / "result.md").write_text("---\nid: dupe\ntype: claim\nstatus: pending\ndate: 2026-01-01\n---\n")
        d2 = research_dir / "claims" / "claim-1-test" / "experimenter" / "results"
        d2.mkdir(parents=True)
        (d2 / "output.md").write_text("---\nid: dupe\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n")
        conn = init_db()
        seen: dict[str, str] = {}
        _parse_and_upsert(conn, d1 / "result.md", seen_ids=seen)
        _parse_and_upsert(conn, d2 / "output.md", seen_ids=seen)
        err = capsys.readouterr().err
        assert "duplicate" in err.lower()

    def test_unknown_keys_warn(self, research_dir, capsys):
        d = research_dir / "claims" / "claim-1-test" / "architect" / "round-1"
        d.mkdir(parents=True)
        fpath = d / "result.md"
        fpath.write_text("---\nid: test\ntype: claim\nstatus: active\ndate: 2026-01-01\nbogus_key: foo\n---\n")
        conn = init_db()
        _parse_and_upsert(conn, fpath)
        err = capsys.readouterr().err
        assert "unknown" in err.lower() or "Unknown" in err


class TestFindCascadeTargets:
    def _setup_graph(self, research_dir):
        """Create A -> B -> C dependency chain and return (conn, ids)."""
        conn = init_db()
        for nid, status in [("root", "active"), ("dep-1", "active"), ("dep-2", "active")]:
            conn.execute(
                "INSERT INTO nodes (id, type, status, date, file_path) VALUES (?, 'claim', ?, '2026-01-01', ?)",
                (nid, status, f"context/{nid}.md"),
            )
        conn.execute("INSERT INTO edges (source_id, target_id, relation) VALUES ('dep-1', 'root', 'depends_on')")
        conn.execute("INSERT INTO edges (source_id, target_id, relation) VALUES ('dep-2', 'dep-1', 'depends_on')")
        conn.commit()
        return conn

    def test_finds_transitive_dependents(self, research_dir):
        conn = self._setup_graph(research_dir)
        targets = _find_cascade_targets(conn, "root")
        ids = [t[0] for t in targets]
        assert "dep-1" in ids
        assert "dep-2" in ids

    def test_excludes_root_node(self, research_dir):
        conn = self._setup_graph(research_dir)
        targets = _find_cascade_targets(conn, "root")
        ids = [t[0] for t in targets]
        assert "root" not in ids

    def test_empty_when_no_dependents(self, research_dir):
        conn = self._setup_graph(research_dir)
        targets = _find_cascade_targets(conn, "dep-2")
        assert targets == []

    def test_cycle_does_not_infinite_loop(self, research_dir):
        """A -> B -> A cycle should terminate via visited set."""
        conn = init_db()
        for nid in ("a", "b"):
            conn.execute(
                "INSERT INTO nodes (id, type, status, date, file_path) VALUES (?, 'claim', 'active', '2026-01-01', ?)",
                (nid, f"context/{nid}.md"),
            )
        conn.execute("INSERT INTO edges (source_id, target_id, relation) VALUES ('b', 'a', 'depends_on')")
        conn.execute("INSERT INTO edges (source_id, target_id, relation) VALUES ('a', 'b', 'depends_on')")
        conn.commit()
        # Should not hang — visited set prevents infinite loop
        targets = _find_cascade_targets(conn, "a")
        ids = [t[0] for t in targets]
        assert "b" in ids
        assert len(ids) == 1  # only b, not a (root excluded)

    def test_three_node_cycle(self, research_dir):
        """A -> B -> C -> A cycle terminates correctly."""
        conn = init_db()
        for nid in ("x", "y", "z"):
            conn.execute(
                "INSERT INTO nodes (id, type, status, date, file_path) VALUES (?, 'claim', 'active', '2026-01-01', ?)",
                (nid, f"context/{nid}.md"),
            )
        conn.execute("INSERT INTO edges (source_id, target_id, relation) VALUES ('y', 'x', 'depends_on')")
        conn.execute("INSERT INTO edges (source_id, target_id, relation) VALUES ('z', 'y', 'depends_on')")
        conn.execute("INSERT INTO edges (source_id, target_id, relation) VALUES ('x', 'z', 'depends_on')")
        conn.commit()
        targets = _find_cascade_targets(conn, "x")
        ids = sorted(t[0] for t in targets)
        assert ids == ["y", "z"]
