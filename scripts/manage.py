#!/usr/bin/env python3
"""
Principia — design management system for algorithm design from first principles.

User-facing commands:
    scaffold <level> <name> Create claim structure (legacy: cycle/unit/sub-unit)
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
import textwrap
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from db import (
    _find_cascade_targets,
    _update_frontmatter_in_file,
    build_db,
)
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
    extract_title as extract_title,
)
from frontmatter import (
    get_body,
    parse_frontmatter,
    serialise_frontmatter,
)
from ids import (
    derive_id,
    infer_type_from_path,
)
from reports import (
    _format_investigation_breadcrumb,
    cmd_assumptions,
    cmd_codebook,
    cmd_results,
    cmd_status,
)
from validation import cmd_validate, cmd_validate_paste

import config as _cfg
from config import (
    DEFAULT_ORCH_CONFIG,
    PLUGIN_ROOT,
    _atomic_write,
    _emit_progress,
    init_paths,
    rel_path_from_root,
)

# Re-export path globals from config so tests can do `from manage import DB_PATH` etc.
# These are live aliases: callers that import them by name get the current config value.
_PATH_GLOBALS = frozenset({"RESEARCH_DIR", "DB_PATH", "CONTEXT_DIR", "PROGRESS_PATH", "FOUNDATIONS_PATH"})


def __getattr__(name: str) -> object:
    if name in _PATH_GLOBALS:
        return getattr(_cfg, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
    if not str(full).startswith(str(_cfg.RESEARCH_DIR.resolve())):
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
    from orchestration import attenuate_confidence

    for dep_id, dep_fp, dep_status in affected:
        if dep_status != "disproven":
            dep_fpath = _cfg.RESEARCH_DIR / dep_fp
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
    from orchestration import extract_confidence, extract_verdict, load_config

    config = load_config(DEFAULT_ORCH_CONFIG)
    sub_path = args.path
    target = _cfg.RESEARCH_DIR / sub_path

    verdict_file = target / "arbiter" / "results" / "verdict.md"
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

    claim_file = target / "claim.md"
    node_id: str | None = None
    if claim_file.exists():
        meta = parse_frontmatter(claim_file.read_text(encoding="utf-8"))
        node_id = meta.get("id")  # type: ignore[assignment]

    # Apply verdict (extract_verdict now returns principia names: PROVEN, DISPROVEN, PARTIAL)
    if verdict == "PROVEN" and node_id:
        node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if node and node["status"] not in ("proven", "disproven"):
            _update_frontmatter_in_file(claim_file, {"status": "proven"})
            conn.execute("UPDATE nodes SET status = 'proven' WHERE id = ?", (node_id,))
            changes.append(f"Proven: {node_id}")

    elif verdict == "DISPROVEN" and node_id:
        node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if node and node["status"] != "disproven":
            verdict_id = derive_id(str(verdict_file.relative_to(_cfg.RESEARCH_DIR)))
            _update_frontmatter_in_file(claim_file, {"status": "disproven", "falsified_by": verdict_id})
            conn.execute("UPDATE nodes SET status = 'disproven' WHERE id = ?", (node_id,))
            changes.append(f"Disproven: {node_id} by {verdict_id}")
            # Cascade — weaken dependents
            cascade_targets = _find_cascade_targets(conn, node_id)
            from orchestration import attenuate_confidence

            for dep_id, dep_fp, dep_status in cascade_targets:
                if dep_status != "disproven":
                    dep_fpath = _cfg.RESEARCH_DIR / dep_fp
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
        _update_frontmatter_in_file(claim_file, {"status": new_status})
        conn.execute("UPDATE nodes SET status = ? WHERE id = ?", (new_status, node_id))
        changes.append(f"Updated {node_id} to {new_status}")

    # Ledger entry
    today = date.today().isoformat()
    verdict_rel = str(verdict_file.relative_to(_cfg.RESEARCH_DIR)) if verdict_file.exists() else ""
    conn.execute(
        "INSERT INTO ledger (timestamp, event, node_id, details, agent) VALUES (?, ?, ?, ?, ?)",
        (
            today,
            "post_verdict",
            node_id or "unknown",
            f"Verdict: {verdict}, Confidence: {confidence}, File: {verdict_rel}",
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

    _emit_progress("scaffolding", f"scaffold_{level}", name)

    # Create claim.md with frontmatter
    frontier_name = "claim.md"
    frontier = target / frontier_name
    rel = rel_path_from_root(frontier)
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


def cmd_log_dispatch(args: argparse.Namespace) -> None:
    """Log a dispatch event to the dispatches table."""
    conn = build_db()
    conn.execute(
        "INSERT INTO dispatches (timestamp, cycle_id, agent, action, round, details) VALUES (?, ?, ?, ?, ?, ?)",
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
            f"{r['timestamp']:<28} {r['cycle_id']:<25} {r['agent']:<12} {r['action']:<16} {rnd:<6} {r['details'] or ''}"
        )
    print(f"\n({len(rows)} dispatch(es))")


def cmd_next(args: argparse.Namespace) -> None:
    """Determine next action for a claim (or legacy sub-unit)."""
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
    from orchestration import assemble_context, detect_state, list_context_files, load_config

    config = load_config(DEFAULT_ORCH_CONFIG)
    state = detect_state(_cfg.RESEARCH_DIR, args.path, config)
    agent = state["action"].removeprefix("dispatch_") if state["action"].startswith("dispatch_") else ""
    mr = config.get("debate_loop", {}).get("max_rounds", 3)
    files = list_context_files(
        _cfg.RESEARCH_DIR, args.path, state["action"], state.get("round"), agent=agent, max_rounds=mr
    )
    doc = assemble_context(_cfg.RESEARCH_DIR, files)
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
    state = detect_state(_cfg.RESEARCH_DIR, args.path, config)
    agent = state.get("agent")
    if not agent:
        print("ERROR: No agent to dispatch in current state.")
        sys.exit(1)

    paths = compute_paths(args.path, agent, state.get("round"))
    state.update(paths)

    mr = config.get("debate_loop", {}).get("max_rounds", 3)
    files = list_context_files(
        _cfg.RESEARCH_DIR, args.path, state["action"], state.get("round"), agent=agent, max_rounds=mr
    )
    context = assemble_context(_cfg.RESEARCH_DIR, files)

    # Read agent instructions
    agent_file = PLUGIN_ROOT / "agents" / f"{agent}.md"
    instructions = ""
    if agent_file.exists():
        instructions = get_body(agent_file.read_text(encoding="utf-8"))

    prompt = generate_external_prompt(state, context, instructions)

    # Write to prompt_path
    prompt_path = _cfg.RESEARCH_DIR / state["prompt_path"]
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(prompt_path, prompt)
    print(f"Written: {prompt_path}")


def cmd_waves(args: argparse.Namespace) -> None:
    """Show execution waves based on dependency topological sort."""
    from orchestration import compute_waves

    waves = compute_waves(_cfg.RESEARCH_DIR)
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


def cmd_investigate_next(args: argparse.Namespace) -> None:
    """Determine next action for the full investigation."""
    from orchestration import detect_investigation_state, load_config

    config = load_config(DEFAULT_ORCH_CONFIG)
    quick = getattr(args, "quick", False)
    if quick:
        # Quick mode: override to 1 debate round
        config = {**config}
        config["debate_loop"] = {**config.get("debate_loop", {}), "max_rounds": 1}
    state = detect_investigation_state(_cfg.RESEARCH_DIR, config, quick=quick)
    state["breadcrumb"] = _format_investigation_breadcrumb(state, _cfg.RESEARCH_DIR)
    print(json.dumps(state, indent=2))


def cmd_parse_framework(args: argparse.Namespace) -> None:
    """Parse claim registry from blueprint.md (or legacy framework.md)."""
    from orchestration import parse_framework

    framework_path = _cfg.RESEARCH_DIR / "blueprint.md"
    claims = parse_framework(framework_path)
    if not claims:
        print("No claim registry found in blueprint.md.")
        print("Ensure the synthesizer included a ```yaml block with # CLAIM_REGISTRY.", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(claims, indent=2))


def cmd_autonomy_config(args: argparse.Namespace) -> None:
    """Output autonomy configuration as JSON."""
    from orchestration import read_autonomy_config

    result = read_autonomy_config(DEFAULT_ORCH_CONFIG)
    print(json.dumps(result))


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Single-view control panel: phase, active claim, last verdict, blockers, config."""
    from orchestration import detect_investigation_state, load_config, read_autonomy_config

    config = load_config(DEFAULT_ORCH_CONFIG)
    conn = build_db()

    # Investigation state
    inv_state = detect_investigation_state(_cfg.RESEARCH_DIR, config)
    phase = inv_state.get("phase", "unknown")
    action = inv_state.get("action", "unknown")
    breadcrumb = _format_investigation_breadcrumb(inv_state, _cfg.RESEARCH_DIR)

    # Active claim
    active_claim = inv_state.get("sub_unit")
    active_cycle = inv_state.get("cycle")

    # Last verdict
    last_verdict_row = conn.execute(
        "SELECT node_id, event, timestamp FROM ledger "
        "WHERE event IN ('proven', 'disproven', 'partial', 'inconclusive') "
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
            "SELECT COUNT(*) as c FROM nodes WHERE type IN ('claim', 'verdict') "
            "AND file_path LIKE 'claims/%' AND status = ?",
            (status,),
        ).fetchone()["c"]
        if count > 0:
            claim_counts[status] = count

    # Blocked claims (pending with unresolved dependencies)
    blocked = conn.execute(
        "SELECT n.id, dep.id as dep_id FROM nodes n "
        "JOIN edges e ON e.source_id = n.id AND e.relation = 'depends_on' "
        "JOIN nodes dep ON dep.id = e.target_id AND dep.status NOT IN ('proven') "
        "WHERE n.status = 'pending' AND n.file_path LIKE 'claims/%'"
    ).fetchall()
    blocked_claims = [{"id": b["id"], "blocked_by": b["dep_id"]} for b in blocked]

    # Pending human decisions (partial/inconclusive claims needing user input)
    pending_decisions = conn.execute(
        "SELECT id, status, file_path FROM nodes "
        "WHERE status IN ('partial', 'inconclusive') AND file_path LIKE 'claims/%' "
        "ORDER BY file_path"
    ).fetchall()
    decisions = [{"id": d["id"], "status": d["status"], "file": d["file_path"]} for d in pending_decisions]

    # Autonomy config
    autonomy = read_autonomy_config(DEFAULT_ORCH_CONFIG)

    result = {
        "phase": phase,
        "action": action,
        "breadcrumb": breadcrumb,
        "active_claim": active_claim,
        "active_cycle": active_cycle,
        "last_verdict": last_verdict,
        "claims": claim_counts,
        "blocked": blocked_claims,
        "pending_decisions": decisions,
        "autonomy": autonomy,
    }
    print(json.dumps(result, indent=2))


def cmd_reopen(args: argparse.Namespace) -> None:
    """Reopen a completed claim for further investigation."""
    conn = build_db()
    node_id = args.id

    node = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    if not node:
        print(f"ERROR: Node '{node_id}' not found.")
        sys.exit(1)

    if node["status"] in ("pending", "active"):
        print(f"WARN: Node '{node_id}' is already {node['status']} — nothing to reopen.")
        return

    old_status = node["status"]

    # Update frontmatter
    fpath = _cfg.RESEARCH_DIR / node["file_path"]
    if not _update_frontmatter_in_file(fpath, {"status": "active"}):
        print(f"ERROR: Could not update file for '{node_id}' — aborting.")
        sys.exit(1)

    # Update DB
    conn.execute("UPDATE nodes SET status = 'active' WHERE id = ?", (node_id,))

    # Remove post-verdict marker if present
    claim_dir = fpath.parent
    marker = claim_dir / ".post_verdict_done"
    if marker.exists():
        marker.unlink()

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
    target = _cfg.RESEARCH_DIR / sub_path

    if not target.exists():
        print(f"ERROR: Path not found: {target}")
        sys.exit(1)

    verdict_file = target / "arbiter" / "results" / "verdict.md"
    if not verdict_file.exists():
        print(f"ERROR: No verdict file found at {verdict_file}")
        sys.exit(1)

    # Remove verdict file
    verdict_file.unlink()
    print(f"Removed: {verdict_file.relative_to(_cfg.RESEARCH_DIR)}")

    # Remove post-verdict marker
    marker = target / ".post_verdict_done"
    if marker.exists():
        marker.unlink()
        print("Removed: .post_verdict_done marker")

    # Reset claim.md status to active
    claim_file = target / "claim.md"
    if claim_file.exists() and not _update_frontmatter_in_file(claim_file, {"status": "active"}):
        print(f"WARN: Could not update frontmatter in {claim_file}")

    # Ledger entry
    conn = build_db()
    today = date.today().isoformat()
    claim_meta = parse_frontmatter(claim_file.read_text(encoding="utf-8")) if claim_file.exists() else {}
    node_id = claim_meta.get("id", sub_path)
    conn.execute(
        "INSERT INTO ledger (timestamp, event, node_id, details, agent) VALUES (?, ?, ?, ?, ?)",
        (today, "verdict_replaced", str(node_id), f"Verdict removed from {sub_path}", "user"),
    )
    conn.commit()

    print(f"Claim reset to pre-verdict state. Run `/principia:step {sub_path}` to re-dispatch arbiter.")


def cmd_extend_debate(args: argparse.Namespace) -> None:
    """Extend max debate rounds for a specific claim."""
    target = _cfg.RESEARCH_DIR / args.path
    if not target.exists():
        print(f"ERROR: Path not found: {target}")
        sys.exit(1)

    override_file = target / ".max_rounds_override"
    override_file.write_text(str(args.to), encoding="utf-8")
    print(f"Debate extended to {args.to} rounds for {args.path}")


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

    # reopen
    p_reopen = sub.add_parser("reopen", help="Reopen a completed claim for further investigation")
    p_reopen.add_argument("id", help="Node ID to reopen")
    p_reopen.set_defaults(func=cmd_reopen)

    # replace-verdict
    p_rv = sub.add_parser("replace-verdict", help="Delete verdict and reset claim to pre-verdict state")
    p_rv.add_argument("path", help="Claim path")
    p_rv.set_defaults(func=cmd_replace_verdict)

    # status
    p_stat = sub.add_parser("status", help="Auto-generate PROGRESS.md from the DB")
    p_stat.set_defaults(func=cmd_status)

    # dashboard
    p_dash = sub.add_parser("dashboard", help="Control panel: phase, claims, verdicts, blockers")
    p_dash.set_defaults(func=cmd_dashboard)

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

    # scaffold
    p_scaffold = sub.add_parser("scaffold", help="Create directory structure")
    p_scaffold.add_argument("level", choices=["claim"], help="What to scaffold")
    p_scaffold.add_argument("name", help="Slug name (e.g., enrichment, bottleneck)")
    p_scaffold.add_argument("--falsification", default=None, help="Pre-registered falsification criterion")
    p_scaffold.add_argument(
        "--maturity",
        default=None,
        choices=["theorem-backed", "supported", "conjecture", "experiment"],
    )
    p_scaffold.add_argument("--confidence", default=None, choices=["high", "moderate", "low"])
    p_scaffold.add_argument("--statement", default=None, help="Claim statement text")
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

    p_vp = sub.add_parser("validate-paste")  # validate pasted agent result
    p_vp.add_argument(
        "--agent",
        required=True,
        choices=["architect", "adversary", "experimenter", "arbiter", "scout", "synthesizer", "deep-thinker"],
    )
    p_vp.add_argument("--file", required=True, help="Path to file containing pasted result")
    p_vp.set_defaults(func=cmd_validate_paste)

    p_ac = sub.add_parser("autonomy-config")  # output autonomy settings as JSON
    p_ac.set_defaults(func=cmd_autonomy_config)

    p_ed = sub.add_parser("extend-debate")  # conductor extends debate rounds for a claim
    p_ed.add_argument("path", help="Claim path")
    p_ed.add_argument("--to", type=int, required=True, help="New max rounds")
    p_ed.set_defaults(func=cmd_extend_debate)

    args = parser.parse_args()
    init_paths(args.root)
    args.func(args)


if __name__ == "__main__":
    main()
