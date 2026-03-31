"""Contract tests: validate that workflow.md documentation matches actual code behavior.

These tests parse the state table and verdict table from workflow.md and run each
documented transition against detect_state(). If someone changes the code without
updating the docs (or vice versa), these tests fail with a clear message.
"""
# ruff: noqa: N802 — test names use contract IDs (T1, V1) which are uppercase by design

from __future__ import annotations

from pathlib import Path

import pytest
from manage import init_paths
from orchestration import DEFAULT_CONFIG, detect_state, suggest_next

WORKFLOW_MD = Path(__file__).resolve().parent.parent / "skills" / "methodology" / "references" / "workflow.md"


# ---------------------------------------------------------------------------
# Parse the contract tables from workflow.md
# ---------------------------------------------------------------------------


def _extract_table(text: str, start_marker: str, end_marker: str) -> list[dict[str, str]]:
    """Extract a markdown table between markers and return list of row dicts."""
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start == -1 or end == -1:
        raise ValueError(f"Contract markers not found: {start_marker} / {end_marker}")

    block = text[start + len(start_marker) : end].strip()
    lines = [line.strip() for line in block.splitlines() if line.strip()]

    # First line is header, second is separator, rest are data
    if len(lines) < 3:
        raise ValueError("Table has fewer than 3 lines between markers")

    headers = [h.strip() for h in lines[0].split("|") if h.strip()]
    rows = []
    for line in lines[2:]:  # skip header and separator
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def _load_state_contracts() -> list[dict[str, str]]:
    text = WORKFLOW_MD.read_text(encoding="utf-8")
    return _extract_table(text, "<!-- CONTRACT:STATE_TABLE_START -->", "<!-- CONTRACT:STATE_TABLE_END -->")


def _load_verdict_contracts() -> list[dict[str, str]]:
    text = WORKFLOW_MD.read_text(encoding="utf-8")
    return _extract_table(text, "<!-- CONTRACT:VERDICT_TABLE_START -->", "<!-- CONTRACT:VERDICT_TABLE_END -->")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SUB_REL = "cycles/cycle-1/unit-1-test/sub-1a-direct"


@pytest.fixture
def sub_unit(tmp_path):
    """Create a sub-unit directory with role dirs and frontier files."""
    research_dir = tmp_path
    for d in ["cycles", "context/assumptions", ".db"]:
        (research_dir / d).mkdir(parents=True)
    init_paths(research_dir)

    sub = research_dir / SUB_REL
    for role in ("thinker", "refutor", "coder", "judge", "researcher"):
        (sub / role).mkdir(parents=True)

    # Unit frontier
    unit_frontier = sub.parent / "frontier.md"
    unit_frontier.parent.mkdir(parents=True, exist_ok=True)
    unit_frontier.write_text("---\nid: test\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test Unit\n")

    # Sub-unit frontier
    sub_frontier = sub / "frontier.md"
    sub_frontier.write_text("---\nid: test-sub\ntype: verdict\nstatus: pending\ndate: 2026-01-01\n---\n\n# Test Sub\n")

    return research_dir


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_result(
    research_dir: Path,
    rel_path: str,
    severity: str | None = None,
    verdict: str | None = None,
    content_override: str | None = None,
) -> None:
    """Write a result file with optional severity/verdict."""
    full = research_dir / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    body = content_override or "# Result\n\nContent."
    if severity:
        body += f"\n\n**Severity**: {severity}\n"
    if verdict:
        body += f"\n\n**Verdict**: {verdict}\n"
    full.write_text(f"---\nid: test\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n{body}")


# ---------------------------------------------------------------------------
# Build scenarios from contract IDs
# ---------------------------------------------------------------------------


def _setup_scenario(research_dir: Path, contract_id: str) -> None:
    """Set up the filesystem state for a given contract ID."""
    sub = SUB_REL

    if contract_id == "T1":
        pass  # Empty sub-unit

    elif contract_id == "T2":
        _write_result(research_dir, f"{sub}/thinker/round-1/result.md")

    elif contract_id == "T3":
        _write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        _write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Fatal (blocks the approach)")

    elif contract_id == "T4":
        _write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        _write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Serious (requires modification)")

    elif contract_id == "T5":
        _write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        _write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Minor (worth noting)")

    elif contract_id == "T6":
        _write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        _write_result(research_dir, f"{sub}/refutor/round-1/result.md", content_override="No genuine flaws found.")

    elif contract_id == "T7":
        _write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        _write_result(research_dir, f"{sub}/refutor/round-1/result.md")  # no severity field

    elif contract_id == "T8":
        for r in range(1, 4):
            _write_result(research_dir, f"{sub}/thinker/round-{r}/result.md")
            _write_result(research_dir, f"{sub}/refutor/round-{r}/result.md", severity="Fatal")

    elif contract_id == "T9":
        _write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        _write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Minor")
        _write_result(research_dir, f"{sub}/coder/results/output.md")

    elif contract_id == "T10":
        _write_result(research_dir, f"{sub}/thinker/round-1/result.md")
        _write_result(research_dir, f"{sub}/refutor/round-1/result.md", severity="Minor")
        _write_result(research_dir, f"{sub}/coder/results/output.md")
        _write_result(research_dir, f"{sub}/judge/results/verdict.md", verdict="SETTLED")

    elif contract_id == "T11":
        # Prompt exists but no result — waiting for external
        prompt = research_dir / sub / "thinker" / "round-1" / "prompt.md"
        prompt.parent.mkdir(parents=True, exist_ok=True)
        prompt.write_text("# External prompt\n")

    else:
        raise ValueError(f"Unknown contract ID: {contract_id}")


def _parse_action(action_str: str) -> tuple[str, int | None]:
    """Parse 'dispatch_thinker round 2' into ('dispatch_thinker', 2)."""
    parts = action_str.strip().split()
    action = parts[0]
    round_num = None
    if "round" in parts:
        idx = parts.index("round")
        if idx + 1 < len(parts):
            round_num = int(parts[idx + 1])
    return action, round_num


# ---------------------------------------------------------------------------
# Contract tests: state table
# ---------------------------------------------------------------------------


class TestStateTableContract:
    """Each test validates one row from the state table in workflow.md.

    If a test fails, it means EITHER:
    - The code changed and workflow.md needs updating, OR
    - workflow.md changed and the code needs updating
    """

    @pytest.fixture(autouse=True)
    def _load_contracts(self):
        self.contracts = {row["ID"]: row for row in _load_state_contracts()}

    def _assert_contract(self, sub_unit, contract_id: str):
        """Run detect_state and check it matches the documented contract."""
        contract = self.contracts[contract_id]
        _setup_scenario(sub_unit, contract_id)
        state = detect_state(sub_unit, SUB_REL, DEFAULT_CONFIG)

        expected_action, expected_round = _parse_action(contract["Action"])
        expected_phase = contract["Phase"]

        assert state["action"] == expected_action, (
            f"Contract {contract_id} BROKEN: "
            f"docs say action='{expected_action}' but code returns '{state['action']}'. "
            f"Update workflow.md or orchestration.py."
        )
        assert state["phase"] == expected_phase, (
            f"Contract {contract_id} BROKEN: "
            f"docs say phase='{expected_phase}' but code returns '{state['phase']}'. "
            f"Update workflow.md or orchestration.py."
        )
        if expected_round is not None:
            assert state.get("round") == expected_round, (
                f"Contract {contract_id} BROKEN: "
                f"docs say round={expected_round} but code returns round={state.get('round')}. "
                f"Update workflow.md or orchestration.py."
            )

    def test_T1_empty_subunit(self, sub_unit):
        self._assert_contract(sub_unit, "T1")

    def test_T2_thinker_done(self, sub_unit):
        self._assert_contract(sub_unit, "T2")

    def test_T3_refutor_fatal(self, sub_unit):
        self._assert_contract(sub_unit, "T3")

    def test_T4_refutor_serious(self, sub_unit):
        self._assert_contract(sub_unit, "T4")

    def test_T5_refutor_minor(self, sub_unit):
        self._assert_contract(sub_unit, "T5")

    def test_T6_refutor_none(self, sub_unit):
        self._assert_contract(sub_unit, "T6")

    def test_T7_refutor_unknown(self, sub_unit):
        self._assert_contract(sub_unit, "T7")

    def test_T8_round_max(self, sub_unit):
        self._assert_contract(sub_unit, "T8")

    def test_T9_coder_done(self, sub_unit):
        self._assert_contract(sub_unit, "T9")

    def test_T10_verdict_exists(self, sub_unit):
        self._assert_contract(sub_unit, "T10")

    def test_T11_waiting(self, sub_unit):
        self._assert_contract(sub_unit, "T11")


# ---------------------------------------------------------------------------
# Contract tests: verdict table
# ---------------------------------------------------------------------------


class TestVerdictTableContract:
    """Validates the verdict branching table from workflow.md."""

    @pytest.fixture(autouse=True)
    def _load_contracts(self):
        self.contracts = {row["ID"]: row for row in _load_verdict_contracts()}

    def test_V1_settled(self):
        _v1 = self.contracts["V1"]  # ensure contract exists in docs
        result = suggest_next("SETTLED", "test-sub", DEFAULT_CONFIG)
        assert result["action"] == "complete", (
            f"Contract V1 BROKEN: docs say SETTLED action='complete' but code returns '{result['action']}'"
        )
        assert result["cascade"] is False, "Contract V1 BROKEN: SETTLED should not cascade"

    def test_V2_falsified(self):
        _v2 = self.contracts["V2"]  # ensure contract exists in docs
        result = suggest_next("FALSIFIED", "test-sub", DEFAULT_CONFIG)
        assert result["action"] == "complete", (
            f"Contract V2 BROKEN: docs say FALSIFIED action='complete' but code returns '{result['action']}'"
        )
        assert result["cascade"] is True, "Contract V2 BROKEN: FALSIFIED should cascade"

    def test_V3_mixed(self):
        _v3 = self.contracts["V3"]  # ensure contract exists in docs
        result = suggest_next("MIXED", "test-sub", DEFAULT_CONFIG)
        assert result["cascade"] is False, "Contract V3 BROKEN: MIXED should not cascade"

    def test_V4_inconclusive(self):
        _v4 = self.contracts["V4"]  # ensure contract exists in docs
        result = suggest_next("INCONCLUSIVE", "test-sub", DEFAULT_CONFIG)
        assert result["action"] == "prompt_user", (
            f"Contract V4 BROKEN: docs say INCONCLUSIVE action='prompt_user' but code returns '{result['action']}'"
        )
        assert result["cascade"] is False, "Contract V4 BROKEN: INCONCLUSIVE should not cascade"


# ---------------------------------------------------------------------------
# Meta-test: ensure all contract IDs are covered
# ---------------------------------------------------------------------------


class TestContractCompleteness:
    """Verify that every contract ID in workflow.md has a corresponding test."""

    def test_all_state_contracts_tested(self):
        contracts = _load_state_contracts()
        contract_ids = {row["ID"] for row in contracts}
        # All test methods in TestStateTableContract
        test_methods = {
            m.replace("test_", "").split("_")[0].upper() for m in dir(TestStateTableContract) if m.startswith("test_T")
        }
        missing = contract_ids - test_methods
        assert not missing, (
            f"Contract IDs in workflow.md without tests: {missing}. Add test methods to TestStateTableContract."
        )

    def test_all_verdict_contracts_tested(self):
        contracts = _load_verdict_contracts()
        contract_ids = {row["ID"] for row in contracts}
        test_methods = {
            m.replace("test_", "").split("_")[0].upper()
            for m in dir(TestVerdictTableContract)
            if m.startswith("test_V")
        }
        missing = contract_ids - test_methods
        assert not missing, (
            f"Verdict contract IDs in workflow.md without tests: {missing}. "
            f"Add test methods to TestVerdictTableContract."
        )

    def test_workflow_md_exists(self):
        assert WORKFLOW_MD.exists(), (
            f"workflow.md not found at {WORKFLOW_MD}. Contract tests cannot run without the documentation file."
        )

    def test_contract_markers_present(self):
        text = WORKFLOW_MD.read_text(encoding="utf-8")
        assert "<!-- CONTRACT:STATE_TABLE_START -->" in text, "Missing STATE_TABLE_START marker in workflow.md"
        assert "<!-- CONTRACT:STATE_TABLE_END -->" in text, "Missing STATE_TABLE_END marker in workflow.md"
        assert "<!-- CONTRACT:VERDICT_TABLE_START -->" in text, "Missing VERDICT_TABLE_START marker in workflow.md"
        assert "<!-- CONTRACT:VERDICT_TABLE_END -->" in text, "Missing VERDICT_TABLE_END marker in workflow.md"
