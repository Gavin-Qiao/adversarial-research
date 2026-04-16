"""CLI commands for the principia design management system."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from . import config as _cfg
from .db import (
    _find_cascade_targets,
    _get_or_create_db,
    _update_frontmatter_in_file,
    build_db,
)
from .frontmatter import (
    get_body,
    get_scalar_frontmatter,
    parse_frontmatter,
    serialise_frontmatter,
)
from .ids import (
    derive_id,
    infer_type_from_path,
)
from .reports import _format_investigation_breadcrumb


def _check_path_containment(sub_path: str) -> None:
    """Verify a relative path stays within RESEARCH_DIR. Exits on traversal."""
    root = str(_cfg.RESEARCH_DIR.resolve()) + os.sep
    resolved = str((_cfg.RESEARCH_DIR / sub_path).resolve())
    if not (resolved.startswith(root) or resolved == root.rstrip(os.sep)):
        print("ERROR: Path escapes the research directory.")
        sys.exit(1)


def emit_envelope(data: Any, warnings: list[str] | None = None) -> None:
    """Emit the canonical JSON envelope to stdout.

    All public commands that produce machine-readable output route through
    this helper so the contract envelope shape stays in one place.
    """
    payload = {
        "schema_version": 1,
        "data": data,
        "warnings": warnings or [],
    }
    print(json.dumps(payload, indent=2))


def _primary_claim_file(target: str | os.PathLike[str]) -> Path:
    """Return the main claim document for a target directory.

    Newer layouts use `claim.md`; legacy cycle layouts use `frontier.md`.
    """
    target_path = Path(target)
    claim_file = target_path / "claim.md"
    if claim_file.exists():
        return claim_file
    return target_path / "frontier.md"


def _primary_claim_path_sql(column: str = "file_path") -> str:
    return f"({column} LIKE 'claims/claim-%/claim.md' OR {column} LIKE 'cycles/%/frontier.md')"


def _is_primary_claim_path(file_path: str) -> bool:
    return (file_path.startswith("claims/claim-") and file_path.endswith("/claim.md")) or (
        file_path.startswith("cycles/") and file_path.endswith("/frontier.md")
    )


def _resolved_frontmatter_id(
    fpath: Path,
    meta: dict[str, Any],
    *,
    label: str,
    strict: bool = False,
) -> str:
    rel = _cfg.rel_path_from_root(fpath)
    node_id = get_scalar_frontmatter(meta, "id", filepath=rel, warn=not strict)
    if "id" in meta and node_id is None and strict:
        print(f"ERROR: {label} at {rel} has a non-scalar id.")
        sys.exit(1)
    return node_id or derive_id(rel)


def _load_primary_claim(target: Path) -> tuple[Path, dict[str, Any], str]:
    claim_file = _primary_claim_file(target)
    if not claim_file.exists():
        print(f"ERROR: No primary claim file found in {target}")
        sys.exit(1)
    rel = _cfg.rel_path_from_root(claim_file)
    try:
        text = claim_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: Could not read primary claim file at {rel}: {exc}")
        sys.exit(1)
    meta = parse_frontmatter(text, filepath=rel)
    node_id = _resolved_frontmatter_id(claim_file, meta, label="Primary claim file", strict=True)
    return claim_file, meta, node_id


def _weakened_updates(dep_fpath: Path, dep_node: sqlite3.Row | None, new_confidence: str | None) -> dict[str, Any]:
    """Build frontmatter updates for a cascaded weakening.

    Preserve the node's prior status/confidence the first time it is weakened
    so rollback can restore the original state instead of collapsing to
    `pending`.
    """
    updates: dict[str, Any] = {"status": "weakened", "confidence": new_confidence}
    rel = _cfg.rel_path_from_root(dep_fpath)
    meta = parse_frontmatter(dep_fpath.read_text(encoding="utf-8"), filepath=rel)
    if meta.get("weakened_from_status") in (None, ""):
        updates["weakened_from_status"] = dep_node["status"] if dep_node else "pending"
    if meta.get("weakened_from_confidence") in (None, ""):
        updates["weakened_from_confidence"] = dep_node["confidence"] if dep_node and dep_node["confidence"] else ""
    return updates


def _restore_weakened_state(dep_fpath: Path) -> tuple[bool, str, str | None]:
    """Restore a previously weakened node to its stored pre-weakened state."""
    meta = parse_frontmatter(dep_fpath.read_text(encoding="utf-8"))
    restored_status = str(meta.get("weakened_from_status") or "pending")
    restored_conf_raw = meta.get("weakened_from_confidence")
    restored_conf = str(restored_conf_raw) if restored_conf_raw not in (None, "") else None
    updates: dict[str, Any] = {
        "status": restored_status,
        "confidence": restored_conf or "",
        "weakened_from_status": "",
        "weakened_from_confidence": "",
    }
    return _update_frontmatter_in_file(dep_fpath, updates), restored_status, restored_conf


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
    full = (_cfg.RESEARCH_DIR / rel).resolve()
    # Prevent path traversal outside research/
    _check_path_containment(rel)
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


def cmd_build(args: argparse.Namespace) -> None:
    build_db(force=True)


# ---------------------------------------------------------------------------
# Command: falsify
# ---------------------------------------------------------------------------


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

    if node["status"] == "disproven":
        print(f"WARN: Node '{node_id}' is already disproven — skipping.")
        return

    if evidence_id:
        evidence = conn.execute("SELECT 1 FROM nodes WHERE id = ?", (evidence_id,)).fetchone()
        if not evidence:
            print(f"ERROR: Evidence node '{evidence_id}' not found.")
            sys.exit(1)

    # Find cascade targets
    affected = _find_cascade_targets(conn, node_id)
    non_disproven = [(d, f, s) for d, f, s in affected if s != "disproven"]

    # --dry-run: preview only
    if dry_run:
        print(f"Dry-run: would disprove '{node_id}' ({node['file_path']})")
        if evidence_id:
            print(f"      By: {evidence_id}")
        if non_disproven:
            print(f"\nWould weaken {len(non_disproven)} dependent node(s):")
            for dep_id, fp, status in affected:
                marker = " (already disproven)" if status == "disproven" else ""
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
    fpath = _cfg.RESEARCH_DIR / node["file_path"]
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
    from .orchestration import attenuate_confidence

    for dep_id, dep_fp, dep_status in affected:
        if dep_status != "disproven":
            dep_fpath = _cfg.RESEARCH_DIR / dep_fp
            dep_node = conn.execute("SELECT * FROM nodes WHERE id = ?", (dep_id,)).fetchone()
            new_conf = attenuate_confidence(dep_node["confidence"] if dep_node else None)
            cascade_updates = _weakened_updates(dep_fpath, dep_node, new_conf)
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
            "INSERT INTO ledger (timestamp, event, node_id, details, agent) VALUES (?, ?, ?, ?, ?)",
            (today, event, nid, detail, "user"),
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

    if node["status"] == "proven":
        print(f"WARN: Node '{node_id}' is already proven — skipping.")
        return

    if node["status"] == "disproven":
        print(f"ERROR: Node '{node_id}' is disproven — cannot prove a disproven node.")
        sys.exit(1)

    # Mark the node as proven
    fpath = _cfg.RESEARCH_DIR / node["file_path"]
    if not _update_frontmatter_in_file(fpath, {"status": "proven"}):
        print(f"ERROR: Could not update file for '{node_id}' — aborting.")
        sys.exit(1)

    conn.execute("UPDATE nodes SET status = 'proven' WHERE id = ?", (node_id,))

    # Ledger entry
    today = date.today().isoformat()
    conn.execute(
        "INSERT INTO ledger (timestamp, event, node_id, details, agent) VALUES (?, ?, ?, ?, ?)",
        (today, "proven", node_id, "Set to proven", "user"),
    )
    conn.commit()

    print(f"Settled: {node_id}")
    print(f"   File: {node['file_path']}")


# ---------------------------------------------------------------------------
# Command: post-verdict (automated post-verdict bookkeeping)
# ---------------------------------------------------------------------------


def cmd_post_verdict(args: argparse.Namespace) -> None:
    """Automate post-verdict bookkeeping (update statuses, cascade, regenerate reports)."""
    from .orchestration import extract_confidence, extract_verdict, load_config, read_dispatch_config

    config = load_config(_cfg.DEFAULT_ORCH_CONFIG)
    sub_path = args.path
    _check_path_containment(sub_path)
    target = _cfg.RESEARCH_DIR / sub_path

    verdict_file = target / "arbiter" / "results" / "verdict.md"
    if not verdict_file.exists():
        print(f"ERROR: No verdict file found in {target}")
        sys.exit(1)

    claim_file, _claim_meta, node_id = _load_primary_claim(target)

    verdict = extract_verdict(verdict_file, config)
    if verdict == "UNKNOWN":
        print("ERROR: Could not parse verdict from verdict file.")
        sys.exit(1)
    confidence = extract_confidence(verdict_file)
    verdict_rel = _cfg.rel_path_from_root(verdict_file)
    try:
        verdict_text = verdict_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: Could not read verdict file at {verdict_rel}: {exc}")
        sys.exit(1)
    verdict_meta = parse_frontmatter(verdict_text, filepath=verdict_rel)
    verdict_id = _resolved_frontmatter_id(verdict_file, verdict_meta, label="Verdict file")

    _cfg._emit_progress("recording", "post_verdict", f"{sub_path}: {verdict} ({confidence})")

    conn = build_db()
    _sync_dispatch_receipts(sub_path, root=_cfg.RESEARCH_DIR)
    changes: list[str] = []

    # Apply verdict (extract_verdict now returns principia names: PROVEN, DISPROVEN, PARTIAL)
    if verdict == "PROVEN":
        node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if node and node["status"] not in ("proven", "disproven"):
            _update_frontmatter_in_file(claim_file, {"status": "proven"})
            conn.execute("UPDATE nodes SET status = 'proven' WHERE id = ?", (node_id,))
            changes.append(f"Proven: {node_id}")

    elif verdict == "DISPROVEN":
        node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if node and node["status"] != "disproven":
            _update_frontmatter_in_file(claim_file, {"status": "disproven", "falsified_by": verdict_id})
            conn.execute("UPDATE nodes SET status = 'disproven' WHERE id = ?", (node_id,))
            changes.append(f"Disproven: {node_id} by {verdict_id}")
            # Cascade — weaken dependents
            cascade_targets = _find_cascade_targets(conn, node_id)
            from .orchestration import attenuate_confidence

            for dep_id, dep_fp, dep_status in cascade_targets:
                if dep_status != "disproven":
                    dep_fpath = _cfg.RESEARCH_DIR / dep_fp
                    dep_node = conn.execute("SELECT * FROM nodes WHERE id = ?", (dep_id,)).fetchone()
                    new_conf = attenuate_confidence(dep_node["confidence"] if dep_node else None)
                    cascade_updates = _weakened_updates(dep_fpath, dep_node, new_conf)
                    if _update_frontmatter_in_file(dep_fpath, cascade_updates):
                        conn.execute(
                            "UPDATE nodes SET status = 'weakened', confidence = ? WHERE id = ?",
                            (new_conf, dep_id),
                        )
                        changes.append(f"Weakened: {dep_id}")

    elif verdict in ("PARTIAL", "INCONCLUSIVE"):
        new_status = "partial" if verdict == "PARTIAL" else "inconclusive"
        _update_frontmatter_in_file(claim_file, {"status": new_status})
        conn.execute("UPDATE nodes SET status = ? WHERE id = ?", (new_status, node_id))
        changes.append(f"Updated {node_id} to {new_status}")

    # Ledger entry
    today = date.today().isoformat()
    verdict_rel = verdict_file.relative_to(_cfg.RESEARCH_DIR).as_posix() if verdict_file.exists() else ""
    conn.execute(
        "INSERT INTO ledger (timestamp, event, node_id, details, agent) VALUES (?, ?, ?, ?, ?)",
        (
            today,
            verdict.lower(),
            node_id,
            f"Confidence: {confidence}, File: {verdict_rel}",
            "arbiter",
        ),
    )
    try:
        conn.commit()
    except sqlite3.Error as exc:
        print(f"ERROR: DB commit failed: {exc}. Files were updated; run 'build' to resync DB.", file=sys.stderr)
        sys.exit(1)

    # Write marker file signaling post-verdict bookkeeping is done
    marker = target / ".post_verdict_done"
    _cfg._atomic_write(marker, today)
    cycle_id = Path(sub_path).name
    dispatch_modes = read_dispatch_config(_cfg.RESEARCH_DIR)
    if not _dispatch_event_exists(
        cycle_id=cycle_id,
        agent="arbiter",
        action="recorded",
        result_path=verdict_rel,
        sub_unit=sub_path,
        root=_cfg.RESEARCH_DIR,
    ):
        record_dispatch_event(
            cycle_id=cycle_id,
            agent="arbiter",
            action="recorded",
            details=f"Verdict {verdict} recorded at confidence {confidence}.",
            root=_cfg.RESEARCH_DIR,
            sub_unit=sub_path,
            dispatch_mode=dispatch_modes.get("arbiter", "internal"),
            packet_path=f"{sub_path}/arbiter/packet.md",
            prompt_path=f"{sub_path}/arbiter/prompt.md",
            result_path=verdict_rel,
        )

    result = {
        "verdict": verdict,
        "confidence": confidence,
        "node_id": node_id,
        "changes": changes,
    }
    emit_envelope(result)


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
        print(f"Would set {len(affected)} node(s) to 'weakened':")
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
    """Create directory structure for a claim."""
    from .orchestration import compute_north_star_version

    level = args.level
    name = args.name

    # Validate name is a slug
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", name):
        print(f"ERROR: Name must be a lowercase slug (letters, digits, hyphens): got '{name}'")
        sys.exit(1)

    if level == "claim":
        # Flat hierarchy: claims/claim-N-name/ — no unit/sub-unit nesting
        base = _cfg.RESEARCH_DIR / "claims"
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

    _cfg._emit_progress("scaffolding", f"scaffold_{level}", name)

    # Create claim.md with frontmatter
    frontier_name = "claim.md"
    frontier = target / frontier_name
    rel = _cfg.rel_path_from_root(frontier)
    node_id = derive_id(rel)
    today = date.today().isoformat()
    meta: dict[str, str | list[str] | None] = {
        "id": node_id,
        "type": "claim",
        "status": "pending",
        "date": today,
        "depends_on": [],
        "assumes": [],
        "attack_type": None,
        "falsified_by": None,
        "counterfactual": None,
    }
    north_star_version = compute_north_star_version(_cfg.RESEARCH_DIR)
    if north_star_version:
        meta["north_star_version"] = north_star_version
    # Add optional claim registry metadata
    if getattr(args, "falsification", None):
        meta["falsification"] = args.falsification
    if getattr(args, "maturity", None):
        meta["maturity"] = args.maturity
    if getattr(args, "confidence", None):
        meta["confidence"] = args.confidence
    title = name.replace("-", " ").title()
    body = f"\n\n# {title}\n"
    if getattr(args, "statement", None):
        body = f"\n\n# {title}\n\n{args.statement}\n"
    content = serialise_frontmatter(meta) + body
    frontier.write_text(content, encoding="utf-8")
    print(f"Created: {target}")
    print(f"  {frontier_name} (id: {node_id})")

    # For claims, create role directories
    if level == "claim":
        for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
            (target / role).mkdir()
            print(f"  {role}/")


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
            emit_envelope([])
        else:
            print("(no results)")
        return

    if getattr(args, "json", False):
        emit_envelope([dict(r) for r in rows])
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
        emit_envelope([dict(r) for r in rows])
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
# Command: register / artifacts (coder registry)
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


# ---------------------------------------------------------------------------
# Command: next / context / prompt (orchestration)
# ---------------------------------------------------------------------------


def _resolve_workspace_root(root: Path | None = None) -> Path:
    return _cfg.RESEARCH_DIR.resolve() if root is None else root.resolve()


def _load_agent_instructions(agent: str) -> str:
    agent_file = _cfg.PLUGIN_ROOT / "agents" / f"{agent}.md"
    if not agent_file.exists():
        return ""
    return get_body(agent_file.read_text(encoding="utf-8"))


def _dispatch_cycle_id(state: dict[str, Any]) -> str:
    cycle_id = state.get("cycle")
    if cycle_id:
        return str(cycle_id)
    sub_unit = str(state.get("sub_unit") or "")
    if sub_unit:
        return Path(sub_unit).name
    return "unknown"


def record_dispatch_event(
    *,
    cycle_id: str,
    agent: str,
    action: str,
    round_num: int | None = None,
    details: str | None = None,
    root: Path | None = None,
    sub_unit: str | None = None,
    dispatch_mode: str | None = None,
    packet_path: str | None = None,
    prompt_path: str | None = None,
    result_path: str | None = None,
) -> None:
    """Persist a dispatch audit event without forcing a workspace rebuild."""
    conn = _get_or_create_db(root=_resolve_workspace_root(root))
    try:
        conn.execute(
            "INSERT INTO dispatches (timestamp, cycle_id, agent, action, round, details, sub_unit, dispatch_mode, "
            "packet_path, prompt_path, result_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(UTC).isoformat(),
                cycle_id,
                agent,
                action,
                round_num,
                details or "",
                sub_unit,
                dispatch_mode,
                packet_path,
                prompt_path,
                result_path,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_dispatch_log_payload(*, cycle: str | None = None, root: Path | None = None) -> list[dict[str, Any]]:
    """Return dispatch audit rows as JSON-friendly dictionaries."""
    conn = _get_or_create_db(root=_resolve_workspace_root(root))
    try:
        if cycle:
            rows = conn.execute(
                "SELECT * FROM dispatches WHERE cycle_id = ? ORDER BY timestamp",
                (cycle,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM dispatches ORDER BY timestamp").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _dispatch_event_exists(
    *,
    cycle_id: str,
    agent: str,
    action: str,
    round_num: int | None = None,
    result_path: str | None = None,
    sub_unit: str | None = None,
    root: Path | None = None,
) -> bool:
    """Return whether a matching dispatch lifecycle event already exists."""
    conn = _get_or_create_db(root=_resolve_workspace_root(root))
    try:
        sql = "SELECT 1 FROM dispatches WHERE cycle_id = ? AND agent = ? AND action = ?"
        params: list[Any] = [cycle_id, agent, action]
        if round_num is None:
            sql += " AND round IS NULL"
        else:
            sql += " AND round = ?"
            params.append(round_num)
        if result_path is None:
            sql += " AND result_path IS NULL"
        else:
            sql += " AND result_path = ?"
            params.append(result_path)
        if sub_unit is None:
            sql += " AND sub_unit IS NULL"
        else:
            sql += " AND sub_unit = ?"
            params.append(sub_unit)
        return conn.execute(sql, params).fetchone() is not None
    finally:
        conn.close()


def _sync_dispatch_receipts(sub_path: str, root: Path | None = None) -> None:
    """Record one-time receipt events for completed result artifacts."""
    from .orchestration import compute_paths, find_completed_rounds, read_dispatch_config

    research_root = _resolve_workspace_root(root)
    target = research_root / sub_path
    if not target.exists():
        return

    cycle_id = _dispatch_cycle_id({"sub_unit": sub_path})
    dispatch_config = read_dispatch_config(research_root)

    def _record_if_present(agent: str, round_num: int | None) -> None:
        paths = compute_paths(sub_path, agent, round_num)
        result_path = paths["result_path"]
        if not (research_root / result_path).exists():
            return
        if _dispatch_event_exists(
            cycle_id=cycle_id,
            agent=agent,
            action="received",
            round_num=round_num,
            result_path=result_path,
            sub_unit=sub_path,
            root=research_root,
        ):
            return
        record_dispatch_event(
            cycle_id=cycle_id,
            agent=agent,
            action="received",
            round_num=round_num,
            details="Result artifact received and available for orchestration.",
            root=research_root,
            sub_unit=sub_path,
            dispatch_mode=dispatch_config.get(agent, "internal"),
            packet_path=paths.get("packet_path"),
            prompt_path=paths.get("prompt_path"),
            result_path=result_path,
        )

    for role in ("architect", "adversary"):
        role_dir = target / role
        for round_num in find_completed_rounds(role_dir):
            _record_if_present(role, round_num)

    for role in ("experimenter", "arbiter"):
        _record_if_present(role, None)


def get_next_payload(path: str = "auto", root: Path | None = None) -> dict[str, Any]:
    """Determine the next action for a claim and return a JSON-friendly payload."""
    from .orchestration import (
        compute_paths,
        detect_state,
        extract_confidence,
        find_active_subunit,
        get_claim_north_star_status,
        list_context_files,
        load_config,
        read_dispatch_config,
    )

    research_root = _resolve_workspace_root(root)
    config = load_config(_cfg.DEFAULT_ORCH_CONFIG)
    sub_path = path
    if sub_path == "auto":
        found = find_active_subunit(research_root)
        if not found:
            return {
                "status": "no_active_claims",
                "message": "No active claims found. Use /principia:scaffold to create one.",
            }
        sub_path = found

    _sync_dispatch_receipts(sub_path, root=research_root)
    state = detect_state(research_root, sub_path, config)
    state["sub_unit"] = sub_path

    dispatch_config = read_dispatch_config(research_root)
    agent = state.get("agent")
    if agent:
        state["dispatch_mode"] = dispatch_config.get(agent, "internal")
        state.update(compute_paths(sub_path, agent, state.get("round")))

    agent = state["action"].removeprefix("dispatch_") if state["action"].startswith("dispatch_") else ""
    max_rounds = config.get("debate_loop", {}).get("max_rounds", 3)
    state["context_files"] = list_context_files(
        research_root,
        sub_path,
        state["action"],
        state.get("round"),
        agent=agent,
        max_rounds=max_rounds,
    )
    state["north_star"] = get_claim_north_star_status(research_root, sub_path)

    if state["action"].startswith("complete_"):
        verdict_path = research_root / sub_path / "arbiter" / "results" / "verdict.md"
        state["confidence"] = extract_confidence(verdict_path)

    return state


def _build_dispatch_artifacts(path: str, root: Path | None = None) -> dict[str, Any]:
    """Build the canonical packet and external prompt for the current dispatch."""
    from .orchestration import assemble_context, generate_dispatch_packet, generate_external_prompt

    research_root = _resolve_workspace_root(root)
    state = get_next_payload(path, root=research_root)
    agent = state.get("agent")
    if not agent:
        raise ValueError(state.get("message") or "No agent to dispatch in current state.")

    context = assemble_context(research_root, state["context_files"])
    instructions = _load_agent_instructions(agent)
    packet = generate_dispatch_packet(state, state["context_files"], context, instructions)
    prompt = generate_external_prompt(state, packet)
    return {
        "state": state,
        "context": context,
        "instructions": instructions,
        "packet": packet,
        "prompt": prompt,
    }


def write_packet_artifact(path: str, root: Path | None = None) -> dict[str, Any]:
    """Write the canonical packet artifact for the current dispatch."""
    research_root = _resolve_workspace_root(root)
    artifacts = _build_dispatch_artifacts(path, root=research_root)
    packet_path = research_root / artifacts["state"]["packet_path"]
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    _cfg._atomic_write(packet_path, artifacts["packet"])
    record_dispatch_event(
        cycle_id=_dispatch_cycle_id(artifacts["state"]),
        agent=artifacts["state"]["agent"],
        action="packet",
        round_num=artifacts["state"].get("round"),
        details="Canonical dispatch packet materialized.",
        root=research_root,
        sub_unit=artifacts["state"].get("sub_unit"),
        dispatch_mode=artifacts["state"].get("dispatch_mode"),
        packet_path=artifacts["state"].get("packet_path"),
        prompt_path=artifacts["state"].get("prompt_path"),
        result_path=artifacts["state"].get("result_path"),
    )
    return {
        "path": str(packet_path),
        "relative_path": artifacts["state"]["packet_path"],
        "sub_unit": artifacts["state"]["sub_unit"],
        "agent": artifacts["state"]["agent"],
    }


def write_prompt_artifact(path: str, root: Path | None = None) -> dict[str, Any]:
    """Write packet and prompt artifacts for the current dispatch."""
    research_root = _resolve_workspace_root(root)
    artifacts = _build_dispatch_artifacts(path, root=research_root)

    packet_path = research_root / artifacts["state"]["packet_path"]
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    _cfg._atomic_write(packet_path, artifacts["packet"])

    prompt_path = research_root / artifacts["state"]["prompt_path"]
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    _cfg._atomic_write(prompt_path, artifacts["prompt"])
    record_dispatch_event(
        cycle_id=_dispatch_cycle_id(artifacts["state"]),
        agent=artifacts["state"]["agent"],
        action="dispatch",
        round_num=artifacts["state"].get("round"),
        details="Dispatch artifacts materialized for agent handoff.",
        root=research_root,
        sub_unit=artifacts["state"].get("sub_unit"),
        dispatch_mode=artifacts["state"].get("dispatch_mode"),
        packet_path=artifacts["state"].get("packet_path"),
        prompt_path=artifacts["state"].get("prompt_path"),
        result_path=artifacts["state"].get("result_path"),
    )

    return {
        "path": str(prompt_path),
        "relative_path": artifacts["state"]["prompt_path"],
        "packet_path": artifacts["state"]["packet_path"],
        "sub_unit": artifacts["state"]["sub_unit"],
        "agent": artifacts["state"]["agent"],
    }


def get_patch_status_payload(root: Path | None = None) -> dict[str, Any]:
    """Return north-star/claim alignment status for the workspace."""
    from .orchestration import collect_north_star_alignment

    return collect_north_star_alignment(_resolve_workspace_root(root))


def cmd_log_dispatch(args: argparse.Namespace) -> None:
    """Log a dispatch event to the dispatches table."""
    record_dispatch_event(
        cycle_id=args.cycle,
        agent=args.agent,
        action=args.action,
        round_num=args.round,
        details=args.details,
        sub_unit=getattr(args, "sub_unit", None),
        dispatch_mode=getattr(args, "dispatch_mode", None),
        packet_path=getattr(args, "packet_path", None),
        prompt_path=getattr(args, "prompt_path", None),
        result_path=getattr(args, "result_path", None),
    )
    print(f"Logged: {args.action} {args.agent} (cycle {args.cycle})")


def _legacy_cmd_dispatch_log(args: argparse.Namespace) -> None:
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
            f"{r['timestamp']:<28} {r['cycle_id']:<25} {r['agent']:<12} {r['action']:<16} {rnd:<6} {r['details'] or ''}"
        )
    print(f"\n({len(rows)} dispatch(es))")


def _legacy_cmd_next(args: argparse.Namespace) -> None:
    """Determine next action for a claim (or legacy sub-unit)."""
    from .orchestration import (
        compute_paths,
        detect_state,
        extract_confidence,
        find_active_subunit,
        list_context_files,
        load_config,
        read_dispatch_config,
    )

    config = load_config(_cfg.DEFAULT_ORCH_CONFIG)
    sub_path = args.path
    if sub_path != "auto":
        _check_path_containment(sub_path)
    if sub_path == "auto":
        found = find_active_subunit(_cfg.RESEARCH_DIR)
        if not found:
            print("No active claims found. Use /principia:scaffold to create one.")
            return
        sub_path = found
        print(f"Auto-detected: {sub_path}", file=sys.stderr)

    state = detect_state(_cfg.RESEARCH_DIR, sub_path, config)
    state["sub_unit"] = sub_path

    # Enrich with dispatch mode
    dispatch_config = read_dispatch_config(_cfg.RESEARCH_DIR)
    agent = state.get("agent")
    if agent:
        state["dispatch_mode"] = dispatch_config.get(agent, "internal")
        paths = compute_paths(sub_path, agent, state.get("round"))
        state.update(paths)

    # Enrich with context files (agent-aware filtering for knowledge divergence)
    agent = state["action"].removeprefix("dispatch_") if state["action"].startswith("dispatch_") else ""
    mr = config.get("debate_loop", {}).get("max_rounds", 3)
    state["context_files"] = list_context_files(
        _cfg.RESEARCH_DIR, sub_path, state["action"], state.get("round"), agent=agent, max_rounds=mr
    )

    # Enrich complete states with verdict confidence
    if state["action"].startswith("complete_"):
        verdict_path = _cfg.RESEARCH_DIR / sub_path / "arbiter" / "results" / "verdict.md"
        state["confidence"] = extract_confidence(verdict_path)

    print(json.dumps(state, indent=2))


def cmd_context(args: argparse.Namespace) -> None:
    """Assemble context document for the next agent."""
    from .orchestration import assemble_context, detect_state, list_context_files, load_config

    _check_path_containment(args.path)
    config = load_config(_cfg.DEFAULT_ORCH_CONFIG)
    state = detect_state(_cfg.RESEARCH_DIR, args.path, config)
    agent = state["action"].removeprefix("dispatch_") if state["action"].startswith("dispatch_") else ""
    mr = config.get("debate_loop", {}).get("max_rounds", 3)
    files = list_context_files(
        _cfg.RESEARCH_DIR, args.path, state["action"], state.get("round"), agent=agent, max_rounds=mr
    )
    doc = assemble_context(_cfg.RESEARCH_DIR, files)
    print(doc)


def _legacy_cmd_prompt(args: argparse.Namespace) -> None:
    """Generate self-contained prompt for external agent dispatch."""
    cmd_prompt(args)


def cmd_dispatch_log(args: argparse.Namespace) -> None:
    """Show dispatch audit trail."""
    rows = get_dispatch_log_payload(cycle=args.cycle)

    if not rows:
        if args.json:
            emit_envelope([])
        else:
            print("No dispatches logged.")
        return

    if args.json:
        emit_envelope(rows)
        return

    print(f"{'Timestamp':<28} {'Cycle':<25} {'Agent':<12} {'Action':<16} {'Round':<6} Details")
    print("-" * 110)
    for row in rows:
        round_value = str(row["round"]) if row["round"] is not None else "-"
        details = row["details"] or ""
        if row.get("sub_unit"):
            details = f"{details} [{row['sub_unit']}]".strip()
        print(
            f"{row['timestamp']:<28} {row['cycle_id']:<25} {row['agent']:<12} "
            f"{row['action']:<16} {round_value:<6} {details}"
        )
    print(f"\n({len(rows)} dispatch(es))")


def cmd_next(args: argparse.Namespace) -> None:
    """Determine next action for a claim (or legacy sub-unit)."""
    sub_path = args.path
    if sub_path != "auto":
        _check_path_containment(sub_path)
    emit_envelope(get_next_payload(sub_path))


def cmd_packet(args: argparse.Namespace) -> None:
    """Generate the canonical packet for the next agent dispatch."""
    _check_path_containment(args.path)
    try:
        result = write_packet_artifact(args.path)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    print(f"Written: {result['path']}")


def cmd_prompt(args: argparse.Namespace) -> None:
    """Generate self-contained prompt for external agent dispatch."""
    _check_path_containment(args.path)
    try:
        result = write_prompt_artifact(args.path)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    print(f"Written: {result['path']}")


def cmd_waves(args: argparse.Namespace) -> None:
    """Show execution waves based on dependency topological sort."""
    from .orchestration import compute_waves

    waves = compute_waves(_cfg.RESEARCH_DIR)
    if not waves:
        if getattr(args, "json", False):
            emit_envelope([])
        else:
            print("No nodes in database. Run 'build' first.")
        return

    if getattr(args, "json", False):
        out = [[dict(n) for n in wave] for wave in waves]
        emit_envelope(out)
        return

    for i, wave in enumerate(waves, 1):
        print(f"\nWave {i}:")
        for node in wave:
            maturity = node.get("maturity") or "—"
            status = node["status"]
            title = node.get("title") or node["id"]
            print(f"  [{maturity:<15}] {status:<12} {title} ({node['id']})")
    print(f"\n{len(waves)} wave(s), {sum(len(w) for w in waves)} node(s)")


def cmd_investigate_next(args: argparse.Namespace) -> None:
    """Determine next action for the full investigation."""
    from .orchestration import detect_investigation_state, load_config

    config = load_config(_cfg.DEFAULT_ORCH_CONFIG)
    quick = getattr(args, "quick", False)
    if quick:
        # Quick mode: override to 1 debate round
        config = {**config}
        config["debate_loop"] = {**config.get("debate_loop", {}), "max_rounds": 1}
    state = detect_investigation_state(_cfg.RESEARCH_DIR, config, quick=quick)
    state["breadcrumb"] = _format_investigation_breadcrumb(state, _cfg.RESEARCH_DIR)
    emit_envelope(state)


def cmd_parse_framework(args: argparse.Namespace) -> None:
    """Parse claim registry from blueprint.md (or legacy framework.md)."""
    from .orchestration import parse_framework

    framework_path = _cfg.RESEARCH_DIR / "blueprint.md"
    claims = parse_framework(framework_path)
    if not claims:
        print("No claim registry found in blueprint.md.")
        print("Ensure the synthesizer included a ```yaml block with # CLAIM_REGISTRY.", file=sys.stderr)
        sys.exit(1)
    emit_envelope(claims)


def cmd_autonomy_config(args: argparse.Namespace) -> None:
    """Output autonomy configuration as JSON."""
    from .orchestration import read_autonomy_config, read_repo_config

    result = read_autonomy_config(_cfg.DEFAULT_ORCH_CONFIG)
    repo_config = read_repo_config(_cfg.RESEARCH_DIR)
    if repo_config.get("workflow_autonomy") in ("checkpoints", "yolo"):
        result["mode"] = repo_config["workflow_autonomy"]
    emit_envelope(result)


def _build_init_status(workspace_exists: bool, research_root: Path, inv_state: dict[str, Any]) -> dict[str, object]:
    north_star_path = research_root / ".north-star.md"
    context_path = research_root / ".context.md"
    config_path = research_root / ".config.md"
    claims_dir = research_root / "claims"
    claims_scaffolded = claims_dir.exists() and any(child.is_dir() for child in claims_dir.iterdir())

    if not workspace_exists:
        status = "missing_workspace"
    elif not north_star_path.exists():
        status = "discussion_in_progress"
    elif inv_state.get("action") in {"divide", "scaffold", "scaffold_quick"} and not claims_scaffolded:
        status = "ready_for_claims"
    elif inv_state.get("phase") == "understand":
        status = "north_star_locked"
    else:
        status = "workflow_active"

    return {
        "status": status,
        "workspace_root": str(research_root),
        "workspace_exists": workspace_exists,
        "north_star_locked": north_star_path.exists(),
        "context_exists": context_path.exists(),
        "config_exists": config_path.exists(),
        "claims_scaffolded": claims_scaffolded,
    }


def _dispatch_row_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "agent": row["agent"],
        "action": row["action"],
        "round": row["round"],
        "timestamp": row["timestamp"],
        "details": row["details"],
        "dispatch_mode": row["dispatch_mode"],
        "packet_path": row["packet_path"],
        "prompt_path": row["prompt_path"],
        "result_path": row["result_path"],
    }


def _waiting_matches_handoff(waiting_for: str | None, agent: str, round_num: int | None) -> bool:
    if not waiting_for:
        return False
    if round_num is None:
        return waiting_for == agent
    return waiting_for == f"{agent} round {round_num}"


def _classify_dispatch_handoff(row: sqlite3.Row, claim_state: dict[str, Any]) -> str:
    action = str(row["action"])
    if action in {"received", "recorded"}:
        return action

    agent = str(row["agent"])
    round_num = row["round"]
    claim_action = str(claim_state.get("action") or "")

    if action == "packet":
        if claim_action == f"dispatch_{agent}" and (round_num is None or claim_state.get("round") == round_num):
            return "ready_to_send"
        return "stale"

    if action == "dispatch":
        if claim_action == "waiting" and _waiting_matches_handoff(claim_state.get("waiting_for"), agent, round_num):
            return "waiting_result"
        return "stale"

    return action


def _summarize_dispatch_lifecycle(
    conn: sqlite3.Connection,
    research_root: Path,
    config: dict[str, Any],
    sub_unit: str | None,
) -> dict[str, object]:
    """Summarize the active claim's dispatch lifecycle from structured audit rows."""
    from .orchestration import detect_state

    if not sub_unit:
        row = conn.execute(
            "SELECT sub_unit FROM dispatches WHERE sub_unit IS NOT NULL ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if not row or not row["sub_unit"]:
            return {"claim": None, "latest": None, "handoffs": [], "outstanding": [], "stale": []}
        sub_unit = str(row["sub_unit"])

    _sync_dispatch_receipts(sub_unit, root=research_root)
    rows = conn.execute(
        "SELECT * FROM dispatches WHERE sub_unit = ? ORDER BY timestamp",
        (sub_unit,),
    ).fetchall()
    if not rows:
        return {"claim": sub_unit, "latest": None, "handoffs": [], "outstanding": [], "stale": []}

    claim_state = detect_state(research_root, sub_unit, config)
    latest = _dispatch_row_payload(rows[-1])
    latest["status"] = _classify_dispatch_handoff(rows[-1], claim_state)
    handoffs: dict[tuple[str, int | None, str | None], sqlite3.Row] = {}
    for row in rows:
        key = (row["agent"], row["round"], row["result_path"])
        handoffs[key] = row

    handoff_rows: list[dict[str, Any]] = []
    for row in handoffs.values():
        payload = _dispatch_row_payload(row)
        payload["status"] = _classify_dispatch_handoff(row, claim_state)
        handoff_rows.append(payload)
    handoff_rows.sort(key=lambda row: row["timestamp"])
    outstanding = [row for row in handoff_rows if row["status"] in {"ready_to_send", "waiting_result", "stale"}]
    stale = [row for row in handoff_rows if row["status"] == "stale"]

    return {
        "claim": sub_unit,
        "latest": latest,
        "handoffs": handoff_rows,
        "outstanding": outstanding,
        "stale": stale,
    }


def _summarize_workspace_dispatches(
    conn: sqlite3.Connection,
    research_root: Path,
    config: dict[str, Any],
) -> dict[str, object]:
    """Summarize dispatch lifecycle health across every claim with audit rows."""
    rows = conn.execute(
        "SELECT sub_unit, MAX(timestamp) AS last_timestamp "
        "FROM dispatches WHERE sub_unit IS NOT NULL GROUP BY sub_unit ORDER BY last_timestamp DESC"
    ).fetchall()
    if not rows:
        return {
            "claim_count": 0,
            "stale_claim_count": 0,
            "outstanding_claim_count": 0,
            "stale_handoff_count": 0,
            "claims": [],
            "stale_claims": [],
        }

    claims: list[dict[str, Any]] = []
    for row in rows:
        sub_unit = str(row["sub_unit"])
        lifecycle = _summarize_dispatch_lifecycle(conn, research_root, config, sub_unit)
        handoffs = cast(list[dict[str, Any]], lifecycle["handoffs"])
        outstanding = cast(list[dict[str, Any]], lifecycle["outstanding"])
        stale = cast(list[dict[str, Any]], lifecycle["stale"])
        ready_to_send = [handoff for handoff in handoffs if handoff["status"] == "ready_to_send"]
        waiting_result = [handoff for handoff in handoffs if handoff["status"] == "waiting_result"]
        claims.append(
            {
                "claim": lifecycle["claim"],
                "latest": lifecycle["latest"],
                "outstanding_count": len(outstanding),
                "stale_count": len(stale),
                "ready_to_send_count": len(ready_to_send),
                "waiting_result_count": len(waiting_result),
                "outstanding": outstanding,
                "stale": stale,
                "ready_to_send": ready_to_send,
                "waiting_result": waiting_result,
            }
        )

    stale_claims = [claim for claim in claims if claim["stale_count"] > 0]
    outstanding_claims = [claim for claim in claims if claim["outstanding_count"] > 0]
    ready_to_send_claims = [claim for claim in claims if claim["ready_to_send_count"] > 0]
    waiting_result_claims = [claim for claim in claims if claim["waiting_result_count"] > 0]
    stale_handoff_count = sum(int(claim["stale_count"]) for claim in stale_claims)
    ready_to_send_handoff_count = sum(int(claim["ready_to_send_count"]) for claim in ready_to_send_claims)
    waiting_result_handoff_count = sum(int(claim["waiting_result_count"]) for claim in waiting_result_claims)

    return {
        "claim_count": len(claims),
        "stale_claim_count": len(stale_claims),
        "outstanding_claim_count": len(outstanding_claims),
        "stale_handoff_count": stale_handoff_count,
        "ready_to_send_claim_count": len(ready_to_send_claims),
        "ready_to_send_handoff_count": ready_to_send_handoff_count,
        "waiting_result_claim_count": len(waiting_result_claims),
        "waiting_result_handoff_count": waiting_result_handoff_count,
        "claims": claims,
        "stale_claims": stale_claims,
        "ready_to_send_claims": ready_to_send_claims,
        "waiting_result_claims": waiting_result_claims,
    }


def get_dashboard_payload(root: Path | None = None) -> dict[str, object]:
    """Build the dashboard payload for a workspace without printing."""
    from .orchestration import (
        collect_north_star_alignment,
        detect_investigation_state,
        load_config,
        read_autonomy_config,
        read_repo_config,
    )

    research_root = _cfg.RESEARCH_DIR.resolve() if root is None else root.resolve()
    workspace_exists = research_root.exists()
    config = load_config(_cfg.DEFAULT_ORCH_CONFIG)
    conn = build_db(root=research_root)

    # Investigation state
    inv_state = detect_investigation_state(research_root, config)
    phase = inv_state.get("phase", "unknown")
    action = inv_state.get("action", "unknown")
    breadcrumb = _format_investigation_breadcrumb(inv_state, research_root)

    # Active claim
    active_claim = inv_state.get("sub_unit")
    active_cycle = inv_state.get("cycle")
    dispatch_lifecycle = _summarize_dispatch_lifecycle(
        conn,
        research_root,
        config,
        active_claim if isinstance(active_claim, str) else None,
    )
    dispatch_overview = _summarize_workspace_dispatches(conn, research_root, config)

    # Last verdict
    last_verdict_row = conn.execute(
        "SELECT l.node_id, l.event, l.timestamp FROM ledger l "
        "JOIN nodes n ON n.id = l.node_id "
        "WHERE l.event IN ('proven', 'disproven', 'partial', 'inconclusive') "
        f"AND {_primary_claim_path_sql('n.file_path')} "
        "ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    last_verdict = None
    if last_verdict_row:
        last_verdict = {
            "claim": last_verdict_row["node_id"],
            "verdict": last_verdict_row["event"].upper(),
            "timestamp": last_verdict_row["timestamp"],
        }

    # Claim summary
    claim_counts = {}
    for status in ("pending", "active", "proven", "disproven", "partial", "weakened", "inconclusive"):
        count = conn.execute(
            f"SELECT COUNT(*) as c FROM nodes WHERE {_primary_claim_path_sql()} AND status = ?",
            (status,),
        ).fetchone()["c"]
        if count > 0:
            claim_counts[status] = count

    # Blocked claims (pending with unresolved dependencies)
    blocked = conn.execute(
        "SELECT n.id, dep.id as dep_id FROM nodes n "
        "JOIN edges e ON e.source_id = n.id AND e.relation IN ('depends_on', 'assumes') "
        "JOIN nodes dep ON dep.id = e.target_id AND dep.status NOT IN ('proven') "
        f"WHERE n.status = 'pending' AND {_primary_claim_path_sql('n.file_path')}"
    ).fetchall()
    blocked_claims = [{"id": b["id"], "blocked_by": b["dep_id"]} for b in blocked]

    # Pending human decisions (partial/inconclusive claims needing user input)
    pending_decisions = conn.execute(
        "SELECT id, status, file_path FROM nodes "
        "WHERE status IN ('partial', 'inconclusive') "
        f"AND {_primary_claim_path_sql()} "
        "ORDER BY file_path"
    ).fetchall()
    decisions = [{"id": d["id"], "status": d["status"], "file": d["file_path"]} for d in pending_decisions]

    # Repo-local config
    repo_config = read_repo_config(research_root)

    # Autonomy config
    autonomy = read_autonomy_config(_cfg.DEFAULT_ORCH_CONFIG)
    if repo_config.get("workflow_autonomy") in ("checkpoints", "yolo"):
        autonomy["mode"] = repo_config["workflow_autonomy"]

    init = _build_init_status(workspace_exists, research_root, inv_state)
    patch_status = collect_north_star_alignment(research_root)
    warnings: list[dict[str, object]] = []

    if patch_status.get("needs_review_count", 0):
        warnings.append(
            {
                "code": "north_star_drift",
                "severity": "warning",
                "message": (
                    f"{patch_status['needs_review_count']} claim(s) are stale or missing a north-star version stamp."
                ),
                "count": patch_status["needs_review_count"],
                "claims": patch_status["needs_review"][:5],
            }
        )
    if dispatch_overview.get("stale_claim_count", 0):
        stale_claims = cast(list[dict[str, Any]], dispatch_overview["stale_claims"])
        warnings.append(
            {
                "code": "dispatch_handoff_stale",
                "severity": "warning",
                "message": (
                    f"{dispatch_overview['stale_handoff_count']} handoff(s) across "
                    f"{dispatch_overview['stale_claim_count']} claim(s) no longer match the current "
                    "filesystem/orchestration state."
                ),
                "count": dispatch_overview["stale_handoff_count"],
                "claim_count": dispatch_overview["stale_claim_count"],
                "claims": stale_claims[:5],
            }
        )

    result: dict[str, object] = {
        "phase": phase,
        "action": action,
        "breadcrumb": breadcrumb,
        "active_claim": active_claim,
        "active_cycle": active_cycle,
        "dispatch_lifecycle": dispatch_lifecycle,
        "dispatch_overview": dispatch_overview,
        "last_verdict": last_verdict,
        "claims": claim_counts,
        "blocked": blocked_claims,
        "pending_decisions": decisions,
        "autonomy": autonomy,
        "init": init,
        "patch_status": patch_status,
        "warnings": warnings,
        "preferences": {
            "workflow_autonomy": repo_config.get("workflow_autonomy") or autonomy["mode"],
            "sidecars": repo_config["sidecars"],
            "dispatch": repo_config["dispatch"],
        },
    }
    conn.close()
    return result


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Single-view control panel: phase, active claim, last verdict, blockers, config."""
    emit_envelope(get_dashboard_payload(root=_cfg.RESEARCH_DIR))


def cmd_reopen(args: argparse.Namespace) -> None:
    """Re-evaluate a completed claim by deleting its verdict and resetting to active.

    The claim's debate and experiment artifacts are preserved. The state machine
    will route to dispatch_arbiter (re-verdict), not back to debate.
    """
    conn = build_db()
    node_id = args.id

    node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    if not node:
        print(f"ERROR: Node '{node_id}' not found.")
        sys.exit(1)
    if not _is_primary_claim_path(node["file_path"]):
        print(f"ERROR: Node '{node_id}' is not a primary claim.")
        sys.exit(1)

    if node["status"] in ("pending", "active"):
        print(f"WARN: Node '{node_id}' is already {node['status']} — nothing to reopen.")
        return

    old_status = node["status"]
    fpath = _cfg.RESEARCH_DIR / node["file_path"]

    # If disproven, clear falsified_by and revert cascade (same logic as replace-verdict)
    if old_status == "disproven":
        affected = _find_cascade_targets(conn, node_id)
        for dep_id, fp, dep_status in affected:
            if dep_status != "weakened":
                continue
            other_disproven = conn.execute(
                "SELECT COUNT(*) as c FROM edges e "
                "JOIN nodes n ON n.id = e.target_id "
                "WHERE e.source_id = ? AND e.relation IN ('depends_on', 'assumes') "
                "AND n.status = 'disproven' AND n.id != ?",
                (dep_id, node_id),
            ).fetchone()["c"]
            if other_disproven > 0:
                print(f"   Kept: {dep_id} still weakened (other disproven dependencies)")
                continue
            wp = _cfg.RESEARCH_DIR / fp
            if wp.exists():
                restored, restored_status, restored_conf = _restore_weakened_state(wp)
                if restored:
                    conn.execute(
                        "UPDATE nodes SET status = ?, confidence = ? WHERE id = ?",
                        (restored_status, restored_conf, dep_id),
                    )
                    print(f"   Reverted: {dep_id} weakened → {restored_status}")

    # Update frontmatter — clear falsified_by if present
    updates: dict[str, str] = {"status": "active"}
    if old_status == "disproven":
        updates["falsified_by"] = ""
    if not _update_frontmatter_in_file(fpath, updates):
        print(f"ERROR: Could not update file for '{node_id}' — aborting.")
        sys.exit(1)

    # Update DB
    conn.execute("UPDATE nodes SET status = 'active' WHERE id = ?", (node_id,))

    # Remove post-verdict marker and verdict file so state machine doesn't
    # treat the claim as complete via mtime fallback
    claim_dir = fpath.parent
    marker = claim_dir / ".post_verdict_done"
    if marker.exists():
        marker.unlink()
    verdict_file = claim_dir / "arbiter" / "results" / "verdict.md"
    if verdict_file.exists():
        verdict_file.unlink()
        print(f"   Removed verdict: {verdict_file.relative_to(_cfg.RESEARCH_DIR)}")

    # Ledger entry
    today = date.today().isoformat()
    conn.execute(
        "INSERT INTO ledger (timestamp, event, node_id, details, agent) VALUES (?, ?, ?, ?, ?)",
        (today, "reopened", node_id, f"Reopened from {old_status}", "user"),
    )
    conn.commit()

    print(f"Reopened: {node_id} ({old_status} → active)")
    print(f"   File: {node['file_path']}")


def cmd_replace_verdict(args: argparse.Namespace) -> None:
    """Delete existing verdict and reset claim to experimenter-done state."""
    sub_path = args.path
    _check_path_containment(sub_path)
    target = _cfg.RESEARCH_DIR / sub_path

    if not target.exists():
        print(f"ERROR: Path not found: {target}")
        sys.exit(1)

    verdict_file = target / "arbiter" / "results" / "verdict.md"
    if not verdict_file.exists():
        print(f"ERROR: No verdict file found at {verdict_file}")
        sys.exit(1)

    claim_file, claim_meta, node_id = _load_primary_claim(target)

    # If claim was disproven, revert cascade — but only for nodes whose
    # SOLE reason for being weakened is this claim.  A node that depends
    # on two disproven claims must stay weakened until both are reverted.
    conn: sqlite3.Connection | None = None
    if claim_meta.get("status") == "disproven":
        conn = build_db()
        affected = _find_cascade_targets(conn, node_id)
        for dep_id, fp, status in affected:
            if status != "weakened":
                continue
            # Check for other live disproven dependencies
            other_disproven = conn.execute(
                "SELECT COUNT(*) as c FROM edges e "
                "JOIN nodes n ON n.id = e.target_id "
                "WHERE e.source_id = ? AND e.relation IN ('depends_on', 'assumes') "
                "AND n.status = 'disproven' AND n.id != ?",
                (dep_id, node_id),
            ).fetchone()["c"]
            if other_disproven > 0:
                print(f"Kept: {dep_id} still weakened (other disproven dependencies)")
                continue
            wp = _cfg.RESEARCH_DIR / fp
            if wp.exists():
                restored, restored_status, restored_conf = _restore_weakened_state(wp)
                if restored:
                    conn.execute(
                        "UPDATE nodes SET status = ?, confidence = ? WHERE id = ?",
                        (restored_status, restored_conf, dep_id),
                    )
                    print(f"Reverted: {dep_id} weakened → {restored_status}")
    # Clear falsified_by from frontmatter and reset to active
    updates: dict[str, str] = {"status": "active"}
    if claim_meta.get("falsified_by"):
        updates["falsified_by"] = ""
    if not _update_frontmatter_in_file(claim_file, updates):
        print(f"WARN: Could not update frontmatter in {claim_file}")

    if conn is not None:
        conn.commit()
        conn.close()

    # Remove verdict file
    verdict_file.unlink()
    print(f"Removed: {verdict_file.relative_to(_cfg.RESEARCH_DIR)}")

    # Remove post-verdict marker
    marker = target / ".post_verdict_done"
    if marker.exists():
        marker.unlink()
        print("Removed: .post_verdict_done marker")

    # Ledger entry
    conn = build_db()
    today = date.today().isoformat()
    conn.execute(
        "INSERT INTO ledger (timestamp, event, node_id, details, agent) VALUES (?, ?, ?, ?, ?)",
        (today, "verdict_replaced", node_id, f"Verdict removed from {sub_path}", "user"),
    )
    conn.commit()

    print(f"Claim reset to pre-verdict state. Run `/principia:step {sub_path}` to re-dispatch arbiter.")


def cmd_extend_debate(args: argparse.Namespace) -> None:
    """Extend max debate rounds for a specific claim."""
    _check_path_containment(args.path)
    target = _cfg.RESEARCH_DIR / args.path
    if not target.exists():
        print(f"ERROR: Path not found: {target}")
        sys.exit(1)

    override_file = target / ".max_rounds_override"
    override_file.write_text(str(args.to), encoding="utf-8")
    print(f"Debate extended to {args.to} rounds for {args.path}")


# ---------------------------------------------------------------------------
# Discovery commands (paths, roles, phases, schema)
# ---------------------------------------------------------------------------


def cmd_paths(args: argparse.Namespace) -> None:
    """Emit workspace path layout as versioned JSON."""
    data = {
        "root": str(_cfg.RESEARCH_DIR),
        "db": str(_cfg.DB_PATH),
        "claims_dir": str(_cfg.RESEARCH_DIR / "claims"),
        "context_dir": str(_cfg.CONTEXT_DIR),
        "progress": str(_cfg.PROGRESS_PATH),
        "foundations": str(_cfg.FOUNDATIONS_PATH),
        "config": str(_cfg.RESEARCH_DIR / ".config.md"),
        "results": str(_cfg.RESEARCH_DIR / "RESULTS.md"),
        "synthesis": str(_cfg.RESEARCH_DIR / "synthesis.md"),
        "composition": str(_cfg.RESEARCH_DIR / "composition.md"),
    }
    emit_envelope(data)


def cmd_roles(args: argparse.Namespace) -> None:
    """Emit the role registry from orchestration config as JSON."""
    from .orchestration import load_config

    cfg = load_config(_cfg.DEFAULT_ORCH_CONFIG)
    roles_data = []
    for role in cfg.get("roles", []):
        if not isinstance(role, dict):
            continue
        entry: dict[str, Any] = {"name": role.get("name")}
        if "type" in role:
            entry["type"] = role["type"]
        # Assign phase from phases mapping
        for phase_name, phase_spec in cfg.get("phases", {}).items():
            if isinstance(phase_spec, dict) and role.get("name") in phase_spec.get("roles", []):
                entry["phase"] = phase_name
                break
        roles_data.append(entry)
    emit_envelope(roles_data)


def cmd_phases(args: argparse.Namespace) -> None:
    """Emit the phase machinery from orchestration config as JSON."""
    from .orchestration import load_config

    cfg = load_config(_cfg.DEFAULT_ORCH_CONFIG)
    phases_data = []
    for phase_name, phase_spec in cfg.get("phases", {}).items():
        if not isinstance(phase_spec, dict):
            continue
        entry: dict[str, Any] = {
            "name": phase_name,
            "roles": list(phase_spec.get("roles", [])),
        }
        if "exit_condition" in phase_spec:
            entry["exit_condition"] = phase_spec["exit_condition"]
        phases_data.append(entry)
    emit_envelope(phases_data)


def cmd_schema(args: argparse.Namespace) -> None:
    """Emit the frontmatter value sets as JSON."""
    from .ids import VALID_CONFIDENCES, VALID_MATURITIES, VALID_STATUSES, VALID_TYPES

    data = {
        "types": sorted(VALID_TYPES),
        "statuses": sorted(VALID_STATUSES),
        "maturities": sorted(v for v in VALID_MATURITIES if v is not None),
        "confidences": sorted(v for v in VALID_CONFIDENCES if v is not None),
    }
    emit_envelope(data)
