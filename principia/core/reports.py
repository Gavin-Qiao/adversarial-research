"""Report generators: PROGRESS.md, FOUNDATIONS.md, RESULTS.md, TOOLKIT.md."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, cast

from . import config as _cfg
from .db import build_db
from .frontmatter import get_body, readable_id


def _primary_claim_path_sql(column: str = "file_path") -> str:
    return f"({column} LIKE 'claims/claim-%/claim.md' OR {column} LIKE 'cycles/%/frontier.md')"


def _workspace_root(root: Path | None = None) -> Path:
    if root is None:
        return _cfg.RESEARCH_DIR.resolve()
    return root.resolve()


def _readable_node_label(row: Any, fallback: str | None = None) -> str:
    title = row["title"] if row and row["title"] else None
    if isinstance(title, str) and title.strip():
        return title.strip()
    node_id = row["id"] if row and row["id"] else None
    if isinstance(node_id, str) and node_id:
        return readable_id(node_id)
    return fallback or "Unknown node"


def _format_results_topline(
    *,
    claim_count: int,
    verdict_counts: dict[str, int],
    open_claim_count: int,
    limitations_count: int,
) -> str:
    if claim_count:
        verdict_bits = ", ".join(f"{count} {verdict.lower()}" for verdict, count in sorted(verdict_counts.items()))
        base = f"{claim_count} claim verdict(s) are recorded"
        if verdict_bits:
            base += f": {verdict_bits}"
    else:
        base = "No claim verdicts are recorded yet"

    if open_claim_count:
        base += f"; {open_claim_count} claim(s) are still open"
    if limitations_count:
        base += f"; {limitations_count} limitation(s) still need attention"
    return base + "."


def _collect_results_facts(research_root: Path, conn: Any) -> dict[str, object]:
    from .orchestration import extract_confidence, extract_verdict, load_config

    claim_rows = conn.execute(
        f"SELECT id, title, status, file_path FROM nodes WHERE {_primary_claim_path_sql()} ORDER BY file_path"
    ).fetchall()
    claim_lookup: dict[str, dict[str, str]] = {}
    for row in claim_rows:
        claim_path = Path(str(row["file_path"])).parent.as_posix()
        claim_lookup[claim_path] = {
            "id": str(row["id"]),
            "label": _readable_node_label(row, fallback=Path(claim_path).name),
            "status": str(row["status"]),
            "file_path": str(row["file_path"]),
        }

    orch_config = load_config(_cfg.DEFAULT_ORCH_CONFIG)
    verdict_entries: list[dict[str, object]] = []
    verdict_counts: dict[str, int] = {}
    confidence_counts: dict[str, int] = {}
    for root_dir in (research_root / "claims", research_root / "cycles"):
        if not root_dir.exists():
            continue
        for verdict_file in sorted(root_dir.rglob("verdict.md")):
            claim_dir = verdict_file.parent.parent.parent
            claim_path = claim_dir.relative_to(research_root).as_posix()
            claim_info = claim_lookup.get(claim_path, {})
            verdict_val = extract_verdict(verdict_file, orch_config)
            confidence_val = extract_confidence(verdict_file)
            verdict_counts[verdict_val] = verdict_counts.get(verdict_val, 0) + 1
            confidence_counts[confidence_val] = confidence_counts.get(confidence_val, 0) + 1
            verdict_entries.append(
                {
                    "claim": claim_dir.name,
                    "claim_id": claim_info.get("id", claim_dir.name),
                    "claim_path": claim_path,
                    "label": claim_info.get("label", claim_dir.name),
                    "status": claim_info.get("status"),
                    "verdict": verdict_val,
                    "confidence": confidence_val,
                    "timestamp": verdict_file.stat().st_mtime,
                }
            )

    latest_verdict_row = conn.execute(
        "SELECT l.node_id, l.event, l.timestamp, n.file_path, n.title FROM ledger l "
        "JOIN nodes n ON n.id = l.node_id "
        "WHERE l.event IN ('proven', 'disproven', 'partial', 'inconclusive') "
        "AND (n.file_path LIKE 'claims/claim-%/claim.md' OR n.file_path LIKE 'cycles/%/frontier.md') "
        "ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    latest_verdict = None
    if latest_verdict_row:
        claim_file = Path(str(latest_verdict_row["file_path"]))
        claim_path = claim_file.parent.as_posix()
        verdict_path = research_root / claim_path / "arbiter" / "results" / "verdict.md"
        latest_verdict = {
            "claim": latest_verdict_row["node_id"],
            "claim_path": claim_path,
            "label": _readable_node_label(latest_verdict_row, fallback=claim_file.parent.name),
            "verdict": latest_verdict_row["event"].upper(),
            "timestamp": latest_verdict_row["timestamp"],
            "confidence": extract_confidence(verdict_path) if verdict_path.exists() else "unknown",
        }
    elif verdict_entries:
        fallback = max(verdict_entries, key=lambda entry: float(cast(int | float, entry["timestamp"])))
        latest_verdict = {
            "claim": fallback["claim_id"],
            "claim_path": fallback["claim_path"],
            "label": fallback["label"],
            "verdict": fallback["verdict"],
            "timestamp": None,
            "confidence": fallback["confidence"],
        }

    disproven_rows = conn.execute(
        "SELECT id, title, file_path FROM nodes WHERE status = 'disproven' ORDER BY file_path"
    ).fetchall()
    pending_assumption_rows = conn.execute(
        "SELECT id, title, file_path FROM nodes WHERE type = 'assumption' AND status = 'pending' ORDER BY file_path"
    ).fetchall()
    weakened_rows = conn.execute(
        "SELECT id, title, file_path FROM nodes WHERE status IN ('partial', 'weakened') ORDER BY file_path"
    ).fetchall()

    def _limitation_payload(rows: list[Any], limitation_type: str) -> list[dict[str, str]]:
        return [
            {
                "type": limitation_type,
                "id": str(row["id"]),
                "label": _readable_node_label(row, fallback=str(row["id"])),
                "file_path": str(row["file_path"]),
            }
            for row in rows
        ]

    limitations = {
        "disproven": _limitation_payload(disproven_rows, "disproven claim"),
        "assumptions": _limitation_payload(pending_assumption_rows, "untested assumption"),
        "weakened": _limitation_payload(weakened_rows, "partial or weakened claim"),
    }
    limitation_preview = (limitations["disproven"] + limitations["assumptions"] + limitations["weakened"])[:3]
    open_claim_count = conn.execute(
        f"SELECT COUNT(*) AS c FROM nodes WHERE {_primary_claim_path_sql()} "
        "AND status IN ('pending', 'active', 'partial', 'weakened', 'inconclusive')"
    ).fetchone()["c"]
    limitations_count = sum(len(entries) for entries in limitations.values())

    return {
        "verdict_entries": verdict_entries,
        "limitations": limitations,
        "summary": {
            "claim_count": len(verdict_entries),
            "verdict_counts": verdict_counts,
            "latest_verdict": latest_verdict,
            "limitations_count": limitations_count,
            "topline": _format_results_topline(
                claim_count=len(verdict_entries),
                verdict_counts=verdict_counts,
                open_claim_count=int(open_claim_count),
                limitations_count=limitations_count,
            ),
            "open_claim_count": int(open_claim_count),
            "confidence_counts": confidence_counts,
            "limitation_preview": limitation_preview,
        },
    }


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
        JOIN edges e ON e.target_id = n.id AND e.relation IN ('depends_on', 'assumes')
        JOIN nodes dep ON dep.id = e.source_id AND dep.status = 'pending'
            AND (dep.file_path LIKE 'claims/claim-%/claim.md' OR dep.file_path LIKE 'cycles/%/frontier.md')
        WHERE n.status = 'active'
          AND (
              n.type = 'assumption'
              OR n.file_path LIKE 'claims/claim-%/claim.md'
              OR n.file_path LIKE 'cycles/%/frontier.md'
          )
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
        active = conn.execute(
            f"SELECT * FROM nodes WHERE status = 'active' AND {_primary_claim_path_sql()} ORDER BY date"
        ).fetchall()
        if active:
            for a in active:
                title = a["title"] or readable_id(a["id"])
                lines.append(f"- **{title}** (`{a['id']}`)")
                lines.append(f"  File: {a['file_path']}")
        else:
            lines.append("No active blockers.")
    lines.append("")

    # --- Proven ---
    lines.append("## What is proven")
    lines.append("")
    proven = conn.execute("SELECT * FROM nodes WHERE status = 'proven' ORDER BY file_path").fetchall()
    if proven:
        lines.append("| Claim | Source |")
        lines.append("|-------|--------|")
        for s in proven:
            title = s["title"] or readable_id(s["id"])
            lines.append(f"| {title} | `{s['id']}` |")
        lines.append("")
    else:
        lines.append("Nothing proven yet.")
        lines.append("")

    # --- Disproven ---
    lines.append("## What is disproven")
    lines.append("")
    falsified = conn.execute(
        "SELECT n.*, e.target_id as evidence_id "
        "FROM nodes n "
        "LEFT JOIN edges e ON e.source_id = n.id AND e.relation = 'falsified_by' "
        "WHERE n.status = 'disproven' "
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
        lines.append("Nothing disproven.")
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

    lines.append("## Claim log")
    lines.append("")
    claim_nodes = conn.execute(f"SELECT * FROM nodes WHERE {_primary_claim_path_sql()} ORDER BY file_path").fetchall()
    if claim_nodes:
        lines.append("| Claim | Status | File |")
        lines.append("|-------|--------|------|")
        for n in claim_nodes:
            title = n["title"] or readable_id(n["id"])
            lines.append(f"| {title} | {n['status']} | `{n['file_path']}` |")
        lines.append("")
    else:
        lines.append("No claims registered.")
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
    _cfg._atomic_write(_cfg.PROGRESS_PATH, content)
    print(f"Generated: {_cfg.PROGRESS_PATH}")


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

            # If disproven
            if a["status"] == "disproven":
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
                    "WHERE n.status IN ('partial', 'weakened')",
                    (a["id"],),
                ).fetchall()
                if cascaded:
                    lines.append(f"- **Cascade**: {', '.join('`' + c['id'] + '`' for c in cascaded)} weakened")
            lines.append("")

    content = "\n".join(lines) + "\n"
    _cfg._atomic_write(_cfg.FOUNDATIONS_PATH, content)
    print(f"Generated: {_cfg.FOUNDATIONS_PATH}")


# ---------------------------------------------------------------------------
# Command: codebook -> TOOLKIT.md
# ---------------------------------------------------------------------------


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
    codebook_path = _cfg.RESEARCH_DIR / "TOOLKIT.md"
    _cfg._atomic_write(codebook_path, content)
    print(f"Generated: {codebook_path}")


# ---------------------------------------------------------------------------
# Helper: investigation breadcrumb
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Command: results -> RESULTS.md
# ---------------------------------------------------------------------------


def generate_results_report(root: Path | None = None) -> tuple[Path, str]:
    """Generate RESULTS.md for a workspace and return its path and status message."""
    research_root = _workspace_root(root)
    conn = build_db(root=research_root)
    try:
        facts = _collect_results_facts(research_root, conn)
        summary = cast(dict[str, object], facts["summary"])
        verdict_entries = cast(list[dict[str, object]], facts["verdict_entries"])
        limitations = cast(dict[str, list[dict[str, str]]], facts["limitations"])

        lines: list[str] = ["# Design Results", ""]
        for name in ("blueprint.md",):
            bp = research_root / name
            if bp.exists():
                body = get_body(bp.read_text(encoding="utf-8"))
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

        lines.append("## Executive Summary")
        lines.append("")
        lines.append(f"- {cast(str, summary['topline'])}")
        latest_verdict = cast(dict[str, object] | None, summary["latest_verdict"])
        if latest_verdict:
            lines.append(
                f"- Latest verdict: **{latest_verdict['verdict']}** on **{latest_verdict['label']}** "
                f"at **{latest_verdict['confidence']}** confidence."
            )
        else:
            lines.append("- Latest verdict: none recorded yet.")
        lines.append(f"- Open claims: {cast(int, summary['open_claim_count'])}")
        limitation_preview = cast(list[dict[str, str]], summary["limitation_preview"])
        if limitation_preview:
            lines.append("- Current limitations:")
            for limitation in limitation_preview:
                lines.append(f"  - {limitation['label']} (`{limitation['id']}`) - {limitation['type']}")
        else:
            lines.append("- Current limitations: none identified.")
        lines.append("")

        lines.append("## Claims")
        lines.append("")
        if verdict_entries:
            for verdict_entry in verdict_entries:
                lines.append(f"### {verdict_entry['label']}")
                lines.append(f"- **Claim ID**: `{verdict_entry['claim_id']}`")
                lines.append(f"- **Claim path**: `{verdict_entry['claim_path']}`")
                lines.append(f"- **Verdict**: {verdict_entry['verdict']}")
                lines.append(f"- **Confidence**: {verdict_entry['confidence']}")
                lines.append("")
        else:
            lines.append("No claim verdicts are recorded yet.")
            lines.append("")

        synthesis = research_root / "synthesis.md"
        if synthesis.exists():
            lines.append("## Synthesis")
            lines.append("")
            body = get_body(synthesis.read_text(encoding="utf-8"))
            lines.append(body.strip())
            lines.append("")

        composition = research_root / "composition.md"
        if composition.exists():
            lines.append("## Composed Algorithm")
            lines.append("")
            body = get_body(composition.read_text(encoding="utf-8"))
            lines.append(body.strip())
            lines.append("")

        lines.append("## Limitations")
        lines.append("")
        if limitations["disproven"]:
            lines.append("### Disproven claims")
            lines.append("")
            for entry in limitations["disproven"]:
                lines.append(f"- {entry['label']} (`{entry['id']}`)")
            lines.append("")
        if limitations["assumptions"]:
            lines.append("### Untested assumptions")
            lines.append("")
            for entry in limitations["assumptions"]:
                lines.append(f"- {entry['label']} (`{entry['id']}`)")
            lines.append("")
        if limitations["weakened"]:
            lines.append("### Partially supported or weakened claims")
            lines.append("")
            for entry in limitations["weakened"]:
                lines.append(f"- {entry['label']} (`{entry['id']}`)")
            lines.append("")
        if not limitations["disproven"] and not limitations["assumptions"] and not limitations["weakened"]:
            lines.append("None identified.")
            lines.append("")

        content = "\n".join(lines) + "\n"
        results_path = research_root / "RESULTS.md"
        _cfg._atomic_write(results_path, content)
        return results_path, f"Generated: {results_path}"
    finally:
        conn.close()

    """Legacy implementation removed.
    # Scan verdict files directly — DB frontmatter status is unreliable
    # (verdict nodes typically have status: active, not the actual verdict)
    found_verdicts = False
    for root_dir in (research_root / "claims", research_root / "cycles"):
        if not root_dir.exists():
            continue
        for verdict_file in sorted(root_dir.rglob("verdict.md")):
            found_verdicts = True
            claim_dir = verdict_file.parent.parent.parent  # arbiter/results/verdict.md → claim dir
            claim_name = claim_dir.name
            verdict_val = extract_verdict(verdict_file, orch_config)
            confidence_val = extract_confidence(verdict_file)
            lines.append(f"### {claim_name}")
            lines.append(f"- **Verdict**: {verdict_val}")
            lines.append(f"- **Confidence**: {confidence_val}")
            lines.append("")

    if not found_verdicts:
        lines.append("No claims investigated yet.")
        lines.append("")

    # --- Synthesis ---
    synthesis = research_root / "synthesis.md"
    if synthesis.exists():
        lines.append("## Synthesis")
        lines.append("")
        body = get_body(synthesis.read_text(encoding="utf-8"))
        lines.append(body.strip())
        lines.append("")

    # --- Composition ---
    composition = research_root / "composition.md"
    if composition.exists():
        lines.append("## Composed Algorithm")
        lines.append("")
        body = get_body(composition.read_text(encoding="utf-8"))
        lines.append(body.strip())
        lines.append("")

    # --- Limitations ---
    lines.append("## Limitations")
    lines.append("")

    disproven = conn.execute("SELECT id FROM nodes WHERE status = 'disproven' ORDER BY id").fetchall()
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

    weakened = conn.execute("SELECT id FROM nodes WHERE status IN ('partial', 'weakened') ORDER BY id").fetchall()
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
    results_path = research_root / "RESULTS.md"
    _cfg._atomic_write(results_path, content)
    conn.close()
    return results_path, f"Generated: {results_path}"
    """


def build_results_summary(root: Path | None = None) -> dict[str, object]:
    """Summarize verdict and limitation signals that back RESULTS.md."""
    research_root = _workspace_root(root)
    conn = build_db(root=research_root)
    try:
        facts = _collect_results_facts(research_root, conn)
        return dict(cast(dict[str, object], facts["summary"]))
    finally:
        conn.close()

    """Legacy implementation removed.

    from .orchestration import extract_confidence, extract_verdict, load_config

    orch_config = load_config(_cfg.DEFAULT_ORCH_CONFIG)
    verdict_entries: list[dict[str, object]] = []
    verdict_counts: dict[str, int] = {}
    for root_dir in (research_root / "claims", research_root / "cycles"):
        if not root_dir.exists():
            continue
        for verdict_file in sorted(root_dir.rglob("verdict.md")):
            claim_dir = verdict_file.parent.parent.parent
            verdict_val = extract_verdict(verdict_file, orch_config)
            confidence_val = extract_confidence(verdict_file)
            verdict_counts[verdict_val] = verdict_counts.get(verdict_val, 0) + 1
            verdict_entries.append(
                {
                    "claim_path": claim_dir.relative_to(research_root).as_posix(),
                    "claim": claim_dir.name,
                    "verdict": verdict_val,
                    "confidence": confidence_val,
                    "timestamp": verdict_file.stat().st_mtime,
                }
            )

    latest_verdict_row = conn.execute(
        "SELECT l.node_id, l.event, l.timestamp, n.file_path FROM ledger l "
        "JOIN nodes n ON n.id = l.node_id "
        "WHERE l.event IN ('proven', 'disproven', 'partial', 'inconclusive') "
        "AND (n.file_path LIKE 'claims/claim-%/claim.md' OR n.file_path LIKE 'cycles/%/frontier.md') "
        "ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    latest_verdict = None
    if latest_verdict_row:
        claim_file = Path(str(latest_verdict_row["file_path"]))
        claim_path = claim_file.parent.as_posix()
        verdict_path = research_root / claim_path / "arbiter" / "results" / "verdict.md"
        latest_verdict = {
            "claim": latest_verdict_row["node_id"],
            "claim_path": claim_path,
            "verdict": latest_verdict_row["event"].upper(),
            "timestamp": latest_verdict_row["timestamp"],
            "confidence": extract_confidence(verdict_path) if verdict_path.exists() else "unknown",
        }
    elif verdict_entries:
        fallback = max(verdict_entries, key=lambda entry: float(entry["timestamp"]))
        latest_verdict = {
            "claim": fallback["claim"],
            "claim_path": fallback["claim_path"],
            "verdict": fallback["verdict"],
            "timestamp": None,
            "confidence": fallback["confidence"],
        }

    disproven = conn.execute("SELECT COUNT(*) AS c FROM nodes WHERE status = 'disproven'").fetchone()["c"]
    pending_assumptions = conn.execute(
        "SELECT COUNT(*) AS c FROM nodes WHERE type = 'assumption' AND status = 'pending'"
    ).fetchone()["c"]
    weakened = conn.execute("SELECT COUNT(*) AS c FROM nodes WHERE status IN ('partial', 'weakened')").fetchone()["c"]
    conn.close()

    return {
        "claim_count": len(verdict_entries),
        "verdict_counts": verdict_counts,
        "latest_verdict": latest_verdict,
        "limitations_count": disproven + pending_assumptions + weakened,
    }
    """


def cmd_results(args: argparse.Namespace) -> None:
    """Generate a single RESULTS.md summarising the entire design investigation."""
    _, message = generate_results_report()
    print(message)
