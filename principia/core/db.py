"""Database layer: schema, migrations, build, discovery, cascade logic."""

from __future__ import annotations

import sqlite3
import sys
from collections import deque
from datetime import date
from pathlib import Path
from typing import Any

from . import config as _cfg
from .config import rel_path_from_root
from .frontmatter import (
    extract_title,
    get_body,
    get_scalar_frontmatter,
    parse_frontmatter,
    serialise_frontmatter,
)
from .ids import derive_id, infer_type_from_path

# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _workspace_root(root: Path | None = None) -> Path:
    if root is None:
        return _cfg.RESEARCH_DIR.resolve()
    return root.resolve()


def _workspace_context_dir(root: Path) -> Path:
    return root / "context"


def _workspace_db_path(root: Path) -> Path:
    return root / ".db" / "research.db"


def _workspace_rel_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def discover_md_files(root: Path | None = None) -> list[Path]:
    """Find all .md files under claims/, legacy cycles/, and context/."""
    research_root = _workspace_root(root)
    files = []
    for root_dir in (
        research_root / "claims",
        research_root / "cycles",
        _workspace_context_dir(research_root),
    ):
        if not root_dir.exists():
            continue
        for p in sorted(root_dir.rglob("*.md")):
            files.append(p)
    return files


def _find_duplicate_ids(files: list[Path], *, root: Path | None = None) -> list[tuple[str, str, str]]:
    """Return duplicate ID collisions as (id, first_rel, duplicate_rel).

    This scans current files directly so incremental builds can detect duplicate
    IDs even when one duplicate was skipped during a previous full rebuild and
    therefore never entered the file tracker.
    """
    research_root = _workspace_root(root)
    seen: dict[str, str] = {}
    duplicates: list[tuple[str, str, str]] = []

    for fpath in files:
        rel = _workspace_rel_path(research_root, fpath)
        try:
            text = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            # Let the normal parse path warn about unreadable files.
            continue
        meta = parse_frontmatter(text, filepath=rel)
        node_id = get_scalar_frontmatter(meta, "id", filepath=rel, warn=True) or derive_id(rel)
        if node_id in seen:
            duplicates.append((node_id, seen[node_id], rel))
        else:
            seen[node_id] = rel

    return duplicates


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


CURRENT_SCHEMA_VERSION = 4

SCHEMA_V1 = """\
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    date TEXT,
    file_path TEXT NOT NULL,
    title TEXT,
    counterfactual TEXT,
    attack_type TEXT
);
CREATE TABLE IF NOT EXISTS edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES nodes(id),
    FOREIGN KEY (target_id) REFERENCES nodes(id)
);
CREATE TABLE IF NOT EXISTS ledger (
    timestamp TEXT NOT NULL,
    event TEXT NOT NULL,
    node_id TEXT,
    details TEXT
);
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""

SCHEMA_V2_NEW_TABLES = """\
CREATE TABLE IF NOT EXISTS dispatches (
    timestamp TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    action TEXT NOT NULL,
    round INTEGER,
    details TEXT
);
CREATE TABLE IF NOT EXISTS coder_artifacts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    description TEXT,
    dependencies TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS file_tracker (
    file_path TEXT PRIMARY KEY,
    mtime REAL NOT NULL
);
"""


def _get_schema_version(conn: sqlite3.Connection) -> int:
    """Get the current schema version, or 0 if unversioned."""
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        return row["version"] if row else 0
    except sqlite3.OperationalError:
        return 0


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Set the schema version."""
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c["name"] == column for c in cols)


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Run migrations to bring DB to current schema version."""
    version = _get_schema_version(conn)

    if version < 1:
        conn.executescript(SCHEMA_V1)
        _set_schema_version(conn, 1)
        version = 1

    if version < 2:
        # Add new columns to nodes (skip if already present from a partial migration)
        for col, col_type in [
            ("maturity", "TEXT"),
            ("wave", "INTEGER"),
            ("cycle_status", "TEXT"),
            ("confidence", "TEXT"),
            ("file_mtime", "REAL"),
        ]:
            if not _has_column(conn, "nodes", col):
                conn.execute(f"ALTER TABLE nodes ADD COLUMN {col} {col_type}")
        conn.executescript(SCHEMA_V2_NEW_TABLES)
        _set_schema_version(conn, 2)
        version = 2

    if version < 3:
        if not _has_column(conn, "ledger", "agent"):
            conn.execute("ALTER TABLE ledger ADD COLUMN agent TEXT")
        _set_schema_version(conn, 3)

    if version < 4:
        for col in (
            "sub_unit TEXT",
            "dispatch_mode TEXT",
            "packet_path TEXT",
            "prompt_path TEXT",
            "result_path TEXT",
        ):
            col_name = col.split()[0]
            if not _has_column(conn, "dispatches", col_name):
                conn.execute(f"ALTER TABLE dispatches ADD COLUMN {col}")
        _set_schema_version(conn, 4)


def _get_or_create_db(root: Path | None = None) -> sqlite3.Connection:
    """Open (or create) the database and run migrations."""
    db_path = _workspace_db_path(_workspace_root(root))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate_db(conn)
    return conn


def init_db(root: Path | None = None) -> sqlite3.Connection:
    """Create a fresh database view for a full rebuild.

    This clears derived build state in-place so repeated rebuilds still work on
    Windows when another connection still has the database file open.
    Ledger, coder_artifacts, and dispatches are intentionally preserved.
    """
    conn = _get_or_create_db(root)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("DELETE FROM edges")
    conn.execute("DELETE FROM nodes")
    conn.execute("DELETE FROM file_tracker")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Command: build
# ---------------------------------------------------------------------------


KNOWN_FRONTMATTER_KEYS = {
    "id",
    "type",
    "status",
    "date",
    "depends_on",
    "assumes",
    "attack_type",
    "falsified_by",
    "counterfactual",
    "maturity",
    "confidence",
    "weakened_from_status",
    "weakened_from_confidence",
    "wave",
    "cycle_status",
    "falsification",
    "north_star_version",
}


def _scalar_meta(
    meta: dict[str, Any],
    key: str,
    *,
    rel: str,
    default: str | None = None,
) -> str | None:
    """Return a scalar frontmatter value, warning and falling back when invalid."""
    value = get_scalar_frontmatter(meta, key, filepath=rel, warn=True)
    if value is None:
        return default
    return value


def _parse_and_upsert(
    conn: sqlite3.Connection,
    fpath: Path,
    seen_ids: dict[str, str] | None = None,
    *,
    root: Path | None = None,
) -> str | None:
    """Parse a single markdown file and upsert its node + edges into the DB.

    Returns the node ID, or None if the file couldn't be parsed."""
    research_root = _workspace_root(root)
    rel = _workspace_rel_path(research_root, fpath)
    try:
        text = fpath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        print(f"  WARN: Skipping {rel} - not valid UTF-8", file=sys.stderr)
        return None

    meta = parse_frontmatter(text, filepath=rel)
    body = get_body(text)
    title = extract_title(body)
    mtime = fpath.stat().st_mtime

    # Warn if frontmatter is missing or empty
    if not meta:
        if text.lstrip().startswith("---"):
            print(f"  WARN: {rel} starts with --- but has no closing --- - frontmatter not parsed", file=sys.stderr)
        else:
            print(f"  WARN: No frontmatter in {rel} - using path-derived defaults", file=sys.stderr)
    else:
        unknown = set(meta.keys()) - KNOWN_FRONTMATTER_KEYS
        if unknown:
            print(f"  WARN: Unknown frontmatter keys in {rel}: {', '.join(sorted(unknown))}", file=sys.stderr)
        for k, v in meta.items():
            if isinstance(v, str) and "\n" in v:
                print(
                    f"  WARN: Multiline value in '{k}' of {rel} - only first line kept. "
                    f"All frontmatter values must be single-line.",
                    file=sys.stderr,
                )

    # Derive defaults
    today = date.today().isoformat()
    node_id = _scalar_meta(meta, "id", rel=rel) or derive_id(rel)
    node_type = _scalar_meta(meta, "type", rel=rel) or infer_type_from_path(rel)
    status = _scalar_meta(meta, "status", rel=rel) or "pending"
    node_date = _scalar_meta(meta, "date", rel=rel) or today
    counterfactual = _scalar_meta(meta, "counterfactual", rel=rel)
    attack_type = _scalar_meta(meta, "attack_type", rel=rel)
    maturity = _scalar_meta(meta, "maturity", rel=rel)
    confidence = _scalar_meta(meta, "confidence", rel=rel)
    wave = _scalar_meta(meta, "wave", rel=rel)
    cycle_status = _scalar_meta(meta, "cycle_status", rel=rel)

    if seen_ids is not None and node_id in seen_ids:
        print(
            f"  ERROR: Duplicate ID '{node_id}' - claimed by {seen_ids[node_id]} and {rel}. "
            f"Skipping {rel} (first file wins).",
            file=sys.stderr,
        )
        return node_id  # Skip — don't overwrite the first file
    if seen_ids is not None:
        seen_ids[node_id] = rel

    # Upsert node
    conn.execute(
        "INSERT OR REPLACE INTO nodes "
        "(id, type, status, date, file_path, title, counterfactual, attack_type, "
        "maturity, wave, cycle_status, confidence, file_mtime) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            node_id,
            node_type,
            status,
            node_date,
            rel,
            title,
            counterfactual,
            attack_type,
            maturity,
            wave,
            cycle_status,
            confidence,
            mtime,
        ),
    )

    # Remove old edges for this node (will re-add current ones)
    conn.execute("DELETE FROM edges WHERE source_id = ?", (node_id,))

    # Edges from depends_on
    for target in _ensure_list(meta.get("depends_on")):
        conn.execute(
            "INSERT INTO edges (source_id, target_id, relation) VALUES (?, ?, ?)", (node_id, target, "depends_on")
        )

    # Edges from assumes
    for target in _ensure_list(meta.get("assumes")):
        conn.execute(
            "INSERT INTO edges (source_id, target_id, relation) VALUES (?, ?, ?)", (node_id, target, "assumes")
        )

    # Edges from falsified_by
    fby = _scalar_meta(meta, "falsified_by", rel=rel)
    if fby:
        conn.execute(
            "INSERT INTO edges (source_id, target_id, relation) VALUES (?, ?, ?)", (node_id, fby, "falsified_by")
        )

    # Update file tracker
    conn.execute("INSERT OR REPLACE INTO file_tracker (file_path, mtime) VALUES (?, ?)", (rel, mtime))

    return node_id


def _ensure_list(val: Any) -> list[str]:
    """Normalize a value to a list of strings."""
    if not val:
        return []
    if isinstance(val, str):
        return [val]
    return list(val)


def _node_ids_for_file(conn: sqlite3.Connection, file_path: str) -> list[str]:
    """Return every node ID currently associated with a tracked source file."""
    return [row["id"] for row in conn.execute("SELECT id FROM nodes WHERE file_path = ?", (file_path,)).fetchall()]


def _delete_edges_for_node_ids(conn: sqlite3.Connection, column: str, node_ids: list[str]) -> None:
    """Delete edges whose source or target matches any node ID in *node_ids*."""
    if not node_ids:
        return
    placeholders = ", ".join("?" for _ in node_ids)
    conn.execute(f"DELETE FROM edges WHERE {column} IN ({placeholders})", node_ids)


def _clear_file_state(conn: sqlite3.Connection, file_path: str) -> list[str]:
    """Remove tracked DB state for a source file and return the prior node IDs.

    Incoming edges are intentionally preserved so incremental builds can keep
    dangling references visible when a target file is deleted, unreadable, or
    changes IDs. Validation then reports those orphaned edges explicitly.
    """
    old_ids = _node_ids_for_file(conn, file_path)
    _delete_edges_for_node_ids(conn, "source_id", old_ids)
    conn.execute("DELETE FROM nodes WHERE file_path = ?", (file_path,))
    conn.execute("DELETE FROM file_tracker WHERE file_path = ?", (file_path,))
    return old_ids


def _post_build_check(conn: sqlite3.Connection) -> None:
    """Lightweight integrity check after build. Warns on stderr, never fails."""
    orphans = conn.execute(
        "SELECT source_id, target_id, relation FROM edges "
        "WHERE source_id NOT IN (SELECT id FROM nodes) OR target_id NOT IN (SELECT id FROM nodes)"
    ).fetchall()
    if orphans:
        print(f"WARNING: {len(orphans)} orphan edge(s) found. Run 'validate' for details.", file=sys.stderr)
    loops = conn.execute("SELECT source_id FROM edges WHERE source_id = target_id").fetchall()
    if loops:
        print(f"WARNING: {len(loops)} self-loop(s) found. Run 'validate' for details.", file=sys.stderr)


def build_db(force: bool = False, root: Path | None = None) -> sqlite3.Connection:
    """Build the database. Incremental by default — only re-parses changed files.

    Args:
        force: If True, do a full rebuild (delete DB, recreate from scratch).
    """
    research_root = _workspace_root(root)
    db_path = _workspace_db_path(research_root)
    if force or not db_path.exists():
        conn = init_db(research_root)
        return _full_build(conn, research_root)

    conn = _get_or_create_db(research_root)

    # Check if file_tracker table exists (might be a v1 DB just migrated)
    try:
        conn.execute("SELECT 1 FROM file_tracker LIMIT 1")
    except sqlite3.OperationalError:
        # No file_tracker yet — do a full build
        return _full_build(conn)

    files = discover_md_files(research_root)
    duplicates = _find_duplicate_ids(files, root=research_root)
    if duplicates:
        print(
            f"WARNING: {len(duplicates)} duplicate ID collision(s) detected. "
            "Forcing full rebuild to preserve first-file-wins semantics.",
            file=sys.stderr,
        )
        conn.close()
        return build_db(force=True, root=research_root)

    tracked: dict[str, float] = {
        r["file_path"]: r["mtime"] for r in conn.execute("SELECT file_path, mtime FROM file_tracker").fetchall()
    }

    changed: list[Path] = []
    new_files: list[Path] = []
    unchanged = 0

    for fpath in files:
        rel = _workspace_rel_path(research_root, fpath)
        mtime = fpath.stat().st_mtime
        if rel not in tracked:
            new_files.append(fpath)
        elif mtime > tracked[rel]:
            changed.append(fpath)
        else:
            unchanged += 1

    conn.execute("PRAGMA foreign_keys=OFF")

    # Remove nodes for deleted files
    current_paths = {_workspace_rel_path(research_root, f) for f in files}
    deleted = 0
    for tracked_path in list(tracked.keys()):
        if tracked_path not in current_paths:
            _clear_file_state(conn, tracked_path)
            deleted += 1

    # Pre-populate seen_ids from unchanged nodes so incremental builds
    # still enforce first-wins duplicate-ID semantics.
    seen_ids: dict[str, str] = {}
    for row in conn.execute("SELECT id, file_path FROM nodes").fetchall():
        fp = row["file_path"]
        if fp in current_paths and fp not in {_workspace_rel_path(research_root, f) for f in changed + new_files}:
            seen_ids[row["id"]] = fp

    # Parse changed + new files while FK checks are deferred so references to
    # temporarily missing or permanently removed nodes remain queryable.
    for fpath in changed + new_files:
        rel = _workspace_rel_path(research_root, fpath)
        _clear_file_state(conn, rel)
        _parse_and_upsert(conn, fpath, seen_ids, root=research_root)
    conn.execute("PRAGMA foreign_keys=ON")

    conn.commit()
    total = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
    print(
        f"Built database: {total} nodes "
        f"({len(new_files)} new, {len(changed)} changed, {unchanged} unchanged, {deleted} deleted).",
        file=sys.stderr,
    )
    _post_build_check(conn)
    return conn


def _full_build(conn: sqlite3.Connection, root: Path | None = None) -> sqlite3.Connection:
    """Full rebuild: parse all files."""
    conn.execute("PRAGMA foreign_keys=OFF")
    research_root = _workspace_root(root)
    files = discover_md_files(research_root)
    seen_ids: dict[str, str] = {}
    for fpath in files:
        _parse_and_upsert(conn, fpath, seen_ids, root=research_root)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    total = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
    print(f"Built database: {total} nodes from {len(files)} files.", file=sys.stderr)
    _post_build_check(conn)
    return conn


# ---------------------------------------------------------------------------
# Frontmatter update
# ---------------------------------------------------------------------------


def _update_frontmatter_in_file(fpath: Path, updates: dict) -> bool:
    """Read a markdown file, update specific frontmatter keys, write back.
    Returns True on success, False on error (with message printed)."""
    if not fpath.exists():
        print(f"  ERROR: File not found: {fpath} - run 'build' to refresh DB", file=sys.stderr)
        return False
    try:
        text = fpath.read_text(encoding="utf-8")
    except PermissionError:
        print(f"  ERROR: Permission denied reading: {fpath}", file=sys.stderr)
        return False

    meta = parse_frontmatter(text, filepath=str(fpath))
    body = get_body(text)

    if not meta:
        # File had no frontmatter -- create one from scratch
        meta = {
            "id": derive_id(rel_path_from_root(fpath)),
            "type": infer_type_from_path(rel_path_from_root(fpath)),
            "status": "pending",
            "date": date.today().isoformat(),
            "depends_on": [],
            "assumes": [],
            "attack_type": None,
            "falsified_by": None,
            "counterfactual": None,
        }

    meta.update(updates)
    # Ensure blank line between frontmatter and body
    separator = "\n\n" if body and not body.startswith("\n") else "\n"
    new_text = serialise_frontmatter(meta) + separator + body
    try:
        _cfg._atomic_write(fpath, new_text)
    except PermissionError:
        print(f"  ERROR: Permission denied writing: {fpath}", file=sys.stderr)
        return False
    return True


# ---------------------------------------------------------------------------
# Cascade
# ---------------------------------------------------------------------------


def _find_cascade_targets(conn: sqlite3.Connection, node_id: str) -> list[tuple[str, str, str]]:
    """BFS to find all nodes transitively dependent on *node_id*.

    Returns a list of ``(dep_id, file_path, current_status)`` tuples for
    every node reachable through ``depends_on`` or ``assumes`` edges.
    """
    visited: set[str] = set()
    queue = deque([node_id])
    affected: list[tuple[str, str, str]] = []

    while queue:
        current = queue.popleft()
        dependents = conn.execute(
            "SELECT DISTINCT source_id FROM edges WHERE target_id = ? AND relation IN ('depends_on', 'assumes')",
            (current,),
        ).fetchall()
        for dep in dependents:
            dep_id = dep["source_id"]
            if dep_id not in visited and dep_id != node_id:
                visited.add(dep_id)
                dep_node = conn.execute("SELECT * FROM nodes WHERE id = ?", (dep_id,)).fetchone()
                if dep_node:
                    affected.append((dep_id, dep_node["file_path"], dep_node["status"]))
                    queue.append(dep_id)

    return affected
