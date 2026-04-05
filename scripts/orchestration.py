"""Orchestration engine for principia design workflows.

Provides config-driven state machine, context assembly, severity/verdict
extraction, and external prompt generation. All logic is deterministic
and testable — the fuzzy LLM layer lives in the /step skill, not here.
"""

from __future__ import annotations

import contextlib
import re
import sqlite3
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# YAML-subset parser (stdlib only, no PyYAML)
# ---------------------------------------------------------------------------

# We need to parse orchestration.yaml without PyYAML.
# The config uses a simple subset: scalars, lists, and nested dicts.


def _parse_yaml_lines(lines: list[str], start: int = 0, base_indent: int = 0) -> tuple[dict[str, Any], int]:
    """Parse a YAML-subset into a dict. Returns (parsed_dict, lines_consumed)."""
    result: dict[str, Any] = {}
    i = start
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # Calculate indent
        indent = len(line) - len(line.lstrip())
        if indent < base_indent:
            break  # Dedented — return to parent

        if indent > base_indent and not stripped.startswith("- "):
            # Nested block under previous key — skip, handled by recursion
            i += 1
            continue

        # List item at current indent
        if stripped.startswith("- "):
            i += 1
            continue  # Lists handled when we encounter the key

        # Key-value pair
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()

            if val:
                # Inline value
                result[key] = _parse_yaml_value(val)
                i += 1
            else:
                # Check if next non-empty line is a list or nested dict
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    next_line = lines[j]
                    next_indent = len(next_line) - len(next_line.lstrip())
                    next_stripped = next_line.strip()
                    if next_indent > indent and next_stripped.startswith("- "):
                        # It's a list
                        result[key] = _parse_yaml_list(lines, j, next_indent)
                        # Skip past the list
                        i = j
                        while i < len(lines):
                            li = lines[i].strip()
                            li_indent = len(lines[i]) - len(lines[i].lstrip())
                            if not li or li.startswith("#"):
                                i += 1
                                continue
                            if li_indent < next_indent:
                                break
                            i += 1
                    elif next_indent > indent:
                        # Nested dict
                        nested, consumed = _parse_yaml_lines(lines, j, next_indent)
                        result[key] = nested
                        i = j + consumed
                    else:
                        result[key] = None
                        i += 1
                else:
                    result[key] = None
                    i += 1
        else:
            i += 1

    return result, i - start


def _parse_yaml_list(lines: list[str], start: int, base_indent: int) -> list[Any]:
    """Parse a YAML list starting at the given position."""
    items: list[Any] = []
    i = start
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent < base_indent:
            break
        if stripped.startswith("- "):
            content = stripped[2:].strip()
            if ":" in content and not content.startswith('"') and not content.startswith("["):
                # Dict item in list — parse the first key-value, then collect nested keys
                item_dict: dict[str, Any] = {}
                k, _, v = content.partition(":")
                item_dict[k.strip()] = _parse_yaml_value(v.strip()) if v.strip() else None
                # Check for nested keys under this list item
                j = i + 1
                while j < len(lines):
                    nline = lines[j]
                    nstripped = nline.strip()
                    if not nstripped or nstripped.startswith("#"):
                        j += 1
                        continue
                    nindent = len(nline) - len(nline.lstrip())
                    if nindent <= indent:
                        break
                    if ":" in nstripped:
                        nk, _, nv = nstripped.partition(":")
                        nk = nk.strip()
                        nv = nv.strip()
                        if nv:
                            item_dict[nk] = _parse_yaml_value(nv)
                        else:
                            # Nested structure under this key
                            jj = j + 1
                            while jj < len(lines) and not lines[jj].strip():
                                jj += 1
                            if jj < len(lines):
                                nn_indent = len(lines[jj]) - len(lines[jj].lstrip())
                                nn_stripped = lines[jj].strip()
                                if nn_indent > nindent and nn_stripped.startswith("- "):
                                    item_dict[nk] = _parse_yaml_list(lines, jj, nn_indent)
                                    j = jj
                                    while j < len(lines):
                                        li = lines[j].strip()
                                        li_indent = len(lines[j]) - len(lines[j].lstrip())
                                        if not li or li.startswith("#"):
                                            j += 1
                                            continue
                                        if li_indent < nn_indent:
                                            break
                                        j += 1
                                    continue
                                elif nn_indent > nindent:
                                    nested, _ = _parse_yaml_lines(lines, jj, nn_indent)
                                    item_dict[nk] = nested
                                    j = jj
                                    while j < len(lines):
                                        li = lines[j].strip()
                                        li_indent = len(lines[j]) - len(lines[j].lstrip())
                                        if not li or li.startswith("#"):
                                            j += 1
                                            continue
                                        if li_indent < nn_indent:
                                            break
                                        j += 1
                                    continue
                    j += 1
                items.append(item_dict)
                i = j
            else:
                items.append(_parse_yaml_value(content))
                i += 1
        else:
            i += 1
    return items


def _parse_yaml_value(raw: str) -> Any:
    """Parse a single YAML value."""
    raw = raw.strip()
    # Strip inline comments (but not inside quoted strings)
    if not raw.startswith('"') and not raw.startswith("'") and not raw.startswith("["):
        comment_idx = raw.find("  #")
        if comment_idx >= 0:
            raw = raw[:comment_idx].strip()
        elif raw.startswith("#"):
            return None
    if raw in ("null", "~", ""):
        return None
    if raw in ("true", "True"):
        return True
    if raw in ("false", "False"):
        return False
    # Inline list: [a, b, c]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [s.strip().strip("'\"") for s in inner.split(",") if s.strip()]
    # Quoted string
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    # Try int
    try:
        return int(raw)
    except ValueError:
        pass
    return raw


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file using our subset parser."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    result, _ = _parse_yaml_lines(lines, 0, 0)
    return result


# ---------------------------------------------------------------------------
# Default config (used when orchestration.yaml is missing)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
    "debate_loop": {
        "sequence": ["architect", "adversary"],
        "max_rounds": 3,
        "final_say": "adversary",
    },
    "roles": [
        {
            "name": "adversary",
            "exit_condition": {
                "field": "Severity",
                "continue_on": ["fatal", "serious"],
                "exit_on": ["minor", "none"],
                "unknown": "continue",
            },
        },
    ],
    "post_verdict": {
        "PROVEN": {"action": "complete", "message": "Claim proven."},
        "DISPROVEN": {"action": "complete", "cascade": True, "message": "Hypothesis disproven."},
        "PARTIAL": {
            "action": "prompt_user",
            "message": "Verdict partial — claim holds under some conditions.",
            "options": ["Narrow the claim", "More evidence", "Accept partial result"],
        },
        "INCONCLUSIVE": {
            "action": "prompt_user",
            "message": "Verdict inconclusive — insufficient evidence either way.",
            "options": ["Try a different approach", "More evidence", "Defer"],
        },
    },
    "severity_keywords": {
        "fatal": ["fatal", "blocks the approach", "fundamentally flawed"],
        "serious": ["serious", "requires modification"],
        "minor": ["minor", "worth noting"],
        "none": ["no genuine flaws", "no fatal"],
    },
    "auto_review": True,
}


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load orchestration config. Falls back to defaults if missing."""
    if config_path and config_path.exists():
        return load_yaml(config_path)
    return DEFAULT_CONFIG.copy()


def read_autonomy_config(config_path: Path | None = None) -> dict[str, Any]:
    """Read autonomy settings from orchestration config."""
    config = load_config(config_path)
    autonomy = config.get("autonomy", {})
    if not isinstance(autonomy, dict):
        autonomy = {}
    return {
        "mode": autonomy.get("mode", "checkpoints"),
        "checkpoint_at": autonomy.get("checkpoint_at", ["understand", "divide", "test", "synthesize"]),
    }


def _get_roles_config(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a lookup dict from roles list."""
    roles = config.get("roles", [])
    return {r["name"]: r for r in roles if isinstance(r, dict) and "name" in r}


# ---------------------------------------------------------------------------
# State detection helpers
# ---------------------------------------------------------------------------


def find_completed_rounds(role_dir: Path) -> list[int]:
    """Find completed rounds (have result.md) in a role directory.
    Returns sorted list of round numbers."""
    if not role_dir.exists():
        return []
    rounds = []
    for d in role_dir.iterdir():
        if d.is_dir() and d.name.startswith("round-"):
            result_file = d / "result.md"
            if result_file.exists():
                match = re.match(r"round-(\d+)", d.name)
                if match:
                    rounds.append(int(match.group(1)))
    return sorted(rounds)


def _any_result_exists(role_dir: Path) -> bool:
    """Check if any result file exists in a role directory."""
    if not role_dir.exists():
        return False
    results_dir = role_dir / "results"
    if results_dir.exists():
        return any(f.suffix == ".md" for f in results_dir.iterdir())
    # Also check for round-based results
    return bool(find_completed_rounds(role_dir))


def check_waiting(role_dir: Path, round_num: int) -> str | None:
    """Check if an external agent prompt exists without a result.
    Returns a description of what's being waited for, or None."""
    round_dir = role_dir / f"round-{round_num}"
    if round_dir.exists():
        prompt = round_dir / "prompt.md"
        result = round_dir / "result.md"
        if prompt.exists() and not result.exists():
            return f"{role_dir.name} round {round_num}"
    return None


def _check_post_verdict_complete(target: Path) -> bool:
    """Check if post-verdict bookkeeping is done.

    Uses a marker file (.post_verdict_done) written by cmd_post_verdict.
    Falls back to mtime comparison for backward compatibility with
    claims processed before the marker file was introduced.
    """
    marker = target / ".post_verdict_done"
    if marker.exists():
        return True
    # Fallback: mtime comparison (legacy)
    arbiter_dir = target / "arbiter"
    verdict = arbiter_dir / "results" / "verdict.md"
    if not verdict.exists():
        return False
    claim = target / "claim.md"
    if not claim.exists():
        claim = target / "frontier.md"
    return claim.exists() and claim.stat().st_mtime >= verdict.stat().st_mtime


# ---------------------------------------------------------------------------
# Parsing agent output
# ---------------------------------------------------------------------------


def extract_severity(result_path: Path, config: dict[str, Any]) -> str:
    """Extract severity from adversary result using config keywords.
    Returns: fatal/serious/minor/none/unknown"""
    if not result_path.exists():
        return "unknown"
    text = result_path.read_text(encoding="utf-8")
    text_lower = text.lower()

    # Check structured field first
    for line in text.splitlines():
        stripped = line.strip().lower()
        if ("severity" in stripped or "**severity**" in stripped) and ":" in stripped:
            val = stripped.split(":", 1)[1].strip().strip("*").strip()
            for level in ("fatal", "serious", "minor", "none"):
                if level in val:
                    return level

    # Fallback: scan for keyword phrases from config.
    # Check longer phrases first so "no fatal" matches before "fatal".
    keywords = config.get("severity_keywords", {})
    matches: list[tuple[str, str]] = []
    for level, phrases in keywords.items():
        if not isinstance(phrases, list):
            continue
        for phrase in phrases:
            if phrase.lower() in text_lower:
                matches.append((str(level), phrase.lower()))
    if matches:
        matches.sort(key=lambda m: len(m[1]), reverse=True)
        return matches[0][0]

    return "unknown"


def extract_verdict(verdict_path: Path, config: dict[str, Any]) -> str:
    """Extract verdict from arbiter result.
    Returns: PROVEN/DISPROVEN/PARTIAL/INCONCLUSIVE/UNKNOWN"""
    if not verdict_path.exists():
        return "UNKNOWN"
    try:
        text = verdict_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError):
        return "UNKNOWN"

    for line in text.splitlines():
        stripped = line.strip()
        if ("Verdict" in stripped or "**Verdict**" in stripped) and ":" in stripped:
            upper = stripped.upper()
            if "PROVEN" in upper and "DISPROVEN" not in upper:
                return "PROVEN"
            if "DISPROVEN" in upper:
                return "DISPROVEN"
            if "INCONCLUSIVE" in upper:
                return "INCONCLUSIVE"
            if "PARTIAL" in upper:
                return "PARTIAL"

    return "UNKNOWN"


def extract_confidence(verdict_path: Path) -> str:
    """Extract confidence from arbiter/conductor verdict.
    Returns: high/moderate/low/unknown"""
    if not verdict_path.exists():
        return "unknown"
    try:
        text = verdict_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError):
        return "unknown"

    for line in text.splitlines():
        stripped = line.strip().lower()
        if ("confidence" in stripped or "**confidence**" in stripped) and ":" in stripped:
            val = stripped.split(":", 1)[1].strip().strip("*").strip()
            for level in ("high", "moderate", "low"):
                if level in val:
                    return level

    return "unknown"


# Confidence attenuation: when cascading undermined, downgrade one level
_CONFIDENCE_DOWNGRADE = {"high": "moderate", "moderate": "low", "low": "low", "unknown": "low"}


def attenuate_confidence(current: str | None) -> str:
    """Downgrade confidence by one level for undermined nodes."""
    return _CONFIDENCE_DOWNGRADE.get(current or "unknown", "low")


# ---------------------------------------------------------------------------
# Post-verdict suggestions
# ---------------------------------------------------------------------------


def suggest_next(verdict: str, sub_path: str, config: dict[str, Any]) -> dict[str, Any]:
    """Return post-verdict message and suggestions from config."""
    post = config.get("post_verdict", {})
    entry = post.get(verdict, {})
    return {
        "verdict": verdict,
        "sub_unit": sub_path,
        "action": entry.get("action", "unknown"),
        "cascade": entry.get("cascade", False),
        "message": entry.get("message", f"Verdict: {verdict}"),
        "options": entry.get("options", []),
    }


# ---------------------------------------------------------------------------
# Execution waves (topological sort of claim dependencies)
# ---------------------------------------------------------------------------


def compute_waves(research_dir: Path, db_path: Path | None = None) -> list[list[dict[str, Any]]]:
    """Compute execution waves from claim dependencies using topological sort.

    Returns a list of waves, where each wave is a list of node dicts.
    Nodes within a wave are independent and can run in parallel.
    Waves must be executed sequentially (wave N+1 depends on wave N).

    Within each wave, nodes are sorted by maturity priority:
    theorem-backed > supported > conjecture > experiment
    """
    if db_path is None:
        db_path = research_dir / ".db" / "research.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Get all nodes with their dependencies
    nodes = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM nodes").fetchall()}
    edges = conn.execute(
        "SELECT source_id, target_id FROM edges WHERE relation IN ('depends_on', 'assumes')"
    ).fetchall()
    conn.close()

    # Build adjacency: node -> list of nodes it depends on
    deps: dict[str, set[str]] = {nid: set() for nid in nodes}
    for e in edges:
        if e["source_id"] in deps and e["target_id"] in nodes:
            deps[e["source_id"]].add(e["target_id"])

    # Kahn's algorithm for topological sort into waves
    in_degree: dict[str, int] = {nid: len(d) for nid, d in deps.items()}
    waves: list[list[dict[str, Any]]] = []
    remaining = set(nodes.keys())

    while remaining:
        # Find all nodes with in-degree 0 (no unresolved dependencies)
        wave_ids = [nid for nid in remaining if in_degree.get(nid, 0) == 0]
        if not wave_ids:
            break  # Cycle detected — remaining nodes can't be scheduled

        # Sort by maturity priority within wave
        maturity_order = {"theorem-backed": 0, "supported": 1, "conjecture": 2, "experiment": 3}
        wave_ids.sort(key=lambda nid: maturity_order.get(nodes[nid].get("maturity") or "", 99))

        wave = [nodes[nid] for nid in wave_ids]
        waves.append(wave)

        # Remove these nodes and update in-degrees
        for nid in wave_ids:
            remaining.discard(nid)
            for other in remaining:
                if nid in deps.get(other, set()):
                    in_degree[other] -= 1

    return waves


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def _make_state(
    action: str,
    *,
    agent: str | None = None,
    round_num: int | None = None,
    phase: str = "unknown",
    waiting_for: str | None = None,
    severity: str | None = None,
    suggestion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a state dict."""
    state: dict[str, Any] = {
        "action": action,
        "phase": phase,
    }
    if agent is not None:
        state["agent"] = agent
    elif action.startswith("dispatch_"):
        state["agent"] = action.replace("dispatch_", "")
    if round_num is not None:
        state["round"] = round_num
    if waiting_for is not None:
        state["waiting_for"] = waiting_for
    if severity is not None:
        state["severity"] = severity
    if suggestion is not None:
        state["suggestion"] = suggestion
    return state


def detect_state(research_dir: Path, sub_path: str, config: dict[str, Any]) -> dict[str, Any]:
    """Scan claim directory and return structured state."""
    target = research_dir / sub_path
    if not target.exists():
        return _make_state("error", phase="error")

    debate_config = config.get("debate_loop", DEFAULT_CONFIG["debate_loop"])
    roles_config = _get_roles_config(config)
    max_rounds = debate_config.get("max_rounds", 3)

    # Conductor can override max_rounds per claim via extend-debate
    override_file = target / ".max_rounds_override"
    if override_file.exists():
        with contextlib.suppress(ValueError, OSError):
            max_rounds = int(override_file.read_text().strip())

    # Scan existing files
    architect_dir = target / "architect"
    adversary_dir = target / "adversary"
    experimenter_dir = target / "experimenter"
    verdict_dir = target / "arbiter"
    architect_rounds = find_completed_rounds(architect_dir)
    adversary_rounds = find_completed_rounds(adversary_dir)
    has_experimenter = _any_result_exists(experimenter_dir)
    has_verdict = (verdict_dir / "results" / "verdict.md").exists()
    post_verdict_done = _check_post_verdict_complete(target)

    a_count = len(architect_rounds)
    adv_count = len(adversary_rounds)

    # --- State machine ---

    # Skip debate entirely if max_rounds == 0
    if max_rounds == 0 and not has_experimenter:
        return _make_state("dispatch_experimenter", phase="experiment")

    # No architect yet → start debate
    if a_count == 0:
        waiting = check_waiting(architect_dir, 1)
        if waiting:
            return _make_state("waiting", waiting_for=waiting, phase="debate")
        return _make_state("dispatch_architect", round_num=1, phase="debate")

    # Architect ahead of adversary → adversary's turn
    if a_count > adv_count:
        waiting = check_waiting(adversary_dir, a_count)
        if waiting:
            return _make_state("waiting", waiting_for=waiting, phase="debate")
        return _make_state("dispatch_adversary", round_num=a_count, phase="debate")

    # Adversary has responded, no experimenter yet → decide: continue debate or proceed
    if adv_count >= a_count and not has_experimenter:
        # Check for waiting external
        waiting = check_waiting(architect_dir, adv_count + 1)
        if waiting:
            return _make_state("waiting", waiting_for=waiting, phase="debate")

        # Final round reached → proceed to experimenter
        if adv_count >= max_rounds:
            return _make_state("dispatch_experimenter", phase="experiment")

        # Check severity from adversary's latest result
        adversary_result = adversary_dir / f"round-{adv_count}" / "result.md"
        severity = extract_severity(adversary_result, config)

        adversary_config = roles_config.get("adversary", {})
        exit_cond = adversary_config.get("exit_condition", {})
        exit_on = exit_cond.get("exit_on", ["minor", "none"])
        continue_on = exit_cond.get("continue_on", ["fatal", "serious"])
        unknown_default = exit_cond.get("unknown", "continue")

        if severity in exit_on:
            return _make_state("dispatch_experimenter", phase="experiment")
        if severity in continue_on:
            return _make_state("dispatch_architect", round_num=adv_count + 1, phase="debate")
        # Unknown severity
        if unknown_default == "continue":
            return _make_state(
                "dispatch_architect",
                round_num=adv_count + 1,
                phase="debate",
                severity="unknown",
            )
        return _make_state("dispatch_experimenter", phase="experiment", severity="unknown")

    # Experimenter done, no verdict → dispatch arbiter
    if has_experimenter and not has_verdict:
        waiting = check_waiting(verdict_dir, 1)
        if waiting:
            return _make_state("waiting", waiting_for=waiting, phase="verdict")
        return _make_state("dispatch_arbiter", phase="verdict")

    # Verdict rendered, post-verdict not done → auto-review or manual review
    if has_verdict and not post_verdict_done:
        if config.get("auto_review", True):
            return _make_state("post_verdict", phase="recording")
        return _make_state("dispatch_reviewer", phase="recording")

    # Post-verdict done → complete
    if post_verdict_done:
        verdict = extract_verdict(verdict_dir / "results" / "verdict.md", config)
        suggestion = suggest_next(verdict, sub_path, config)
        return _make_state(
            f"complete_{verdict.lower()}",
            phase="complete",
            suggestion=suggestion,
        )

    return _make_state("unknown")


# ---------------------------------------------------------------------------
# Find active claim (or legacy sub-unit)
# ---------------------------------------------------------------------------


def find_active_subunit(research_dir: Path, db_path: Path | None = None) -> str | None:
    """Find the first claim that needs work.
    Uses the SQLite DB if available, otherwise scans directories."""
    from frontmatter import get_scalar_frontmatter, parse_frontmatter

    def _primary_claim_status(target: Path) -> str | None:
        claim_file = target / "claim.md"
        if not claim_file.exists():
            claim_file = target / "frontier.md"
        if not claim_file.exists():
            return None
        try:
            meta = parse_frontmatter(claim_file.read_text(encoding="utf-8"), filepath=str(claim_file))
        except (OSError, UnicodeDecodeError, ValueError):
            return None
        return get_scalar_frontmatter(meta, "status")

    if db_path is None:
        db_path = research_dir / ".db" / "research.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT file_path FROM nodes "
                "WHERE status IN ('pending', 'active') "
                "AND (file_path LIKE 'claims/claim-%/claim.md' OR file_path LIKE 'cycles/%/frontier.md') "
                "ORDER BY file_path LIMIT 1"
            ).fetchone()
            conn.close()
            if row:
                return str(Path(row["file_path"]).parent)
        except sqlite3.Error:
            pass

    # Fallback: scan claims/ directory for flat claims
    claims_dir = research_dir / "claims"
    if claims_dir.exists():
        for claim_dir in sorted(claims_dir.iterdir()):
            if (
                claim_dir.is_dir()
                and claim_dir.name.startswith("claim-")
                and _primary_claim_status(claim_dir) in ("pending", "active")
            ):
                return str(claim_dir.relative_to(research_dir))

    # Legacy cycles/ hierarchy
    cycles_dir = research_dir / "cycles"
    if cycles_dir.exists():
        for cycle_dir in sorted(cycles_dir.iterdir()):
            if not cycle_dir.is_dir():
                continue
            for unit_dir in sorted(cycle_dir.iterdir()):
                if not unit_dir.is_dir() or not unit_dir.name.startswith("unit-"):
                    continue
                for sub_dir in sorted(unit_dir.iterdir()):
                    if (
                        not sub_dir.is_dir()
                        or not sub_dir.name.startswith("sub-")
                        or _primary_claim_status(sub_dir) not in ("pending", "active")
                    ):
                        continue
                    return str(sub_dir.relative_to(research_dir))

    return None


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------


def list_context_files(
    research_dir: Path,
    sub_path: str,
    action: str,
    round_num: int | None = None,
    agent: str = "",
    max_rounds: int = 3,
) -> list[str]:
    """List all context files the next agent needs, in reading order.

    When *agent* is provided, apply role-specific filtering to enforce
    knowledge divergence between debate participants.
    """
    target = research_dir / sub_path
    files: list[str] = []

    # Claim file (the research question)
    claim_file = target / "claim.md"
    if not claim_file.exists():
        claim_file = target / "frontier.md"
    if claim_file.exists():
        files.append(str(claim_file.relative_to(research_dir)))

    # Scout results if they exist
    scout_dir = target / "scout"
    if scout_dir.exists():
        for f in sorted(scout_dir.rglob("*.md")):
            files.append(str(f.relative_to(research_dir)))

    # All completed architect/adversary rounds in order
    for r in range(1, max_rounds + 1):
        for role in ("architect", "adversary"):
            result = target / role / f"round-{r}" / "result.md"
            if result.exists():
                files.append(str(result.relative_to(research_dir)))

    # Experimenter output
    exp_output = target / "experimenter" / "results" / "output.md"
    if exp_output.exists():
        files.append(str(exp_output.relative_to(research_dir)))

    # Arbiter verdict (only for post-verdict context)
    if action in ("dispatch_reviewer", "post_verdict"):
        verdict = target / "arbiter" / "results" / "verdict.md"
        if verdict.exists():
            files.append(str(verdict.relative_to(research_dir)))

    # Agent-aware filtering for knowledge divergence
    if agent == "adversary":
        files = [f for f in files if not ("/architect/" in f and f.endswith("prompt.md"))]

    return files


def assemble_context(research_dir: Path, context_files: list[str]) -> str:
    """Read and concatenate context files into a single document."""
    from frontmatter import extract_title, get_body

    sections: list[str] = []
    for fpath in context_files:
        full = research_dir / fpath
        if not full.exists():
            continue
        text = full.read_text(encoding="utf-8")
        body = get_body(text)
        title = extract_title(body) or fpath
        sections.append(f"## {title}\n**Source**: `{fpath}`\n\n{body}")

    return "\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# External prompt generation
# ---------------------------------------------------------------------------


def generate_external_prompt(state: dict[str, Any], context: str, agent_instructions: str) -> str:
    """Build a self-contained prompt for external agent dispatch."""
    agent = state.get("agent", "unknown")
    round_num = state.get("round", "")
    round_str = f" — Round {round_num}" if round_num else ""

    return f"""# External Prompt: {agent}{round_str}

## Agent Instructions

{agent_instructions}

---

## Research Context

{context}

---

## Your Task

Based on the context above, produce your output following the format specified in the agent instructions.
"""


# ---------------------------------------------------------------------------
# Dispatch config
# ---------------------------------------------------------------------------


def read_dispatch_config(research_dir: Path) -> dict[str, str]:
    """Parse .config.md and return {{agent: 'internal'|'external'}}."""
    config_file = research_dir / ".config.md"
    defaults = {
        "scout": "internal",
        "architect": "internal",
        "adversary": "internal",
        "experimenter": "internal",
        "arbiter": "internal",
        "synthesizer": "internal",
        "deep-thinker": "internal",
    }
    if not config_file.exists():
        return defaults

    text = config_file.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- ") and ":" in line:
            content = line[2:].strip()
            key, _, val = content.partition(":")
            key = key.strip().lower()
            val = val.strip().lower().split("(")[0].strip()  # strip "(always)" etc.
            if key in defaults and val in ("internal", "external"):
                defaults[key] = val

    return defaults


# ---------------------------------------------------------------------------
# Compute paths for new files
# ---------------------------------------------------------------------------


def compute_paths(sub_path: str, agent: str, round_num: int | None) -> dict[str, str]:
    """Compute prompt_path and result_path for the next agent."""
    if agent in ("architect", "adversary") and round_num:
        base = f"{sub_path}/{agent}/round-{round_num}"
        return {"prompt_path": f"{base}/prompt.md", "result_path": f"{base}/result.md"}
    if agent == "experimenter":
        return {
            "prompt_path": f"{sub_path}/{agent}/prompt.md",
            "result_path": f"{sub_path}/{agent}/results/output.md",
        }
    if agent == "arbiter":
        return {
            "prompt_path": f"{sub_path}/{agent}/prompt.md",
            "result_path": f"{sub_path}/{agent}/results/verdict.md",
        }
    return {"prompt_path": f"{sub_path}/{agent}/prompt.md", "result_path": f"{sub_path}/{agent}/result.md"}


# ---------------------------------------------------------------------------
# Blueprint parsing (synthesizer claim registry)
# ---------------------------------------------------------------------------

_REGISTRY_MARKER = "# CLAIM_REGISTRY"


def parse_framework(framework_path: Path) -> list[dict[str, Any]]:
    """Extract claim registry from synthesizer blueprint output.

    Looks for a fenced ```yaml block containing '# CLAIM_REGISTRY'.
    Returns list of claim dicts with keys: id, statement, maturity,
    confidence, depends_on, falsification.  Empty list if not found.
    """
    if not framework_path.exists():
        return []

    text = framework_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Find the fenced yaml block containing the registry marker
    yaml_block: list[str] = []
    in_block = False
    found_marker = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```yaml") and not in_block:
            in_block = True
            yaml_block = []
            continue
        if stripped == "```" and in_block:
            if found_marker:
                break  # End of the registry block
            in_block = False
            yaml_block = []
            found_marker = False
            continue
        if in_block:
            if _REGISTRY_MARKER in line:
                found_marker = True
                continue  # Skip the marker line itself
            if found_marker:
                yaml_block.append(line)

    if not yaml_block:
        return []

    # Parse the YAML content using our subset parser
    try:
        parsed, _ = _parse_yaml_lines(yaml_block, 0, 0)
    except (ValueError, IndexError, KeyError, TypeError, AttributeError):
        return []

    claims_raw = parsed.get("claims", [])
    if not isinstance(claims_raw, list):
        return []

    # Normalize each claim
    claims: list[dict[str, Any]] = []
    for item in claims_raw:
        if not isinstance(item, dict) or "id" not in item:
            continue
        claim: dict[str, Any] = {
            "id": str(item["id"]),
            "statement": str(item.get("statement", "")),
            "maturity": str(item.get("maturity", "conjecture")),
            "confidence": str(item.get("confidence", "moderate")),
            "depends_on": item.get("depends_on", []) or [],
            "falsification": str(item.get("falsification", "")),
        }
        # Ensure depends_on is a list
        if isinstance(claim["depends_on"], str):
            claim["depends_on"] = [s.strip() for s in claim["depends_on"].split(",") if s.strip()]
        claims.append(claim)

    return claims


# ---------------------------------------------------------------------------
# Investigation-level state machine
# ---------------------------------------------------------------------------


def _classify_cycle_states(
    cycle_states: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Classify cycle states into needs_review, incomplete, and done."""
    needs_review: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    done: list[dict[str, Any]] = []
    for cs in cycle_states:
        action = cs["state"].get("action", "")
        if action.startswith("complete_"):
            done.append(cs)
        elif action in ("dispatch_reviewer", "post_verdict"):
            needs_review.append(cs)
        else:
            incomplete.append(cs)
    return needs_review, incomplete, done


def detect_investigation_state(
    research_dir: Path,
    config: dict[str, Any],
    db_path: Path | None = None,
    quick: bool = False,
) -> dict[str, Any]:
    """Detect the current state of a full investigation.

    Scans the research directory structure to determine what phase
    the investigation is in. Returns a JSON-serializable dict with
    an ``action`` key and relevant context.

    v0.3 four-phase model:
    - understand    -- discuss (.north-star.md), inspect (.context.md), research (survey-*.md)
    - divide        -- north star + context + surveys exist, no blueprint.md
    - scaffold      -- blueprint exists, claims not scaffolded
    - test_claim    -- scaffolded claims need testing
    - record_verdict-- claim needs post-verdict bookkeeping
    - synthesize    -- all claims tested, no synthesis.md
    - complete      -- synthesis.md exists

    If *quick* is True, skip research in understand and synthesizer in divide.
    """
    context_dir = research_dir / "context"
    framework_path = research_dir / "blueprint.md"
    synthesis_path = research_dir / "synthesis.md"
    north_star_path = research_dir / ".north-star.md"
    context_path = research_dir / ".context.md"

    # --- Phase 1: Understand ---
    # Check which understand sub-steps are complete
    surveys = sorted(context_dir.glob("survey-*.md")) if context_dir.exists() else []
    if not surveys:
        surveys = sorted(context_dir.glob("distillation-*.md")) if context_dir.exists() else []

    substeps: list[str] = []
    if not north_star_path.exists():
        substeps.append("discuss")
    if not context_path.exists():
        substeps.append("inspect")
    if not surveys and not quick:
        substeps.append("research")

    if substeps:
        return {"action": "understand", "phase": "understand", "substeps": substeps}

    # --- Quick mode: skip blueprint, scaffold single claim ---
    if quick:
        claims_dir = research_dir / "claims"
        if not claims_dir.exists() or not any(claims_dir.iterdir()):
            return {"action": "scaffold_quick", "phase": "divide"}
        claim_dirs = sorted(d for d in claims_dir.iterdir() if d.is_dir())
        if claim_dirs:
            sub_path = str(claim_dirs[0].relative_to(research_dir))
            state = detect_state(research_dir, sub_path, config)
            if state.get("action", "").startswith("complete_"):
                if not synthesis_path.exists():
                    return {
                        "action": "synthesize",
                        "phase": "synthesize",
                        "completed_cycles": [claim_dirs[0].name],
                        "proven_claims": ([claim_dirs[0].name] if state.get("action") == "complete_proven" else []),
                    }
                return {"action": "complete", "phase": "complete"}
            return {
                "action": "test_claim",
                "phase": "test",
                "cycle": claim_dirs[0].name,
                "sub_unit": sub_path,
                "cycle_state": state,
            }

    # --- Phase 2: Divide ---
    if not framework_path.exists():
        context_files: list[str] = []
        if north_star_path.exists():
            context_files.append(str(north_star_path.relative_to(research_dir)))
        if context_path.exists():
            context_files.append(str(context_path.relative_to(research_dir)))
        context_files.extend(str(d.relative_to(research_dir)) for d in surveys)
        return {
            "action": "divide",
            "phase": "divide",
            "context_files": context_files,
        }

    # --- Phase 3: Scaffold ---
    claims = parse_framework(framework_path)
    claims_dir = research_dir / "claims"
    cycles_dir = research_dir / "cycles"
    has_cycles = cycles_dir.exists() and any(cycles_dir.iterdir())
    has_claims = claims_dir.exists() and any(claims_dir.iterdir())
    if not has_cycles and not has_claims:
        return {
            "action": "scaffold",
            "phase": "divide",
            "claims": claims,
        }

    # Check for unscaffolded claims
    existing_dirs: set[str] = set()
    if cycles_dir.exists():
        existing_dirs |= {d.name for d in cycles_dir.iterdir() if d.is_dir()}
    if claims_dir.exists():
        existing_dirs |= {d.name for d in claims_dir.iterdir() if d.is_dir()}

    def _id_matches_dir(cid: str, dirname: str) -> bool:
        """Check if claim ID matches a directory name (not just substring)."""
        # Directory format: claim-N-slug or cycle-N-slug
        # Match if ID appears as a complete segment delimited by hyphens or at boundaries
        return cid == dirname or f"-{cid}-" in f"-{dirname}-"

    unscaffolded = [c for c in claims if not any(_id_matches_dir(c["id"], name) for name in existing_dirs)]
    if unscaffolded:
        return {
            "action": "scaffold",
            "phase": "divide",
            "claims": unscaffolded,
        }

    # --- Phase 4: Test ---
    cycle_states: list[dict[str, Any]] = []

    if claims_dir.exists():
        for claim_dir in sorted(claims_dir.iterdir()):
            if not claim_dir.is_dir() or not claim_dir.name.startswith("claim-"):
                continue
            sub_path = str(claim_dir.relative_to(research_dir))
            state = detect_state(research_dir, sub_path, config)
            cycle_states.append(
                {
                    "cycle": claim_dir.name,
                    "sub_unit": sub_path,
                    "state": state,
                }
            )

    # Legacy cycles/ hierarchy
    if cycles_dir.exists():
        for cycle_dir in sorted(cycles_dir.iterdir()):
            if not cycle_dir.is_dir():
                continue
            for unit_dir in sorted(cycle_dir.iterdir()):
                if not unit_dir.is_dir() or not unit_dir.name.startswith("unit-"):
                    continue
                for sub_dir in sorted(unit_dir.iterdir()):
                    if not sub_dir.is_dir() or not sub_dir.name.startswith("sub-"):
                        continue
                    sub_path = str(sub_dir.relative_to(research_dir))
                    state = detect_state(research_dir, sub_path, config)
                    cycle_states.append(
                        {
                            "cycle": cycle_dir.name,
                            "sub_unit": sub_path,
                            "state": state,
                        }
                    )

    if not cycle_states:
        return {
            "action": "scaffold",
            "phase": "divide",
            "claims": claims,
        }

    # Wave-based execution
    waves = compute_waves(research_dir, db_path) if db_path else []
    by_cycle: dict[str, list[dict[str, Any]]] = {}
    for cs in cycle_states:
        by_cycle.setdefault(cs["cycle"], []).append(cs)

    claim_to_cycle: dict[str, str] = {}
    if cycles_dir.exists():
        for cycle_dir_item in cycles_dir.iterdir():
            if cycle_dir_item.is_dir():
                for claim in claims:
                    if _id_matches_dir(claim["id"], cycle_dir_item.name):
                        claim_to_cycle[claim["id"]] = cycle_dir_item.name

    if claims_dir.exists():
        for claim_dir_item in claims_dir.iterdir():
            if claim_dir_item.is_dir():
                for claim in claims:
                    if _id_matches_dir(claim["id"], claim_dir_item.name):
                        claim_to_cycle[claim["id"]] = claim_dir_item.name

    if waves and len(waves) > 1:
        for wave in waves:
            wave_claim_ids = [node["id"] for node in wave]
            wave_cycle_names = [claim_to_cycle[cid] for cid in wave_claim_ids if cid in claim_to_cycle]

            wave_cs = [cs for cycle_name in wave_cycle_names for cs in by_cycle.get(cycle_name, [])]
            w_needs_review, w_incomplete, _w_done = _classify_cycle_states(wave_cs)

            if w_needs_review:
                nr = w_needs_review[0]
                return {
                    "action": "record_verdict",
                    "phase": "test",
                    "cycle": nr["cycle"],
                    "sub_unit": nr["sub_unit"],
                }
            if w_incomplete:
                ic = w_incomplete[0]
                return {
                    "action": "test_claim",
                    "phase": "test",
                    "cycle": ic["cycle"],
                    "sub_unit": ic["sub_unit"],
                    "cycle_state": ic["state"],
                }
    else:
        needs_review, incomplete, _ = _classify_cycle_states(cycle_states)

        if needs_review:
            nr = needs_review[0]
            return {
                "action": "record_verdict",
                "phase": "test",
                "cycle": nr["cycle"],
                "sub_unit": nr["sub_unit"],
            }
        if incomplete:
            ic = incomplete[0]
            return {
                "action": "test_claim",
                "phase": "test",
                "cycle": ic["cycle"],
                "sub_unit": ic["sub_unit"],
                "cycle_state": ic["state"],
            }

    # --- Phase 5: Synthesize (merges old compose + synthesize) ---
    done = [cs for cs in cycle_states if cs["state"].get("action", "").startswith("complete_")]
    proven = [cs for cs in done if cs["state"].get("action") == "complete_proven"]

    if not synthesis_path.exists():
        return {
            "action": "synthesize",
            "phase": "synthesize",
            "completed_cycles": [cs["cycle"] for cs in done],
            "proven_claims": [cs["cycle"] for cs in proven],
        }

    return {"action": "complete", "phase": "complete"}
