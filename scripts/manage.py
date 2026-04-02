#!/usr/bin/env python3
"""
Principia — design management system for algorithm design from first principles.

User-facing commands:
    scaffold <level> <name> Create claim/cycle/unit/sub-unit structure
    status                  Auto-generate PROGRESS.md
    validate                Check referential integrity
    query <sql>             Query the evidence database
    list [--type] [--status] Browse claims and evidence
    results                 Generate RESULTS.md summary
    cascade <id>            Preview impact of disproving a claim
    settle <id>             Mark a claim as proven
    falsify <id> [--by id]  Mark a claim as disproven and cascade

Internal commands (used by skills and agents):
    build, new, next, context, prompt, waves, investigate-next,
    parse-framework, register, artifacts, codebook, post-verdict,
    log-dispatch, dispatch-log, assumptions
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
import textwrap
from collections import defaultdict, deque
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from frontmatter import (
    _FM_RE as _FM_RE,
)
from frontmatter import (
    _parse_yaml_value as _parse_yaml_value,
)
from frontmatter import (
    _yaml_val as _yaml_val,
)
from frontmatter import (
    extract_title,
    get_body,
    parse_frontmatter,
    readable_id,
    serialise_frontmatter,
)

# ---------------------------------------------------------------------------
# Paths (set by init_paths(), called from main())
# ---------------------------------------------------------------------------

RESEARCH_DIR: Path = Path(".")
DB_PATH: Path = Path(".")
CYCLES_DIR: Path = Path(".")
CONTEXT_DIR: Path = Path(".")
PROGRESS_PATH: Path = Path(".")
FOUNDATIONS_PATH: Path = Path(".")


def init_paths(root: Path) -> None:
    """Configure all path globals from the given research root directory."""
    global RESEARCH_DIR, DB_PATH, CYCLES_DIR, CONTEXT_DIR, PROGRESS_PATH, FOUNDATIONS_PATH
    RESEARCH_DIR = root.resolve()
    db_dir = RESEARCH_DIR / ".db"
    db_dir.mkdir(parents=True, exist_ok=True)
    DB_PATH = db_dir / "research.db"
    CYCLES_DIR = RESEARCH_DIR / "cycles"
    CONTEXT_DIR = RESEARCH_DIR / "context"
    PROGRESS_PATH = RESEARCH_DIR / "PROGRESS.md"
    FOUNDATIONS_PATH = RESEARCH_DIR / "FOUNDATIONS.md"


def _emit_progress(
    phase: str,
    step: str,
    detail: str = "",
    total: int | None = None,
    current: int | None = None,
) -> None:
    """Emit structured progress to stderr for skill-level reporting."""
    progress: dict[str, Any] = {"type": "progress", "phase": phase, "step": step}
    if detail:
        progress["detail"] = detail
    if total is not None:
        progress["total"] = total
        progress["current"] = current
    print(json.dumps(progress), file=sys.stderr)


def _atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to path atomically via temp file + os.replace().

    Writes to a temporary file in the same directory, then uses
    os.replace() which is atomic on the same filesystem.  If the write
    or rename fails, the temp file is cleaned up and the original file
    is left intact.
    """
    fd = None
    tmp_path: Path | None = None
    try:
        fd = tempfile.NamedTemporaryFile(  # noqa: SIM115
            mode="w",
            encoding=encoding,
            dir=path.parent,
            suffix=".tmp",
            delete=False,
        )
        tmp_path = Path(fd.name)
        fd.write(content)
        fd.flush()
        os.fsync(fd.fileno())
        fd.close()
        fd = None
        os.replace(tmp_path, path)
    except BaseException:
        if fd is not None:
            fd.close()
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = {
    "pending", "active",
    "proven", "disproven", "partial", "weakened", "inconclusive",  # principia names
    "settled", "falsified", "mixed", "undermined",                 # legacy aliases
}
VALID_TYPES = {"claim", "assumption", "evidence", "reference", "verdict", "question"}
VALID_ATTACK_TYPES = {"undermines", "rebuts", "undercuts", None}
VALID_MATURITIES = {"theorem-backed", "supported", "conjecture", "experiment", None}
VALID_CONFIDENCES = {"high", "moderate", "low", None}
VALID_CYCLE_STATUSES = {"not-started", "in-progress", "complete", None}

# Role name mapping: new names (principia) → legacy names for backward compat
ROLE_ALIASES = {
    "architect": "thinker",
    "adversary": "refutor",
    "experimenter": "coder",
    "scout": "researcher",
    "arbiter": "judge",
    "synthesizer": "deep-thinker",
}
# Reverse: legacy → principia
ROLE_ALIASES_REV = {v: k for k, v in ROLE_ALIASES.items()}

ROLE_TYPE_MAP = {
    # Principia names
    "architect": "claim",
    "adversary": "claim",
    "experimenter": "evidence",
    "scout": "reference",
    "arbiter": "verdict",
    "synthesizer": "claim",
    # Legacy names (still supported)
    "thinker": "claim",
    "refutor": "claim",
    "coder": "evidence",
    "researcher": "reference",
    "judge": "verdict",
    "deep-thinker": "claim",
}

# Status mapping: principia ↔ legacy
STATUS_ALIASES = {
    "proven": "settled",
    "disproven": "falsified",
    "partial": "mixed",
    "weakened": "undermined",
}
STATUS_ALIASES_REV = {v: k for k, v in STATUS_ALIASES.items()}

# Verdict mapping: principia ↔ legacy
VERDICT_ALIASES = {
    "PROVEN": "SETTLED",
    "DISPROVEN": "FALSIFIED",
    "PARTIAL": "MIXED",
}
VERDICT_ALIASES_REV = {v: k for k, v in VERDICT_ALIASES.items()}

# ---------------------------------------------------------------------------
# Frontmatter parser/serialiser — see frontmatter.py
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ID derivation from relative path
# ---------------------------------------------------------------------------

_ABBREV_PATTERNS = [
    (re.compile(r"^cycles/"), ""),
    (re.compile(r"cycle-(\d+)"), r"c\1"),
    (re.compile(r"unit-(\d+)-[a-z0-9_-]+"), r"u\1"),
    (re.compile(r"sub-(\d+[a-z])-[a-z0-9_-]+"), r"s\1"),
    (re.compile(r"round-(\d+)"), r"r\1"),
]


def derive_id(rel_path: str) -> str:
    """Derive a short ID from a path relative to research/."""
    # Remove file extension
    p = rel_path
    if p.endswith(".md"):
        p = p[:-3]
    # Strip leading directory prefixes
    p = re.sub(r"^cycles/", "", p)
    p = re.sub(r"^claims/", "", p)
    p = re.sub(r"^context/", "", p)
    # Apply abbreviations
    parts = p.split("/")
    result = []
    for part in parts:
        t = part
        # cycle-N or cycle-N-name -> cN
        t = re.sub(r"^cycle-(\d+)(?:-[a-z0-9_-]+)?$", r"c\1", t)
        # claim-N or claim-N-name -> hN (hypothesis)
        t = re.sub(r"^claim-(\d+)(?:-[a-z0-9_-]+)?$", r"h\1", t)
        # unit-M-name -> uM
        t = re.sub(r"^unit-(\d+)-[a-z0-9_-]+$", r"u\1", t)
        # sub-Ma-name -> sMa
        t = re.sub(r"^sub-(\d+[a-z])-[a-z0-9_-]+$", r"s\1", t)
        # round-N -> rN
        t = re.sub(r"^round-(\d+)$", r"r\1", t)
        # Drop bare prompts/ and results/ directory names
        if t in ("prompts", "results"):
            continue
        result.append(t)
    return "-".join(result)


def infer_type_from_path(rel_path: str) -> str:
    """Infer the node type from the role directory in the path."""
    parts = rel_path.split("/")
    # Assumption files
    if "assumptions" in parts:
        return "assumption"
    # Role-based inference, with prompt vs result distinction
    _prompt_roles = {
        "thinker", "refutor", "deep-thinker", "researcher",  # legacy
        "architect", "adversary", "synthesizer", "scout",     # principia
    }
    for role in ROLE_TYPE_MAP:
        if role in parts:
            basename = os.path.basename(rel_path)
            if basename == "prompt.md" and role in _prompt_roles:
                return "question"
            return ROLE_TYPE_MAP[role]
    # frontier/claim files
    basename = os.path.basename(rel_path)
    if basename in ("frontier.md", "claim.md"):
        return "verdict"
    return "reference"


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def discover_md_files() -> list[Path]:
    """Find all .md files under cycles/, claims/, and context/."""
    files = []
    claims_dir = RESEARCH_DIR / "claims"
    for root_dir in (CYCLES_DIR, claims_dir, CONTEXT_DIR):
        if not root_dir.exists():
            continue
        for p in sorted(root_dir.rglob("*.md")):
            files.append(p)
    return files


def rel_path_from_root(p: Path) -> str:
    """Return path relative to the research root."""
    return str(p.relative_to(RESEARCH_DIR))


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


CURRENT_SCHEMA_VERSION = 2

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


def _get_or_create_db() -> sqlite3.Connection:
    """Open (or create) the database and run migrations."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate_db(conn)
    return conn


def init_db() -> sqlite3.Connection:
    """Create a fresh database (full rebuild). Preserves ledger, coder_artifacts, and dispatches."""
    preserved_ledger: list[tuple] = []
    preserved_artifacts: list[tuple] = []
    preserved_dispatches: list[tuple] = []
    if DB_PATH.exists():
        try:
            old = sqlite3.connect(str(DB_PATH))
            old.row_factory = sqlite3.Row
            preserved_ledger = [
                (r["timestamp"], r["event"], r["node_id"], r["details"])
                for r in old.execute("SELECT * FROM ledger").fetchall()
            ]
            if _get_schema_version(old) >= 2:
                preserved_artifacts = [tuple(r) for r in old.execute("SELECT * FROM coder_artifacts").fetchall()]
                preserved_dispatches = [
                    (r["timestamp"], r["cycle_id"], r["agent"], r["action"], r["round"], r["details"])
                    for r in old.execute("SELECT * FROM dispatches").fetchall()
                ]
            old.close()
        except Exception:
            pass
        DB_PATH.unlink()

    conn = _get_or_create_db()

    if preserved_ledger:
        conn.executemany(
            "INSERT INTO ledger (timestamp, event, node_id, details) VALUES (?, ?, ?, ?)",
            preserved_ledger,
        )
    if preserved_artifacts:
        cols = "id, name, artifact_type, file_path, description, dependencies, created_by, created_at"
        placeholders = ", ".join("?" for _ in cols.split(", "))
        conn.executemany(
            f"INSERT OR IGNORE INTO coder_artifacts ({cols}) VALUES ({placeholders})",
            preserved_artifacts,
        )
    if preserved_dispatches:
        conn.executemany(
            "INSERT INTO dispatches (timestamp, cycle_id, agent, action, round, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            preserved_dispatches,
        )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Command: new
# ---------------------------------------------------------------------------


def cmd_new(args: argparse.Namespace) -> None:
    """Create a new markdown file with auto-generated frontmatter."""
    rel = args.path
    if os.path.isabs(rel):
        print(f"ERROR: Path must be relative (got absolute: {rel})")
        sys.exit(1)
    # Ensure it ends with .md
    if not rel.endswith(".md"):
        rel += ".md"
        print(f"  (appended .md → {rel})")
    full = (RESEARCH_DIR / rel).resolve()
    # Prevent path traversal outside research/
    if not str(full).startswith(str(RESEARCH_DIR.resolve())):
        print(f"ERROR: Path escapes research directory: {rel}")
        sys.exit(1)
    if full.exists():
        print(f"ERROR: File already exists: {full}")
        sys.exit(1)

    node_id = derive_id(rel)
    node_type = infer_type_from_path(rel)
    today = date.today().isoformat()

    meta: dict[str, str | list[str] | None] = {
        "id": node_id,
        "type": node_type,
        "status": "pending",
        "date": today,
        "depends_on": [],
        "assumes": [],
        "attack_type": None,
        "falsified_by": None,
        "counterfactual": None,
    }

    content = serialise_frontmatter(meta) + "\n\n<!-- Content goes here -->\n"

    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    print(f"Created: {full}")
    print(f"     ID: {node_id}")
    print(f"   Type: {node_type}")


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
    "wave",
    "cycle_status",
}


def _parse_and_upsert(conn: sqlite3.Connection, fpath: Path, seen_ids: dict[str, str] | None = None) -> str | None:
    """Parse a single markdown file and upsert its node + edges into the DB.

    Returns the node ID, or None if the file couldn't be parsed."""
    rel = rel_path_from_root(fpath)
    try:
        text = fpath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        print(f"  WARN: Skipping {rel} — not valid UTF-8", file=sys.stderr)
        return None

    meta = parse_frontmatter(text, filepath=rel)
    body = get_body(text)
    title = extract_title(body)
    mtime = fpath.stat().st_mtime

    # Warn if frontmatter is missing or empty
    if not meta:
        if text.lstrip().startswith("---"):
            print(f"  WARN: {rel} starts with --- but has no closing --- — frontmatter not parsed", file=sys.stderr)
        else:
            print(f"  WARN: No frontmatter in {rel} — using path-derived defaults", file=sys.stderr)
    else:
        unknown = set(meta.keys()) - KNOWN_FRONTMATTER_KEYS
        if unknown:
            print(f"  WARN: Unknown frontmatter keys in {rel}: {', '.join(sorted(unknown))}", file=sys.stderr)
        for k, v in meta.items():
            if isinstance(v, str) and "\n" in v:
                print(
                    f"  WARN: Multiline value in '{k}' of {rel} — only first line kept. "
                    f"All frontmatter values must be single-line.",
                    file=sys.stderr,
                )

    # Derive defaults
    today = date.today().isoformat()
    node_id = meta.get("id") or derive_id(rel)
    node_type = meta.get("type") or infer_type_from_path(rel)
    status = meta.get("status", "pending")
    node_date = meta.get("date", today)
    counterfactual = meta.get("counterfactual")
    attack_type = meta.get("attack_type")
    maturity = meta.get("maturity")
    confidence = meta.get("confidence")
    wave = meta.get("wave")
    cycle_status = meta.get("cycle_status")

    if seen_ids is not None and node_id in seen_ids:
        print(
            f"  WARN: ID collision — '{node_id}' claimed by both {seen_ids[node_id]} and {rel} (last one wins)",
            file=sys.stderr,
        )
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
    fby = meta.get("falsified_by")
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


def build_db(force: bool = False) -> sqlite3.Connection:
    """Build the database. Incremental by default — only re-parses changed files.

    Args:
        force: If True, do a full rebuild (delete DB, recreate from scratch).
    """
    if force or not DB_PATH.exists():
        conn = init_db()
        return _full_build(conn)

    conn = _get_or_create_db()

    # Check if file_tracker table exists (might be a v1 DB just migrated)
    try:
        conn.execute("SELECT 1 FROM file_tracker LIMIT 1")
    except sqlite3.OperationalError:
        # No file_tracker yet — do a full build
        return _full_build(conn)

    files = discover_md_files()
    tracked: dict[str, float] = {
        r["file_path"]: r["mtime"] for r in conn.execute("SELECT file_path, mtime FROM file_tracker").fetchall()
    }

    changed: list[Path] = []
    new_files: list[Path] = []
    unchanged = 0

    for fpath in files:
        rel = rel_path_from_root(fpath)
        mtime = fpath.stat().st_mtime
        if rel not in tracked:
            new_files.append(fpath)
        elif mtime > tracked[rel]:
            changed.append(fpath)
        else:
            unchanged += 1

    # Remove nodes for deleted files
    current_paths = {rel_path_from_root(f) for f in files}
    deleted = 0
    for tracked_path in list(tracked.keys()):
        if tracked_path not in current_paths:
            conn.execute(
                "DELETE FROM edges WHERE source_id IN (SELECT id FROM nodes WHERE file_path = ?)",
                (tracked_path,),
            )
            conn.execute("DELETE FROM nodes WHERE file_path = ?", (tracked_path,))
            conn.execute("DELETE FROM file_tracker WHERE file_path = ?", (tracked_path,))
            deleted += 1

    # Parse changed + new files (defer FK checks — edges may reference nodes from unchanged files)
    conn.execute("PRAGMA foreign_keys=OFF")
    seen_ids: dict[str, str] = {}
    for fpath in changed + new_files:
        _parse_and_upsert(conn, fpath, seen_ids)
    conn.execute("PRAGMA foreign_keys=ON")

    conn.commit()
    total = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
    print(
        f"Built database: {total} nodes "
        f"({len(new_files)} new, {len(changed)} changed, {unchanged} unchanged, {deleted} deleted).",
        file=sys.stderr,
    )
    return conn


def _full_build(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Full rebuild: parse all files."""
    conn.execute("PRAGMA foreign_keys=OFF")
    files = discover_md_files()
    seen_ids: dict[str, str] = {}
    for fpath in files:
        _parse_and_upsert(conn, fpath, seen_ids)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    total = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
    print(f"Built database: {total} nodes from {len(files)} files.", file=sys.stderr)
    return conn


def cmd_build(args: argparse.Namespace) -> None:
    build_db(force=True)


# ---------------------------------------------------------------------------
# Command: validate
# ---------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> None:
    """Run integrity checks on the database."""
    conn = build_db()  # Always rebuild for freshness
    errors = []

    # Check for duplicate IDs (shouldn't happen with PRIMARY KEY, but check source files)
    rows = conn.execute("SELECT id, COUNT(*) as cnt FROM nodes GROUP BY id HAVING cnt > 1").fetchall()
    for r in rows:
        errors.append(f"Duplicate ID: {r['id']} appears {r['cnt']} times")

    # Check required fields
    for row in conn.execute("SELECT * FROM nodes").fetchall():
        nid = row["id"]
        fp = row["file_path"]
        if not nid:
            errors.append(f"Missing ID in {fp}")
        if not row["type"]:
            errors.append(f"Missing type for {nid} ({fp})")
        if not row["status"]:
            errors.append(f"Missing status for {nid} ({fp})")
        if not row["date"]:
            errors.append(f"Missing date for {nid} ({fp})")
        if not fp:
            errors.append(f"Missing file_path for {nid}")

        # Valid status
        if row["status"] and row["status"] not in VALID_STATUSES:
            errors.append(f"Invalid status '{row['status']}' for {nid} ({fp})")

        # Valid type
        if row["type"] and row["type"] not in VALID_TYPES:
            errors.append(f"Invalid type '{row['type']}' for {nid} ({fp})")

        # Valid attack_type
        if row["attack_type"] and row["attack_type"] not in VALID_ATTACK_TYPES:
            errors.append(f"Invalid attack_type '{row['attack_type']}' for {nid} ({fp})")

        # Valid cycle_status
        if row["cycle_status"] and row["cycle_status"] not in VALID_CYCLE_STATUSES:
            errors.append(f"Invalid cycle_status '{row['cycle_status']}' for {nid} ({fp})")

    # Check for self-loops
    self_loops = conn.execute("SELECT source_id, relation FROM edges WHERE source_id = target_id").fetchall()
    for sl in self_loops:
        errors.append(f"Self-loop: '{sl['source_id']}' depends on itself (relation={sl['relation']})")

    # Check referential integrity: edges point to existing nodes
    all_ids = {r["id"] for r in conn.execute("SELECT id FROM nodes").fetchall()}

    # Check for cycles (DFS with coloring: 0=white, 1=gray, 2=black)
    adj: dict[str, list[str]] = defaultdict(list)
    for edge in conn.execute(
        "SELECT source_id, target_id FROM edges WHERE relation IN ('depends_on', 'assumes')"
    ).fetchall():
        adj[edge["source_id"]].append(edge["target_id"])
    color: dict[str, int] = {nid: 0 for nid in all_ids}

    def _dfs_cycle(node: str, path: list[str]) -> list[str] | None:
        color[node] = 1  # gray — in current path
        for neighbor in adj.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == 1:  # back edge → cycle
                cycle_start = path.index(neighbor)
                return [*path[cycle_start:], neighbor]
            if color[neighbor] == 0:
                result = _dfs_cycle(neighbor, [*path, neighbor])
                if result:
                    return result
        color[node] = 2  # black — done
        return None

    for nid in all_ids:
        if color.get(nid, 0) == 0:
            cycle = _dfs_cycle(nid, [nid])
            if cycle:
                errors.append(f"Dependency cycle: {' → '.join(cycle)}")
                break  # one cycle is enough to flag

    for edge in conn.execute("SELECT * FROM edges").fetchall():
        if edge["source_id"] not in all_ids:
            errors.append(f"Edge references unknown source '{edge['source_id']}' (relation={edge['relation']})")
        if edge["target_id"] not in all_ids:
            errors.append(
                f"Edge from '{edge['source_id']}' references unknown target '{edge['target_id']}' "
                f"(relation={edge['relation']})"
            )

    if getattr(args, "json", False):
        result = {
            "valid": len(errors) == 0,
            "error_count": len(errors),
            "errors": errors,
        }
        if not errors:
            result["node_count"] = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
            result["edge_count"] = conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
        print(json.dumps(result, indent=2))
        if errors:
            sys.exit(1)
        return

    if errors:
        print(f"VALIDATION FAILED: {len(errors)} error(s)\n")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        node_count = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        edge_count = conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
        print(f"Validation passed: {node_count} nodes, {edge_count} edges, 0 errors.")


# ---------------------------------------------------------------------------
# Command: falsify
# ---------------------------------------------------------------------------


def _update_frontmatter_in_file(fpath: Path, updates: dict) -> bool:
    """Read a markdown file, update specific frontmatter keys, write back.
    Returns True on success, False on error (with message printed)."""
    if not fpath.exists():
        print(f"  ERROR: File not found: {fpath} — run 'build' to refresh DB", file=sys.stderr)
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
        _atomic_write(fpath, new_text)
    except PermissionError:
        print(f"  ERROR: Permission denied writing: {fpath}", file=sys.stderr)
        return False
    return True


def _find_cascade_targets(
    conn: sqlite3.Connection, node_id: str
) -> list[tuple[str, str, str]]:
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
            "SELECT DISTINCT source_id FROM edges "
            "WHERE target_id = ? AND relation IN ('depends_on', 'assumes')",
            (current,),
        ).fetchall()
        for dep in dependents:
            dep_id = dep["source_id"]
            if dep_id not in visited and dep_id != node_id:
                visited.add(dep_id)
                dep_node = conn.execute(
                    "SELECT * FROM nodes WHERE id = ?", (dep_id,)
                ).fetchone()
                if dep_node:
                    affected.append((dep_id, dep_node["file_path"], dep_node["status"]))
                    queue.append(dep_id)

    return affected


def cmd_falsify(args: argparse.Namespace) -> None:
    """Mark a node as falsified and cascade to dependents."""
    conn = build_db()  # Always rebuild for freshness
    node_id = args.id
    evidence_id = args.by
    dry_run = getattr(args, "dry_run", False)
    force = getattr(args, "force", False)

    # Check node exists
    node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    if not node:
        print(f"ERROR: Node '{node_id}' not found.")
        sys.exit(1)

    if node["status"] in ("falsified", "disproven"):
        print(f"WARN: Node '{node_id}' is already disproven — skipping.")
        return

    # Find cascade targets
    affected = _find_cascade_targets(conn, node_id)
    non_disproven = [(d, f, s) for d, f, s in affected if s not in ("falsified", "disproven")]

    # --dry-run: preview only
    if dry_run:
        print(f"Dry-run: would disprove '{node_id}' ({node['file_path']})")
        if evidence_id:
            print(f"      By: {evidence_id}")
        if non_disproven:
            print(f"\nWould weaken {len(non_disproven)} dependent node(s):")
            for dep_id, fp, status in affected:
                marker = " (already disproven)" if status in ("falsified", "disproven") else ""
                print(f"  {dep_id}  ({fp})  status={status}{marker}")
        else:
            print("No dependents would be affected.")
        return

    # Confirmation (unless --force or non-interactive)
    if not force and non_disproven and sys.stdin.isatty():
        print(f"About to disprove '{node_id}' and cascade to {len(non_disproven)} dependent(s):")
        for dep_id, fp, _status in non_disproven:
            print(f"  {dep_id}  ({fp})")
        answer = input("\nProceed? (y/N) ").strip().lower()
        if answer != "y":
            print("Aborted.")
            return

    changes: list[tuple[str, str, str]] = []

    # Mark the node itself as disproven
    fpath = RESEARCH_DIR / node["file_path"]
    updates: dict[str, Any] = {"status": "disproven"}
    if evidence_id:
        updates["falsified_by"] = evidence_id
    if not _update_frontmatter_in_file(fpath, updates):
        print(f"ERROR: Could not update file for '{node_id}' — aborting.")
        sys.exit(1)
    changes.append((node_id, node["file_path"], "disproven"))

    conn.execute("UPDATE nodes SET status = 'disproven' WHERE id = ?", (node_id,))
    if evidence_id:
        existing = conn.execute(
            "SELECT 1 FROM edges WHERE source_id = ? AND target_id = ? AND relation = 'falsified_by'",
            (node_id, evidence_id),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO edges (source_id, target_id, relation) VALUES (?, ?, ?)",
                (node_id, evidence_id, "falsified_by"),
            )

    # Apply cascade to dependents — weaken them
    from orchestration import attenuate_confidence

    for dep_id, dep_fp, dep_status in affected:
        if dep_status not in ("falsified", "disproven"):
            dep_fpath = RESEARCH_DIR / dep_fp
            dep_node = conn.execute("SELECT * FROM nodes WHERE id = ?", (dep_id,)).fetchone()
            new_conf = attenuate_confidence(dep_node["confidence"] if dep_node else None)
            cascade_updates: dict[str, Any] = {"status": "weakened", "confidence": new_conf}
            if _update_frontmatter_in_file(dep_fpath, cascade_updates):
                conn.execute(
                    "UPDATE nodes SET status = 'weakened', confidence = ? WHERE id = ?",
                    (new_conf, dep_id),
                )
                changes.append((dep_id, dep_fp, "weakened"))

    # Ledger entries
    today = date.today().isoformat()
    for nid, _fp, new_status in changes:
        event = "disproven" if new_status == "disproven" else "weakened"
        detail = f"Set to {new_status}"
        if new_status == "disproven" and evidence_id:
            detail += f" by {evidence_id}"
        conn.execute(
            "INSERT INTO ledger (timestamp, event, node_id, details) VALUES (?, ?, ?, ?)",
            (today, event, nid, detail),
        )

    try:
        conn.commit()
    except sqlite3.Error as exc:
        print(f"ERROR: DB commit failed: {exc}. Files were updated; run 'build' to resync DB.", file=sys.stderr)
        sys.exit(1)

    print(f"Disproven: {node_id}")
    if evidence_id:
        print(f"      By: {evidence_id}")
    if len(changes) > 1:
        print(f"\nCascade ({len(changes) - 1} dependent(s) weakened):")
        for nid, fp, status in changes[1:]:
            print(f"  {nid}  ({fp})  -> {status}")
    else:
        print("No dependents affected.")


# ---------------------------------------------------------------------------
# Command: settle
# ---------------------------------------------------------------------------


def cmd_settle(args: argparse.Namespace) -> None:
    """Mark a node as settled."""
    conn = build_db()  # Always rebuild for freshness
    node_id = args.id

    # Check node exists
    node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    if not node:
        print(f"ERROR: Node '{node_id}' not found.")
        sys.exit(1)

    if node["status"] in ("settled", "proven"):
        print(f"WARN: Node '{node_id}' is already proven — skipping.")
        return

    if node["status"] in ("falsified", "disproven"):
        print(f"ERROR: Node '{node_id}' is disproven — cannot prove a disproven node.")
        sys.exit(1)

    # Mark the node as proven
    fpath = RESEARCH_DIR / node["file_path"]
    if not _update_frontmatter_in_file(fpath, {"status": "proven"}):
        print(f"ERROR: Could not update file for '{node_id}' — aborting.")
        sys.exit(1)

    conn.execute("UPDATE nodes SET status = 'proven' WHERE id = ?", (node_id,))

    # Ledger entry
    today = date.today().isoformat()
    conn.execute(
        "INSERT INTO ledger (timestamp, event, node_id, details) VALUES (?, ?, ?, ?)",
        (today, "proven", node_id, "Set to proven"),
    )
    conn.commit()

    print(f"Settled: {node_id}")
    print(f"   File: {node['file_path']}")


# ---------------------------------------------------------------------------
# Command: post-verdict (automated reviewer replacement)
# ---------------------------------------------------------------------------


def cmd_post_verdict(args: argparse.Namespace) -> None:
    """Automate post-verdict bookkeeping (replaces reviewer LLM dispatch)."""
    from orchestration import extract_confidence, extract_verdict, load_config

    config = load_config(DEFAULT_ORCH_CONFIG)
    sub_path = args.path
    target = RESEARCH_DIR / sub_path

    # Support both principia (arbiter/) and legacy (judge/) directories
    verdict_file = target / "arbiter" / "results" / "verdict.md"
    if not verdict_file.exists():
        verdict_file = target / "judge" / "results" / "verdict.md"
    if not verdict_file.exists():
        print(f"ERROR: No verdict file found in {target}")
        sys.exit(1)

    verdict = extract_verdict(verdict_file, config)
    confidence = extract_confidence(verdict_file)

    if verdict == "UNKNOWN":
        print("ERROR: Could not parse verdict from verdict file.")
        sys.exit(1)

    _emit_progress("recording", "post_verdict", f"{sub_path}: {verdict} ({confidence})")

    conn = build_db()
    changes: list[str] = []

    # Determine the claim node ID from the sub-unit frontier
    frontier = target / "frontier.md"
    node_id: str | None = None
    if frontier.exists():
        meta = parse_frontmatter(frontier.read_text(encoding="utf-8"))
        node_id = meta.get("id")  # type: ignore[assignment]

    # Apply verdict (extract_verdict now returns principia names: PROVEN, DISPROVEN, PARTIAL)
    if verdict == "PROVEN" and node_id:
        node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if node and node["status"] not in ("settled", "proven", "falsified", "disproven"):
            _update_frontmatter_in_file(frontier, {"status": "proven"})
            conn.execute("UPDATE nodes SET status = 'proven' WHERE id = ?", (node_id,))
            changes.append(f"Proven: {node_id}")

    elif verdict == "DISPROVEN" and node_id:
        node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if node and node["status"] not in ("falsified", "disproven"):
            verdict_id = derive_id(str(verdict_file.relative_to(RESEARCH_DIR)))
            _update_frontmatter_in_file(frontier, {"status": "disproven", "falsified_by": verdict_id})
            conn.execute("UPDATE nodes SET status = 'disproven' WHERE id = ?", (node_id,))
            changes.append(f"Disproven: {node_id} by {verdict_id}")
            # Cascade — weaken dependents
            cascade_targets = _find_cascade_targets(conn, node_id)
            from orchestration import attenuate_confidence

            for dep_id, dep_fp, dep_status in cascade_targets:
                if dep_status not in ("falsified", "disproven"):
                    dep_fpath = RESEARCH_DIR / dep_fp
                    dep_node = conn.execute("SELECT * FROM nodes WHERE id = ?", (dep_id,)).fetchone()
                    new_conf = attenuate_confidence(dep_node["confidence"] if dep_node else None)
                    if _update_frontmatter_in_file(dep_fpath, {"status": "weakened", "confidence": new_conf}):
                        conn.execute(
                            "UPDATE nodes SET status = 'weakened', confidence = ? WHERE id = ?",
                            (new_conf, dep_id),
                        )
                        changes.append(f"Weakened: {dep_id}")

    elif verdict in ("PARTIAL", "INCONCLUSIVE") and node_id:
        new_status = "partial" if verdict == "PARTIAL" else "inconclusive"
        _update_frontmatter_in_file(frontier, {"status": new_status})
        conn.execute("UPDATE nodes SET status = ? WHERE id = ?", (new_status, node_id))
        changes.append(f"Updated {node_id} to {new_status}")

    # Ledger entry
    today = date.today().isoformat()
    conn.execute(
        "INSERT INTO ledger (timestamp, event, node_id, details) VALUES (?, ?, ?, ?)",
        (today, "post_verdict", node_id or "unknown", f"Verdict: {verdict}, Confidence: {confidence}"),
    )
    try:
        conn.commit()
    except sqlite3.Error as exc:
        print(f"ERROR: DB commit failed: {exc}. Files were updated; run 'build' to resync DB.", file=sys.stderr)
        sys.exit(1)

    # Write marker file signaling post-verdict bookkeeping is done
    marker = target / ".post_verdict_done"
    _atomic_write(marker, today)

    result = {
        "verdict": verdict,
        "confidence": confidence,
        "node_id": node_id,
        "changes": changes,
    }
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Command: cascade (dry-run)
# ---------------------------------------------------------------------------


def cmd_cascade(args: argparse.Namespace) -> None:
    """Dry-run: show what would be affected if a node were falsified."""
    conn = build_db()  # Always rebuild for freshness
    node_id = args.id

    node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    if not node:
        print(f"ERROR: Node '{node_id}' not found.")
        sys.exit(1)

    affected = _find_cascade_targets(conn, node_id)

    print(f"Cascade analysis for: {node_id}")
    print(f"  Current status: {node['status']}")
    print(f"  File: {node['file_path']}")
    print()

    if affected:
        print(f"Would set {len(affected)} node(s) to 'undermined':")
        for dep_id, fp, status in affected:
            rel = conn.execute(
                "SELECT relation FROM edges WHERE source_id = ? AND target_id = ?",
                (dep_id, node_id),
            ).fetchone()
            rel_str = rel["relation"] if rel else "transitive"
            print(f"  {dep_id:40s}  status={status:12s}  via={rel_str}")
            print(f"    {fp}")
    else:
        print("No nodes would be affected.")


# ---------------------------------------------------------------------------
# Command: scaffold
# ---------------------------------------------------------------------------


def cmd_scaffold(args: argparse.Namespace) -> None:
    """Create directory structure for a cycle, unit, or sub-unit."""
    level = args.level
    name = args.name
    parent = args.parent

    # Validate name is a slug
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", name):
        print(f"ERROR: Name must be a lowercase slug (letters, digits, hyphens): got '{name}'")
        sys.exit(1)

    if level == "cycle":
        base = CYCLES_DIR
        if not base.exists():
            base.mkdir(parents=True)
        # Auto-number: count existing cycle-* dirs
        existing = sorted(d.name for d in base.iterdir() if d.is_dir() and d.name.startswith("cycle-"))
        next_num = len(existing) + 1
        dir_name = f"cycle-{next_num}-{name}"
        target = base / dir_name

    elif level == "unit":
        if not parent:
            print("ERROR: --parent is required for 'unit'. Provide the cycle path (e.g., cycles/cycle-1-enrichment).")
            sys.exit(1)
        base = (RESEARCH_DIR / parent).resolve()
        if not str(base).startswith(str(RESEARCH_DIR.resolve())):
            print("ERROR: Parent path escapes the research directory.")
            sys.exit(1)
        if not base.exists():
            print(f"ERROR: Parent directory does not exist: {base}")
            sys.exit(1)
        existing = sorted(d.name for d in base.iterdir() if d.is_dir() and d.name.startswith("unit-"))
        next_num = len(existing) + 1
        dir_name = f"unit-{next_num}-{name}"
        target = base / dir_name

    elif level == "sub-unit":
        if not parent:
            print("ERROR: --parent is required for 'sub-unit'. Provide the unit path.")
            sys.exit(1)
        base = (RESEARCH_DIR / parent).resolve()
        if not str(base).startswith(str(RESEARCH_DIR.resolve())):
            print("ERROR: Parent path escapes the research directory.")
            sys.exit(1)
        if not base.exists():
            print(f"ERROR: Parent directory does not exist: {base}")
            sys.exit(1)
        existing = sorted(d.name for d in base.iterdir() if d.is_dir() and d.name.startswith("sub-"))
        # Derive letter suffix: count existing → a, b, c, ..., z, aa, ab, ...
        parent_unit_match = re.search(r"unit-(\d+)", parent)
        unit_num = parent_unit_match.group(1) if parent_unit_match else "1"
        next_idx = len(existing)
        if next_idx < 26:
            letter = chr(ord("a") + next_idx)
        else:
            letter = chr(ord("a") + (next_idx // 26) - 1) + chr(ord("a") + (next_idx % 26))
        dir_name = f"sub-{unit_num}{letter}-{name}"
        target = base / dir_name

    elif level == "claim":
        # Flat hierarchy: claims/claim-N-name/ — no unit/sub-unit nesting
        base = RESEARCH_DIR / "claims"
        if not base.exists():
            base.mkdir(parents=True)
        existing = sorted(d.name for d in base.iterdir() if d.is_dir() and d.name.startswith("claim-"))
        next_num = len(existing) + 1
        dir_name = f"claim-{next_num}-{name}"
        target = base / dir_name

    else:
        print(f"ERROR: Unknown level '{level}'.")
        sys.exit(1)

    if target.exists():
        print(f"ERROR: Directory already exists: {target}")
        sys.exit(1)

    # Create the directory
    target.mkdir(parents=True)

    _emit_progress("scaffolding", f"scaffold_{level}", name)

    # Create frontier.md (claim.md for flat claims) with frontmatter
    frontier_name = "claim.md" if level == "claim" else "frontier.md"
    frontier = target / frontier_name
    rel = rel_path_from_root(frontier)
    node_id = derive_id(rel)
    today = date.today().isoformat()
    meta: dict[str, str | list[str] | None] = {
        "id": node_id,
        "type": "verdict",
        "status": "pending",
        "date": today,
        "depends_on": [],
        "assumes": [],
        "attack_type": None,
        "falsified_by": None,
        "counterfactual": None,
    }
    content = serialise_frontmatter(meta) + "\n\n# " + name.replace("-", " ").title() + "\n"
    frontier.write_text(content, encoding="utf-8")
    print(f"Created: {target}")
    print(f"  {frontier_name} (id: {node_id})")

    # For sub-units and claims, create role directories
    if level in ("sub-unit", "claim"):
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (target / role).mkdir()
            print(f"  {role}/")


# ---------------------------------------------------------------------------
# Command: status -> PROGRESS.md
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> None:
    """Auto-generate PROGRESS.md from the DB."""
    conn = build_db()  # Always rebuild for freshness

    lines = [
        "# Design Progress",
        "",
        "> Auto-generated by `manage.py status`. Do not edit manually.",
        "",
    ]

    # --- Current blockers ---
    # Active nodes that have dependents still pending
    blockers = conn.execute("""
        SELECT n.id, n.file_path, n.title,
               COUNT(DISTINCT e.source_id) as blocked_count
        FROM nodes n
        JOIN edges e ON e.target_id = n.id AND e.relation = 'depends_on'
        JOIN nodes dep ON dep.id = e.source_id AND dep.status = 'pending'
        WHERE n.status = 'active'
        GROUP BY n.id
        ORDER BY blocked_count DESC
    """).fetchall()

    lines.append("## Current blockers")
    lines.append("")
    if blockers:
        for b in blockers:
            title = b["title"] or readable_id(b["id"])
            lines.append(f"- **{title}** (`{b['id']}`) -- blocks {b['blocked_count']} pending node(s)")
            lines.append(f"  File: {b['file_path']}")
    else:
        # Fallback: any active node
        active = conn.execute("SELECT * FROM nodes WHERE status = 'active' ORDER BY date").fetchall()
        if active:
            for a in active:
                title = a["title"] or readable_id(a["id"])
                lines.append(f"- **{title}** (`{a['id']}`)")
                lines.append(f"  File: {a['file_path']}")
        else:
            lines.append("No active blockers.")
    lines.append("")

    # --- Settled ---
    lines.append("## What is settled")
    lines.append("")
    settled = conn.execute("SELECT * FROM nodes WHERE status = 'settled' ORDER BY file_path").fetchall()
    if settled:
        # Group by cycle
        by_cycle = defaultdict(list)
        for s in settled:
            parts = s["file_path"].split("/")
            cycle = "unknown"
            for p in parts:
                if p.startswith("cycle-"):
                    cycle = p
                    break
            by_cycle[cycle].append(s)
        for cycle in sorted(by_cycle):
            lines.append(f"### {cycle}")
            lines.append("")
            lines.append("| Decision | Source |")
            lines.append("|----------|--------|")
            for s in by_cycle[cycle]:
                title = s["title"] or readable_id(s["id"])
                lines.append(f"| {title} | `{s['id']}` |")
            lines.append("")
    else:
        lines.append("Nothing settled yet.")
        lines.append("")

    # --- Falsified ---
    lines.append("## What is falsified")
    lines.append("")
    falsified = conn.execute(
        "SELECT n.*, e.target_id as evidence_id "
        "FROM nodes n "
        "LEFT JOIN edges e ON e.source_id = n.id AND e.relation = 'falsified_by' "
        "WHERE n.status = 'falsified' "
        "ORDER BY n.file_path"
    ).fetchall()
    if falsified:
        lines.append("| Node | File | Falsified by |")
        lines.append("|------|------|-------------|")
        for f in falsified:
            title = f["title"] or readable_id(f["id"])
            eby = f["evidence_id"] or "--"
            lines.append(f"| {title} | `{f['file_path']}` | `{eby}` |")
        lines.append("")
    else:
        lines.append("Nothing falsified.")
        lines.append("")

    # --- Assumptions ---
    lines.append("## Assumptions")
    lines.append("")
    assumptions = conn.execute("SELECT * FROM nodes WHERE type = 'assumption' ORDER BY date").fetchall()
    if assumptions:
        lines.append("| ID | Status | Dependents |")
        lines.append("|----|--------|------------|")
        for a in assumptions:
            dep_count = conn.execute(
                "SELECT COUNT(*) as c FROM edges WHERE target_id = ? AND relation = 'assumes'",
                (a["id"],),
            ).fetchone()["c"]
            lines.append(f"| `{a['id']}` | {a['status']} | {dep_count} |")
        lines.append("")
    else:
        lines.append("No assumptions registered.")
        lines.append("")

    # --- Cycle log ---
    lines.append("## Cycle log")
    lines.append("")
    # Build a tree of cycles > units > sub-units from file paths
    cycle_nodes = conn.execute("SELECT * FROM nodes WHERE file_path LIKE 'cycles/%' ORDER BY file_path").fetchall()

    # Organize hierarchically
    def _make_sub() -> dict[str, Any]:
        return {"frontier": None, "nodes": []}

    def _make_unit() -> dict[str, Any]:
        return {"frontier": None, "subs": defaultdict(_make_sub)}

    cycles: dict[str, Any] = defaultdict(lambda: {"frontier": None, "units": defaultdict(_make_unit)})

    for n in cycle_nodes:
        parts = n["file_path"].split("/")
        # parts: cycles / cycle-N / ...
        if len(parts) < 2:
            continue
        cycle_name = parts[1] if len(parts) > 1 else None
        unit_name = None
        sub_name = None
        for p in parts:
            if p.startswith("unit-"):
                unit_name = p
            if p.startswith("sub-"):
                sub_name = p

        if cycle_name:
            if os.path.basename(n["file_path"]) == "frontier.md" and unit_name is None:
                cycles[cycle_name]["frontier"] = n
            elif unit_name and sub_name is None and os.path.basename(n["file_path"]) == "frontier.md":
                cycles[cycle_name]["units"][unit_name]["frontier"] = n
            elif unit_name and sub_name and os.path.basename(n["file_path"]) == "frontier.md":
                cycles[cycle_name]["units"][unit_name]["subs"][sub_name]["frontier"] = n
            elif unit_name and sub_name:
                cycles[cycle_name]["units"][unit_name]["subs"][sub_name]["nodes"].append(n)
            elif unit_name:
                unit_data = cycles[cycle_name]["units"][unit_name]
                unit_data["frontier"] = unit_data["frontier"] or n
            else:
                # Top-level cycle nodes (e.g., cycle-0/deep-thinker/...)
                # Put them under a virtual unit
                cycles[cycle_name]["units"]["(top-level)"]["subs"]["(root)"]["nodes"].append(n)

    lines.append("| Cycle | Status | Frontier |")
    lines.append("|-------|--------|----------|")
    for cname in sorted(cycles):
        cdata = cycles[cname]
        cf = cdata["frontier"]
        cstatus = cf["status"] if cf else "--"
        ctitle = cf["title"] if cf else cname
        cfpath = cf["file_path"] if cf else "--"
        lines.append(f"| {ctitle or cname} | {cstatus} | `{cfpath}` |")

        for uname in sorted(cdata["units"]):
            if uname == "(top-level)":
                continue
            udata = cdata["units"][uname]
            uf = udata["frontier"]
            ustatus = uf["status"] if uf else "--"
            utitle = uf["title"] if uf else uname
            ufpath = uf["file_path"] if uf else "--"
            lines.append(f"| -- {utitle or uname} | {ustatus} | `{ufpath}` |")

            for sname in sorted(udata["subs"]):
                sdata = udata["subs"][sname]
                sf = sdata["frontier"]
                sstatus = sf["status"] if sf else "--"
                stitle = sf["title"] if sf else sname
                sfpath = sf["file_path"] if sf else "--"
                lines.append(f"| ---- {stitle or sname} | {sstatus} | `{sfpath}` |")
    lines.append("")

    # --- Next action ---
    lines.append("## Next action")
    lines.append("")
    pending = conn.execute("SELECT * FROM nodes WHERE status = 'pending' ORDER BY file_path LIMIT 1").fetchone()
    if pending:
        title = pending["title"] or readable_id(pending["id"])
        lines.append(f"First pending: **{title}** (`{pending['id']}`)")
        lines.append(f"File: `{pending['file_path']}`")
    else:
        lines.append("No pending nodes.")
    lines.append("")

    content = "\n".join(lines) + "\n"
    _atomic_write(PROGRESS_PATH, content)
    print(f"Generated: {PROGRESS_PATH}")


# ---------------------------------------------------------------------------
# Command: assumptions -> FOUNDATIONS.md
# ---------------------------------------------------------------------------


def cmd_assumptions(args: argparse.Namespace) -> None:
    """Auto-generate FOUNDATIONS.md."""
    conn = build_db()  # Always rebuild for freshness

    lines = [
        "# Foundations",
        "",
        "> Auto-generated by `manage.py assumptions`. Do not edit manually.",
        "",
    ]

    assumptions = conn.execute("SELECT * FROM nodes WHERE type = 'assumption' ORDER BY date, id").fetchall()

    if not assumptions:
        lines.append("No assumptions registered in the database.")
        lines.append("")
        lines.append("To register assumptions, add `type: assumption` to a file's frontmatter,")
        lines.append("and reference it via `assumes: [<id>]` in dependent files.")
    else:
        for a in assumptions:
            lines.append(f"## `{a['id']}`")
            lines.append("")
            lines.append(f"- **Status**: {a['status']}")
            lines.append(f"- **Date introduced**: {a['date']}")
            lines.append(f"- **File**: `{a['file_path']}`")

            # What depends on it
            dependents = conn.execute(
                "SELECT source_id FROM edges WHERE target_id = ? AND relation = 'assumes'",
                (a["id"],),
            ).fetchall()
            if dependents:
                lines.append(f"- **Depended on by**: {', '.join('`' + d['source_id'] + '`' for d in dependents)}")
            else:
                lines.append("- **Depended on by**: (none)")

            # If falsified
            if a["status"] == "falsified":
                evidence = conn.execute(
                    "SELECT target_id FROM edges WHERE source_id = ? AND relation = 'falsified_by'",
                    (a["id"],),
                ).fetchone()
                if evidence:
                    lines.append(f"- **Falsified by**: `{evidence['target_id']}`")

                # What was cascaded
                cascaded = conn.execute(
                    "SELECT n.id, n.status FROM nodes n "
                    "JOIN edges e ON e.source_id = n.id AND e.target_id = ? AND e.relation = 'assumes' "
                    "WHERE n.status IN ('mixed', 'undermined')",
                    (a["id"],),
                ).fetchall()
                if cascaded:
                    lines.append(f"- **Cascade**: {', '.join('`' + c['id'] + '`' for c in cascaded)} weakened")
            lines.append("")

    content = "\n".join(lines) + "\n"
    _atomic_write(FOUNDATIONS_PATH, content)
    print(f"Generated: {FOUNDATIONS_PATH}")


# ---------------------------------------------------------------------------
# Command: query
# ---------------------------------------------------------------------------


_READ_SQL_RE = re.compile(
    r"^\s*(?:/\*.*?\*/\s*)*(SELECT|EXPLAIN|PRAGMA)\b",
    re.IGNORECASE | re.DOTALL,
)

_PRAGMA_WRITE_RE = re.compile(r"^\s*PRAGMA\s+\w+\s*=", re.IGNORECASE)


def cmd_query(args: argparse.Namespace) -> None:
    """Run arbitrary SQL against the DB."""
    # Rebuild DB first for freshness
    conn = build_db()
    sql = args.sql

    if not _READ_SQL_RE.match(sql):
        print("ERROR: Query command is read-only. Only SELECT, EXPLAIN, and PRAGMA statements are allowed.")
        sys.exit(1)

    if _PRAGMA_WRITE_RE.match(sql):
        print(
            "ERROR: Write-capable PRAGMA statements are not allowed. Use read-only PRAGMAs (e.g., PRAGMA table_info)."
        )
        sys.exit(1)

    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"SQL error: {e}")
        sys.exit(1)

    if not rows:
        if getattr(args, "json", False):
            print("[]")
        else:
            print("(no results)")
        return

    if getattr(args, "json", False):
        print(json.dumps([dict(r) for r in rows], indent=2))
        return

    # Print as table
    keys = rows[0].keys()
    widths = {k: len(k) for k in keys}
    str_rows = []
    for row in rows:
        sr = {}
        for k in keys:
            val = str(row[k]) if row[k] is not None else "NULL"
            sr[k] = val
            widths[k] = max(widths[k], len(val))
        str_rows.append(sr)

    header = " | ".join(k.ljust(widths[k]) for k in keys)
    sep = "-+-".join("-" * widths[k] for k in keys)
    print(header)
    print(sep)
    for sr in str_rows:
        line = " | ".join(sr[k].ljust(widths[k]) for k in keys)
        print(line)

    print(f"\n({len(rows)} row(s))")


# ---------------------------------------------------------------------------
# Command: list (node listing with filters)
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> None:
    """List nodes, optionally filtered by type or status."""
    conn = build_db()

    clauses: list[str] = []
    params: list[str] = []
    if args.type:
        clauses.append("type = ?")
        params.append(args.type)
    if args.status:
        clauses.append("status = ?")
        params.append(args.status)

    sql = "SELECT id, type, status, maturity, confidence, title, file_path FROM nodes"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY file_path"

    rows = conn.execute(sql, params).fetchall()

    if getattr(args, "json", False):
        print(json.dumps([dict(r) for r in rows], indent=2))
        return

    if not rows:
        print("No nodes found.")
        return

    for row in rows:
        title = row["title"] or row["id"]
        status = row["status"] or "?"
        ntype = row["type"] or "?"
        conf = f"  conf={row['confidence']}" if row["confidence"] else ""
        mat = f"  mat={row['maturity']}" if row["maturity"] else ""
        print(f"  {row['id']:40s}  {ntype:12s}  {status:12s}{conf}{mat}")
        if title != row["id"]:
            print(f"    {title}")

    print(f"\n({len(rows)} node(s))")


# ---------------------------------------------------------------------------
# Command: register / artifacts / codebook (coder registry)
# ---------------------------------------------------------------------------


def cmd_register(args: argparse.Namespace) -> None:
    """Register a coder artifact (function, generator, benchmark)."""
    conn = build_db()
    conn.execute(
        "INSERT OR REPLACE INTO coder_artifacts "
        "(id, name, artifact_type, file_path, description, dependencies, created_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            args.id,
            args.name,
            args.type,
            args.path,
            args.description or "",
            args.deps or "",
            args.cycle or "",
            date.today().isoformat(),
        ),
    )
    conn.commit()
    print(f"Registered: {args.id} ({args.name}) — {args.type} at {args.path}")


def cmd_artifacts(args: argparse.Namespace) -> None:
    """List all registered coder artifacts."""
    conn = build_db()
    rows = conn.execute("SELECT * FROM coder_artifacts ORDER BY created_at").fetchall()
    if not rows:
        print("No experiment artifacts registered. Use 'register' to add one.")
        return
    print(f"{'ID':<20} {'Name':<25} {'Type':<10} {'File':<40} {'Created'}")
    print("-" * 110)
    for r in rows:
        print(f"{r['id']:<20} {r['name']:<25} {r['artifact_type']:<10} {r['file_path']:<40} {r['created_at']}")
    print(f"\n({len(rows)} artifact(s))")


def cmd_codebook(args: argparse.Namespace) -> None:
    """Generate TOOLKIT.md from the coder artifacts registry."""
    conn = build_db()
    rows = conn.execute("SELECT * FROM coder_artifacts ORDER BY artifact_type, name").fetchall()

    lines = [
        "# Experiment Toolkit",
        "",
        "> Auto-generated from the experiment artifacts registry. Do not edit manually.",
        "",
    ]

    if not rows:
        lines.append("No artifacts registered yet.")
    else:
        by_type: dict[str, list] = {}
        for r in rows:
            by_type.setdefault(r["artifact_type"], []).append(r)

        for atype in sorted(by_type):
            lines.append(f"## {atype.title()}s")
            lines.append("")
            for r in by_type[atype]:
                lines.append(f"### `{r['id']}` — {r['name']}")
                lines.append(f"- **File**: `{r['file_path']}`")
                if r["description"]:
                    lines.append(f"- **Description**: {r['description']}")
                if r["dependencies"]:
                    lines.append(f"- **Dependencies**: {r['dependencies']}")
                if r["created_by"]:
                    lines.append(f"- **Created by**: cycle `{r['created_by']}`")
                lines.append(f"- **Date**: {r['created_at']}")
                lines.append("")

    content = "\n".join(lines) + "\n"
    codebook_path = RESEARCH_DIR / "TOOLKIT.md"
    _atomic_write(codebook_path, content)
    print(f"Generated: {codebook_path}")


# ---------------------------------------------------------------------------
# Command: next / context / prompt (orchestration)
# ---------------------------------------------------------------------------

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ORCH_CONFIG = PLUGIN_ROOT / "config" / "orchestration.yaml"


def cmd_log_dispatch(args: argparse.Namespace) -> None:
    """Log a dispatch event to the dispatches table."""
    conn = build_db()
    conn.execute(
        "INSERT INTO dispatches (timestamp, cycle_id, agent, action, round, details) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(),
            args.cycle,
            args.agent,
            args.action,
            args.round,
            args.details or "",
        ),
    )
    conn.commit()
    print(f"Logged: {args.action} {args.agent} (cycle {args.cycle})")


def cmd_dispatch_log(args: argparse.Namespace) -> None:
    """Show dispatch audit trail."""
    conn = build_db()
    if args.cycle:
        rows = conn.execute(
            "SELECT * FROM dispatches WHERE cycle_id = ? ORDER BY timestamp",
            (args.cycle,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM dispatches ORDER BY timestamp").fetchall()

    if not rows:
        print("No dispatches logged.")
        return

    if args.json:
        print(json.dumps([dict(r) for r in rows], indent=2))
        return

    print(f"{'Timestamp':<28} {'Cycle':<25} {'Agent':<12} {'Action':<16} {'Round':<6} Details")
    print("-" * 110)
    for r in rows:
        rnd = str(r["round"]) if r["round"] is not None else "—"
        print(
            f"{r['timestamp']:<28} {r['cycle_id']:<25} {r['agent']:<12} "
            f"{r['action']:<16} {rnd:<6} {r['details'] or ''}"
        )
    print(f"\n({len(rows)} dispatch(es))")


def cmd_next(args: argparse.Namespace) -> None:
    """Determine next action for a sub-unit."""
    from orchestration import (
        compute_paths,
        detect_state,
        extract_confidence,
        find_active_subunit,
        list_context_files,
        load_config,
        read_dispatch_config,
    )

    config = load_config(DEFAULT_ORCH_CONFIG)
    sub_path = args.path
    if sub_path == "auto":
        found = find_active_subunit(RESEARCH_DIR)
        if not found:
            print("No active sub-units found. Use /principia:scaffold to create one.")
            return
        sub_path = found
        print(f"Auto-detected: {sub_path}", file=sys.stderr)

    state = detect_state(RESEARCH_DIR, sub_path, config)
    state["sub_unit"] = sub_path

    # Enrich with dispatch mode
    dispatch_config = read_dispatch_config(RESEARCH_DIR)
    agent = state.get("agent")
    if agent:
        state["dispatch_mode"] = dispatch_config.get(agent, "internal")
        paths = compute_paths(sub_path, agent, state.get("round"))
        state.update(paths)

    # Enrich with context files (agent-aware filtering for knowledge divergence)
    agent = state["action"].removeprefix("dispatch_") if state["action"].startswith("dispatch_") else ""
    mr = config.get("debate_loop", {}).get("max_rounds", 3)
    state["context_files"] = list_context_files(
        RESEARCH_DIR, sub_path, state["action"], state.get("round"), agent=agent, max_rounds=mr
    )

    # Enrich complete states with verdict confidence
    if state["action"].startswith("complete_"):
        verdict_path = RESEARCH_DIR / sub_path / "judge" / "results" / "verdict.md"
        state["confidence"] = extract_confidence(verdict_path)

    print(json.dumps(state, indent=2))


def cmd_context(args: argparse.Namespace) -> None:
    """Assemble context document for the next agent."""
    from orchestration import assemble_context, detect_state, list_context_files, load_config

    config = load_config(DEFAULT_ORCH_CONFIG)
    state = detect_state(RESEARCH_DIR, args.path, config)
    agent = state["action"].removeprefix("dispatch_") if state["action"].startswith("dispatch_") else ""
    mr = config.get("debate_loop", {}).get("max_rounds", 3)
    files = list_context_files(RESEARCH_DIR, args.path, state["action"], state.get("round"), agent=agent, max_rounds=mr)
    doc = assemble_context(RESEARCH_DIR, files)
    print(doc)


def cmd_prompt(args: argparse.Namespace) -> None:
    """Generate self-contained prompt for external agent dispatch."""
    from orchestration import (
        assemble_context,
        compute_paths,
        detect_state,
        generate_external_prompt,
        list_context_files,
        load_config,
    )

    config = load_config(DEFAULT_ORCH_CONFIG)
    state = detect_state(RESEARCH_DIR, args.path, config)
    agent = state.get("agent")
    if not agent:
        print("ERROR: No agent to dispatch in current state.")
        sys.exit(1)

    paths = compute_paths(args.path, agent, state.get("round"))
    state.update(paths)

    mr = config.get("debate_loop", {}).get("max_rounds", 3)
    files = list_context_files(RESEARCH_DIR, args.path, state["action"], state.get("round"), agent=agent, max_rounds=mr)
    context = assemble_context(RESEARCH_DIR, files)

    # Read agent instructions
    agent_file = PLUGIN_ROOT / "agents" / f"{agent}.md"
    instructions = ""
    if agent_file.exists():
        instructions = get_body(agent_file.read_text(encoding="utf-8"))

    prompt = generate_external_prompt(state, context, instructions)

    # Write to prompt_path
    prompt_path = RESEARCH_DIR / state["prompt_path"]
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(prompt_path, prompt)
    print(f"Written: {prompt_path}")


def cmd_waves(args: argparse.Namespace) -> None:
    """Show execution waves based on dependency topological sort."""
    from orchestration import compute_waves

    waves = compute_waves(RESEARCH_DIR)
    if not waves:
        if getattr(args, "json", False):
            print("[]")
        else:
            print("No nodes in database. Run 'build' first.")
        return

    if getattr(args, "json", False):
        out = [[dict(n) for n in wave] for wave in waves]
        print(json.dumps(out, indent=2))
        return

    for i, wave in enumerate(waves, 1):
        print(f"\nWave {i}:")
        for node in wave:
            maturity = node.get("maturity") or "—"
            status = node["status"]
            title = node.get("title") or node["id"]
            print(f"  [{maturity:<15}] {status:<12} {title} ({node['id']})")
    print(f"\n{len(waves)} wave(s), {sum(len(w) for w in waves)} node(s)")


def _format_investigation_breadcrumb(state: dict[str, Any], research_dir: Path) -> str:
    """Format a breadcrumb string for the current investigation state."""
    phase = state.get("phase", "")
    action = state.get("action", "")

    # Read north star title if exists
    ns_path = research_dir / ".north-star.md"
    north_star = ""
    if ns_path.exists():
        body = get_body(ns_path.read_text(encoding="utf-8"))
        first_line = body.strip().split("\n")[0].lstrip("# ").strip()
        north_star = first_line[:80]

    parts: list[str] = []

    if phase == "understand":
        substeps = state.get("substeps", [])
        current = substeps[0].title() if substeps else "Complete"
        parts.append(f"[Understand > {current}]")
        remaining = ", ".join(s for s in substeps[1:])
        if remaining:
            parts.append(f"  Next: {remaining}")
    elif phase == "divide":
        if action == "scaffold":
            n = len(state.get("claims", []))
            parts.append(f"[Divide > Scaffold] {n} claims to scaffold")
        else:
            parts.append("[Divide] Decomposing into testable claims")
    elif phase == "test":
        cycle = state.get("cycle", "")
        if action == "test_claim":
            parts.append(f"[Test > {cycle}] Dispatching conductor")
        elif action == "record_verdict":
            parts.append(f"[Test > {cycle}] Recording verdict")
    elif phase == "synthesize":
        n = len(state.get("proven_claims", []))
        parts.append(f"[Synthesize] Composing from {n} proven claims")
    elif phase == "complete":
        parts.append("[Complete] Design process finished")

    if north_star:
        parts.append(f'  North star: "{north_star}"')

    return "\n".join(parts)


def cmd_investigate_next(args: argparse.Namespace) -> None:
    """Determine next action for the full investigation."""
    from orchestration import detect_investigation_state, load_config

    config = load_config(DEFAULT_ORCH_CONFIG)
    quick = getattr(args, "quick", False)
    if quick:
        # Quick mode: override to 1 debate round
        config = {**config}
        config["debate_loop"] = {**config.get("debate_loop", {}), "max_rounds": 1}
    state = detect_investigation_state(RESEARCH_DIR, config, quick=quick)
    state["breadcrumb"] = _format_investigation_breadcrumb(state, RESEARCH_DIR)
    print(json.dumps(state, indent=2))


def cmd_parse_framework(args: argparse.Namespace) -> None:
    """Parse claim registry from blueprint.md (or legacy framework.md)."""
    from orchestration import parse_framework

    framework_path = RESEARCH_DIR / "blueprint.md"
    if not framework_path.exists():
        framework_path = RESEARCH_DIR / "framework.md"
    claims = parse_framework(framework_path)
    if not claims:
        print("No claim registry found in blueprint.md.")
        print("Ensure the synthesizer included a ```yaml block with # CLAIM_REGISTRY.", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(claims, indent=2))


# ---------------------------------------------------------------------------
# Command: results -> RESULTS.md
# ---------------------------------------------------------------------------


def cmd_results(args: argparse.Namespace) -> None:
    """Generate a single RESULTS.md summarising the entire design investigation."""
    conn = build_db()

    lines: list[str] = ["# Design Results", ""]

    # --- Original question/principle ---
    # Try to read from blueprint or framework
    for name in ("blueprint.md", "framework.md"):
        bp = RESEARCH_DIR / name
        if bp.exists():
            body = get_body(bp.read_text(encoding="utf-8"))
            # Extract first paragraph as the principle
            para = []
            for line in body.splitlines():
                if line.strip():
                    para.append(line.strip())
                elif para:
                    break
            if para:
                lines.append("## Principle")
                lines.append("")
                lines.extend(para)
                lines.append("")
            break

    # --- Claims and verdicts ---
    lines.append("## Claims")
    lines.append("")

    cycles_dir = RESEARCH_DIR / "cycles"
    claims_dir = RESEARCH_DIR / "claims"

    # Gather all verdict nodes
    verdicts = conn.execute(
        "SELECT id, status, confidence FROM nodes WHERE type = 'verdict' ORDER BY id"
    ).fetchall()

    if verdicts:
        for v in verdicts:
            vid = v["id"]
            status = v["status"] or "pending"
            confidence = v["confidence"] or "unknown"
            # Map legacy status names
            display_status = STATUS_ALIASES_REV.get(status, status).upper()
            lines.append(f"### {vid}")
            lines.append(f"- **Verdict**: {display_status}")
            lines.append(f"- **Confidence**: {confidence}")
            lines.append("")
    else:
        # Fall back to scanning directories
        for search_dir in (claims_dir, cycles_dir):
            if not search_dir.exists():
                continue
            for verdict_file in sorted(search_dir.rglob("verdict.md")):
                rel = str(verdict_file.relative_to(RESEARCH_DIR))
                text = verdict_file.read_text(encoding="utf-8")
                meta = parse_frontmatter(text)
                body_preview = get_body(text).strip().splitlines()[:3]
                lines.append(f"### {rel}")
                if meta.get("status"):
                    status = meta["status"]
                    display = STATUS_ALIASES_REV.get(status, status).upper()
                    lines.append(f"- **Verdict**: {display}")
                for bline in body_preview:
                    lines.append(f"> {bline}")
                lines.append("")

    if not verdicts and not any((claims_dir.exists(), cycles_dir.exists())):
        lines.append("No claims investigated yet.")
        lines.append("")

    # --- Synthesis ---
    synthesis = RESEARCH_DIR / "synthesis.md"
    if synthesis.exists():
        lines.append("## Synthesis")
        lines.append("")
        body = get_body(synthesis.read_text(encoding="utf-8"))
        lines.append(body.strip())
        lines.append("")

    # --- Composition ---
    composition = RESEARCH_DIR / "composition.md"
    if composition.exists():
        lines.append("## Composed Algorithm")
        lines.append("")
        body = get_body(composition.read_text(encoding="utf-8"))
        lines.append(body.strip())
        lines.append("")

    # --- Limitations ---
    lines.append("## Limitations")
    lines.append("")

    disproven = conn.execute(
        "SELECT id FROM nodes WHERE status IN ('falsified', 'disproven') ORDER BY id"
    ).fetchall()
    if disproven:
        lines.append("**Disproven claims**:")
        for row in disproven:
            lines.append(f"- {row['id']}")
        lines.append("")

    pending_assumptions = conn.execute(
        "SELECT id FROM nodes WHERE type = 'assumption' AND status = 'pending' ORDER BY id"
    ).fetchall()
    if pending_assumptions:
        lines.append("**Untested assumptions**:")
        for row in pending_assumptions:
            lines.append(f"- {row['id']}")
        lines.append("")

    weakened = conn.execute(
        "SELECT id FROM nodes WHERE status IN ('mixed', 'partial', 'undermined', 'weakened') ORDER BY id"
    ).fetchall()
    if weakened:
        lines.append("**Partially supported / weakened**:")
        for row in weakened:
            lines.append(f"- {row['id']}")
        lines.append("")

    if not disproven and not pending_assumptions and not weakened:
        lines.append("None identified.")
        lines.append("")

    # --- Write ---
    content = "\n".join(lines) + "\n"
    results_path = RESEARCH_DIR / "RESULTS.md"
    _atomic_write(results_path, content)
    print(f"Generated: {results_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Principia design management system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python manage.py --root design scaffold claim enrichment
              python manage.py --root design validate
              python manage.py --root design status
              python manage.py --root design results
              python manage.py --root design query "SELECT id, status FROM nodes WHERE type='claim'"
        """),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("design"),
        help="Path to design root directory (default: design/)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # new
    p_new = sub.add_parser("new", help="Create a new markdown file with auto-generated frontmatter")
    p_new.add_argument("path", help="Relative path from research root (e.g. cycles/cycle-1/...)")
    p_new.set_defaults(func=cmd_new)

    # build
    p_build = sub.add_parser("build", help="Rebuild SQLite DB from all markdown files")
    p_build.set_defaults(func=cmd_build)

    # validate
    p_val = sub.add_parser("validate", help="Check referential integrity and required fields")
    p_val.add_argument("--json", action="store_true", help="Output as JSON")
    p_val.set_defaults(func=cmd_validate)

    # falsify
    p_fals = sub.add_parser("falsify", help="Mark a node as falsified and cascade")
    p_fals.add_argument("id", help="Node ID to falsify")
    p_fals.add_argument("--by", help="Evidence ID that falsified it", default=None)
    p_fals.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    p_fals.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    p_fals.set_defaults(func=cmd_falsify)

    # settle
    p_settle = sub.add_parser("settle", help="Mark a node as settled")
    p_settle.add_argument("id", help="Node ID to settle")
    p_settle.set_defaults(func=cmd_settle)

    # status
    p_stat = sub.add_parser("status", help="Auto-generate PROGRESS.md from the DB")
    p_stat.set_defaults(func=cmd_status)

    # assumptions
    p_assu = sub.add_parser("assumptions", help="Auto-generate FOUNDATIONS.md")
    p_assu.set_defaults(func=cmd_assumptions)

    # query
    p_query = sub.add_parser("query", help="Run arbitrary SQL against the DB")
    p_query.add_argument("sql", help="SQL query to execute")
    p_query.add_argument("--json", action="store_true", help="Output as JSON")
    p_query.set_defaults(func=cmd_query)

    # list
    p_list = sub.add_parser("list", help="List nodes with optional filters")
    p_list.add_argument("--type", default=None, help="Filter by node type (claim, assumption, evidence, ...)")
    p_list.add_argument("--status", default=None, help="Filter by status (pending, active, settled, falsified, ...)")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")
    p_list.set_defaults(func=cmd_list)

    # impact (was cascade)
    p_casc = sub.add_parser("cascade", help="Preview: what breaks if this claim is disproven?")
    p_casc.add_argument("id", help="Node ID to analyze")
    p_casc.set_defaults(func=cmd_cascade)

    # scaffold (supports cycle/unit/sub-unit and flat claim)
    p_scaffold = sub.add_parser("scaffold", help="Create directory structure")
    p_scaffold.add_argument(
        "level", choices=["cycle", "unit", "sub-unit", "claim"], help="What to scaffold"
    )
    p_scaffold.add_argument("name", help="Slug name (e.g., enrichment, bottleneck)")
    p_scaffold.add_argument(
        "--parent", help="Parent path relative to research/ (required for unit/sub-unit)", default=None
    )
    p_scaffold.set_defaults(func=cmd_scaffold)

    # results — generate RESULTS.md
    p_results = sub.add_parser("results", help="Generate RESULTS.md summary document")
    p_results.set_defaults(func=cmd_results)

    # --- Internal commands (hidden from --help, used by skills/agents) ---

    p_reg = sub.add_parser("register")  # register experimenter artifact
    p_reg.add_argument("--id", required=True)
    p_reg.add_argument("--name", required=True)
    p_reg.add_argument("--type", required=True, choices=["function", "class", "script", "dataset"])
    p_reg.add_argument("--path", required=True)
    p_reg.add_argument("--description", default=None)
    p_reg.add_argument("--deps", default=None)
    p_reg.add_argument("--cycle", default=None)
    p_reg.set_defaults(func=cmd_register)

    p_art = sub.add_parser("artifacts")  # list registered artifacts
    p_art.set_defaults(func=cmd_artifacts)

    p_cb = sub.add_parser("codebook")  # generate TOOLKIT.md
    p_cb.set_defaults(func=cmd_codebook)

    p_next = sub.add_parser("next")  # determine next action for a sub-unit
    p_next.add_argument("path", nargs="?", default="auto")
    p_next.set_defaults(func=cmd_next)

    p_ctx = sub.add_parser("context")  # assemble context document
    p_ctx.add_argument("path")
    p_ctx.set_defaults(func=cmd_context)

    p_prompt = sub.add_parser("prompt")  # generate external agent prompt
    p_prompt.add_argument("path")
    p_prompt.set_defaults(func=cmd_prompt)

    p_waves = sub.add_parser("waves")  # show execution waves
    p_waves.add_argument("--json", action="store_true")
    p_waves.set_defaults(func=cmd_waves)

    p_logd = sub.add_parser("log-dispatch")  # log a dispatch event
    p_logd.add_argument("--cycle", required=True)
    p_logd.add_argument("--agent", required=True)
    p_logd.add_argument("--action", required=True, choices=["dispatch", "side_dispatch", "override"])
    p_logd.add_argument("--round", type=int, default=None)
    p_logd.add_argument("--details", default=None)
    p_logd.set_defaults(func=cmd_log_dispatch)

    p_dlog = sub.add_parser("dispatch-log")  # show dispatch audit trail
    p_dlog.add_argument("--cycle", default=None)
    p_dlog.add_argument("--json", action="store_true")
    p_dlog.set_defaults(func=cmd_dispatch_log)

    p_inv = sub.add_parser("investigate-next")  # investigation state machine
    p_inv.add_argument("--quick", action="store_true")
    p_inv.set_defaults(func=cmd_investigate_next)

    p_pf = sub.add_parser("parse-framework")  # parse claim registry from blueprint
    p_pf.set_defaults(func=cmd_parse_framework)

    p_pv = sub.add_parser("post-verdict")  # automated post-verdict bookkeeping
    p_pv.add_argument("path")
    p_pv.set_defaults(func=cmd_post_verdict)

    args = parser.parse_args()
    init_paths(args.root)
    args.func(args)


if __name__ == "__main__":
    main()
