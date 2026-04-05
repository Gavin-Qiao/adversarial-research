"""Markdown frontmatter parser and serialiser (no PyYAML dependency).

This module handles the ``---``-delimited YAML subset used for design
node metadata.  It is intentionally dependency-free so it can be imported
by both ``manage.py`` and ``orchestration.py`` without pulling in the
other's transitive dependencies.
"""

from __future__ import annotations

import re
import sys

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

SCALAR_FRONTMATTER_KEYS = (
    "id",
    "type",
    "status",
    "date",
    "attack_type",
    "falsified_by",
    "counterfactual",
    "maturity",
    "confidence",
    "weakened_from_status",
    "weakened_from_confidence",
    "wave",
    "cycle_status",
)


def _parse_yaml_value(raw: str) -> str | list[str] | None:
    """Parse a single YAML value: string, list of strings, null, or date."""
    raw = raw.strip()
    if raw in ("null", "~", ""):
        return None
    # Inline list:  [a, b, c]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        items = [s.strip().strip("'\"") for s in inner.split(",")]
        return [i for i in items if i]
    # Quoted string
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    return raw


def parse_frontmatter(text: str, *, filepath: str | None = None) -> dict:
    """Return metadata dict from a markdown file's frontmatter.

    NOTE: This is a simplified parser. Block scalars (| and >) and nested
    keys are not supported. All values must be single-line.

    If *filepath* is provided, warnings include the file path for context.
    """
    m = _FM_RE.match(text)
    if not m:
        return {}
    block = m.group(1)
    meta: dict[str, str | list[str] | None] = {}
    for i, raw_line in enumerate(block.splitlines()):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            # Detect YAML block-list items the flat parser cannot handle
            if re.match(r"^\s+-\s+", raw_line):
                loc = f" in {filepath}" if filepath else ""
                print(
                    f"  WARN: Skipped YAML list item{loc} (line {i + 1}): '{stripped}'. "
                    f"Use inline format: key: [item1, item2]",
                    file=sys.stderr,
                )
            continue
        key, _, val = stripped.partition(":")
        meta[key.strip()] = _parse_yaml_value(val)
    return meta


def get_scalar_frontmatter(meta: dict, key: str, *, filepath: str | None = None, warn: bool = False) -> str | None:
    """Return a scalar string frontmatter value, or None when missing/invalid."""
    value = meta.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if warn:
        loc = f" in {filepath}" if filepath else ""
        print(
            f"  WARN: Non-scalar frontmatter '{key}'{loc} ignored. Use a single-line scalar value.",
            file=sys.stderr,
        )
    return None


def get_body(text: str) -> str:
    """Return everything after the frontmatter."""
    m = _FM_RE.match(text)
    if not m:
        return text
    return text[m.end() :]


def extract_title(body: str) -> str | None:
    """Return the first # heading from the body, or None."""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def readable_id(node_id: str) -> str:
    """Convert a node ID to a human-readable label when no title exists."""
    return node_id.replace("-", " ").replace("_", " ").title()


# ---------------------------------------------------------------------------
# Serialiser
# ---------------------------------------------------------------------------

_YAML_SPECIAL = {"true", "false", "yes", "no", "on", "off", "null", "~", ""}


def _yaml_val(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, list):
        if not v:
            return "[]"
        parts = []
        for i in v:
            s = str(i)
            if s.lower() in _YAML_SPECIAL or s != i:
                parts.append(f'"{s}"')
            else:
                parts.append(s)
        return "[" + ", ".join(parts) + "]"
    s = str(v)
    # Quote values that YAML would misinterpret as booleans, nulls, or numbers,
    # or that contain colons (ambiguous to external YAML parsers)
    if s.lower() in _YAML_SPECIAL or s != v or ":" in s:
        return f'"{s}"'
    try:
        float(s)
        return f'"{s}"'
    except ValueError:
        pass
    return s


def serialise_frontmatter(meta: dict) -> str:
    """Produce a ---/--- delimited YAML frontmatter block."""
    lines = ["---"]
    # Canonical key order
    order = [
        "id",
        "type",
        "status",
        "date",
        "maturity",
        "confidence",
        "weakened_from_status",
        "weakened_from_confidence",
        "depends_on",
        "assumes",
        "attack_type",
        "falsified_by",
        "counterfactual",
        "wave",
        "cycle_status",
    ]
    seen: set[str] = set()
    for k in order:
        if k in meta:
            lines.append(f"{k}: {_yaml_val(meta[k])}")
            seen.add(k)
    for k, v in meta.items():
        if k not in seen:
            lines.append(f"{k}: {_yaml_val(v)}")
    lines.append("---")
    return "\n".join(lines)
