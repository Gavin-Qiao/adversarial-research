from manage import _update_frontmatter_in_file, build_db, discover_md_files, init_db, parse_frontmatter


class TestInitDb:
    def test_creates_tables(self, research_dir):
        conn = init_db()
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "nodes" in tables
        assert "edges" in tables
        assert "ledger" in tables

    def test_preserves_ledger(self, research_dir):
        conn = init_db()
        conn.execute("INSERT INTO ledger VALUES ('2026-01-01', 'test', 'node-1', 'test entry')")
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
        node = conn.execute("SELECT * FROM nodes WHERE id = 'c1-u1-thinker-r1-result'").fetchone()
        assert node is not None
        assert node["type"] == "claim"
        assert node["status"] == "pending"

    def test_edges(self, populated_research):
        conn = build_db()
        edges = conn.execute("SELECT * FROM edges").fetchall()
        relations = {(e["source_id"], e["target_id"], e["relation"]) for e in edges}
        assert ("c1-u1-thinker-r1-result", "assumption-a1", "assumes") in relations
        assert ("c1-u1-coder-output", "c1-u1-thinker-r1-result", "depends_on") in relations

    def test_missing_frontmatter(self, research_dir):
        """Files without frontmatter should use path-derived defaults."""
        path = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "coder" / "results"
        path.mkdir(parents=True)
        (path / "output.md").write_text("# No frontmatter here\n\nJust content.")
        conn = build_db()
        count = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        assert count == 1


class TestDiscoverMdFiles:
    def test_finds_in_cycles(self, sample_node):
        files = discover_md_files()
        assert len(files) == 1
        assert files[0].name == "result.md"

    def test_finds_in_context(self, research_dir):
        (research_dir / "context" / "distillation-test.md").write_text("---\nid: test\n---\n")
        files = discover_md_files()
        assert len(files) == 1


class TestUpdateFrontmatter:
    def test_updates_status(self, sample_node):
        fpath = sample_node / "cycles" / "cycle-1" / "unit-1-test" / "thinker" / "round-1" / "result.md"
        result = _update_frontmatter_in_file(fpath, {"status": "settled"})
        assert result is True
        meta = parse_frontmatter(fpath.read_text())
        assert meta["status"] == "settled"

    def test_preserves_body(self, sample_node):
        fpath = sample_node / "cycles" / "cycle-1" / "unit-1-test" / "thinker" / "round-1" / "result.md"
        _update_frontmatter_in_file(fpath, {"status": "active"})
        text = fpath.read_text()
        assert "# Test Hypothesis" in text

    def test_missing_file(self, research_dir):
        fpath = research_dir / "nonexistent.md"
        result = _update_frontmatter_in_file(fpath, {"status": "active"})
        assert result is False
