"""
ID derivation constants and functions for Principia.

Extracted from manage.py so that other modules (orchestration, tests) can
import them without pulling in the full manage.py dependency tree.
"""

from __future__ import annotations

import os
import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = {
    "pending",
    "active",
    "proven",
    "disproven",
    "partial",
    "weakened",
    "inconclusive",
}
VALID_TYPES = {"claim", "assumption", "evidence", "reference", "verdict", "question"}
VALID_ATTACK_TYPES = {"undermines", "rebuts", "undercuts", None}
VALID_MATURITIES = {"theorem-backed", "supported", "conjecture", "experiment", None}
VALID_CONFIDENCES = {"high", "moderate", "low", None}

ROLE_TYPE_MAP = {
    "architect": "claim",
    "adversary": "claim",
    "experimenter": "evidence",
    "scout": "reference",
    "arbiter": "verdict",
    "synthesizer": "claim",
}

# ---------------------------------------------------------------------------
# ID derivation from relative path
# ---------------------------------------------------------------------------


def derive_id(rel_path: str) -> str:
    """Derive a short ID from a path relative to research/."""
    p = rel_path
    if p.endswith(".md"):
        p = p[:-3]
    # Strip leading directory prefixes
    p = re.sub(r"^claims/", "", p)
    p = re.sub(r"^context/", "", p)
    # Apply abbreviations
    parts = p.split("/")
    result = []
    for part in parts:
        t = part
        # claim-N or claim-N-name -> hN (hypothesis)
        t = re.sub(r"^claim-(\d+)(?:-[a-z0-9_-]+)?$", r"h\1", t)
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
    if "assumptions" in parts:
        return "assumption"
    _prompt_roles = {"architect", "adversary", "synthesizer", "scout"}
    for role in ROLE_TYPE_MAP:
        if role in parts:
            basename = os.path.basename(rel_path)
            if basename == "prompt.md" and role in _prompt_roles:
                return "question"
            return ROLE_TYPE_MAP[role]
    basename = os.path.basename(rel_path)
    if basename == "claim.md":
        return "claim"
    return "reference"
