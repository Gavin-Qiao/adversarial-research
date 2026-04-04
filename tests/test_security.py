import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)


def run_manage(research_dir, *args):
    """Run manage.py as subprocess and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "scripts/manage.py", "--root", str(research_dir), *list(args)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_PROJECT_ROOT)
    return result.returncode, result.stdout, result.stderr


class TestQuerySecurity:
    def test_rejects_insert(self, research_dir):
        rc, out, _ = run_manage(research_dir, "query", "INSERT INTO nodes VALUES ('x','x','x','x','x','x','x','x')")
        assert rc != 0
        assert "read-only" in out.lower() or "error" in out.lower()

    def test_rejects_drop(self, research_dir):
        rc, _out, _ = run_manage(research_dir, "query", "DROP TABLE nodes")
        assert rc != 0

    def test_rejects_update(self, research_dir):
        rc, _out, _ = run_manage(research_dir, "query", "UPDATE nodes SET status='x'")
        assert rc != 0

    def test_rejects_delete(self, research_dir):
        rc, _out, _ = run_manage(research_dir, "query", "DELETE FROM nodes")
        assert rc != 0

    def test_rejects_pragma_write(self, research_dir):
        rc, out, _ = run_manage(research_dir, "query", "PRAGMA writable_schema=ON")
        assert rc != 0
        assert "write" in out.lower() or "error" in out.lower()

    def test_allows_pragma_read(self, research_dir):
        rc, _out, _ = run_manage(research_dir, "query", "PRAGMA table_info(nodes)")
        assert rc == 0

    def test_allows_select(self, research_dir):
        rc, _out, _ = run_manage(research_dir, "query", "SELECT 1")
        assert rc == 0


class TestPathTraversal:
    def test_rejects_path_traversal(self, research_dir):
        rc, out, _ = run_manage(research_dir, "new", "../../etc/passwd")
        assert rc != 0
        assert "escapes" in out.lower() or "error" in out.lower()

    def test_rejects_absolute_path(self, research_dir):
        rc, _out, _ = run_manage(research_dir, "new", "/etc/passwd")
        assert rc != 0
