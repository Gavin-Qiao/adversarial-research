"""Artifact schema validation and database integrity checks."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

from . import config as _cfg
from .commands import emit_envelope
from .db import build_db
from .ids import VALID_ATTACK_TYPES, VALID_STATUSES, VALID_TYPES

# ---------------------------------------------------------------------------
# Artifact validation schemas
# ---------------------------------------------------------------------------

_VALID_VERDICTS = {"PROVEN", "DISPROVEN", "PARTIAL", "INCONCLUSIVE"}
_VALID_SEVERITIES = {"fatal", "serious", "minor", "none"}
_VALID_CONFIDENCES_PASTE = {"high", "moderate", "low"}


class ValidationResult(TypedDict, total=False):
    valid: bool
    error_count: int
    errors: list[str]
    node_count: int
    edge_count: int


def _find_field(text: str, field_name: str) -> str | None:
    """Extract a structured field value from '**Field**: value' or 'Field: value' lines."""
    for line in text.splitlines():
        stripped = line.strip()
        # Match both **Field**: value and Field: value
        lower = stripped.lower().replace("*", "")
        if lower.startswith(field_name.lower()) and ":" in stripped:
            val = stripped.split(":", 1)[1].strip().strip("*").strip()
            return val
    return None


def validate_artifact(agent: str, content: str) -> list[str]:
    """Validate artifact content for a given agent role. Returns list of errors (empty = valid)."""
    errors: list[str] = []

    if not content or len(content.strip()) < 50:
        errors.append("Result appears empty or truncated (minimum 50 characters).")
        return errors

    if agent == "adversary":
        severity_val = _find_field(content, "Severity")
        if not severity_val:
            errors.append("Missing required field: **Severity**: <Fatal|Serious|Minor|None>")
        elif severity_val.split()[0].lower().rstrip("(,.:") not in _VALID_SEVERITIES:
            errors.append(
                f"Invalid severity value '{severity_val}'. "
                f"Must start with one of: {', '.join(sorted(_VALID_SEVERITIES))}"
            )

    elif agent == "arbiter":
        verdict_val = _find_field(content, "Verdict")
        if not verdict_val:
            errors.append("Missing required field: **Verdict**: <PROVEN|DISPROVEN|PARTIAL|INCONCLUSIVE>")
        elif verdict_val.split()[0].strip("*").upper() not in _VALID_VERDICTS:
            errors.append(
                f"Invalid verdict value '{verdict_val}'. Must be one of: {', '.join(sorted(_VALID_VERDICTS))}"
            )
        confidence_val = _find_field(content, "Confidence")
        if not confidence_val:
            errors.append("Missing required field: **Confidence**: <high|moderate|low>")
        elif confidence_val.split()[0].strip("*").lower() not in _VALID_CONFIDENCES_PASTE:
            errors.append(
                f"Invalid confidence value '{confidence_val}'. "
                f"Must be one of: {', '.join(sorted(_VALID_CONFIDENCES_PASTE))}"
            )

    elif agent == "experimenter":
        # Must have a results section with substantive content
        has_results = any(
            line.strip().lower().startswith(("## result", "# result", "**result")) for line in content.splitlines()
        )
        if not has_results:
            errors.append("Missing results section. Experimenter output must contain a '## Results' heading.")

    elif agent == "scout":
        has_findings = any(
            line.strip().lower().startswith(("## key finding", "# key finding", "**key finding"))
            for line in content.splitlines()
        )
        has_sources = any(
            line.strip().lower().startswith(("## source", "# source", "**source")) for line in content.splitlines()
        )
        if not has_findings:
            errors.append("Missing section: '## Key Findings'")
        if not has_sources:
            errors.append("Missing section: '## Sources'")

    elif agent == "deep-thinker":
        has_analysis = any(
            line.strip().lower().startswith(("## analysis", "# analysis", "**analysis"))
            for line in content.splitlines()
        )
        if not has_analysis:
            errors.append("Missing section: '## Analysis'")

    # architect and synthesizer have no strict structural requirements
    return errors


def cmd_validate_paste(args: argparse.Namespace) -> None:
    """Validate a pasted external agent result against its artifact schema."""
    agent = args.agent
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        sys.exit(1)

    try:
        content = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        print(f"ERROR: File is not valid UTF-8: {file_path}")
        sys.exit(1)
    errors = validate_artifact(agent, content)

    if errors:
        print(f"ERROR: Invalid {agent} result:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print(f"OK: Valid {agent} result ({len(content.strip())} characters).")


def collect_validation_result(root: Path | None = None) -> ValidationResult:
    """Run integrity checks on a workspace and return the structured result."""
    workspace_root = _cfg.RESEARCH_DIR.resolve() if root is None else root.resolve()
    conn = build_db(root=workspace_root)  # Always rebuild for freshness
    errors = []

    # Check for duplicate IDs by scanning source files (the DB won't have dupes
    # because build skips them, but we need to detect the conflicting source files)
    from .db import discover_md_files
    from .frontmatter import SCALAR_FRONTMATTER_KEYS, get_scalar_frontmatter
    from .frontmatter import parse_frontmatter as _parse_fm
    from .ids import derive_id as _derive_id

    id_to_file: dict[str, str] = {}
    for fpath in discover_md_files(workspace_root):
        rel = str(fpath.relative_to(workspace_root))
        try:
            text = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            errors.append(f"Invalid UTF-8: {rel}")
            continue
        meta = _parse_fm(text, filepath=rel)
        for key in SCALAR_FRONTMATTER_KEYS:
            if key in meta and meta.get(key) is not None and get_scalar_frontmatter(meta, key, filepath=rel) is None:
                errors.append(f"Invalid frontmatter: '{rel}' has non-scalar {key}")
        node_id = get_scalar_frontmatter(meta, "id", filepath=rel)
        node_id = node_id or _derive_id(rel)
        if node_id in id_to_file:
            errors.append(f"Duplicate ID: '{node_id}' in both {id_to_file[node_id]} and {rel}")
        else:
            id_to_file[node_id] = rel

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

    result: ValidationResult = {
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
    }
    if not errors:
        result["node_count"] = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
        result["edge_count"] = conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
    conn.close()
    return result


def cmd_validate(args: argparse.Namespace) -> None:
    """Run integrity checks on the database."""
    result = collect_validation_result()
    errors = result["errors"]

    if getattr(args, "json", False):
        emit_envelope(result)
        if errors:
            sys.exit(1)
        return

    if errors:
        print(f"VALIDATION FAILED: {len(errors)} error(s)\n")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        node_count = result["node_count"]
        edge_count = result["edge_count"]
        print(f"Validation passed: {node_count} nodes, {edge_count} edges, 0 errors.")
