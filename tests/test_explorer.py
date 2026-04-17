from __future__ import annotations

import json
import os

from principia.core.explorer import build_workspace_explorer_payload, generate_workspace_explorer


def _write_claim(
    claim_dir,
    claim_id: str,
    *,
    extra_frontmatter: str = "",
    document_name: str = "claim.md",
    title: str | None = None,
) -> None:
    claim_dir.mkdir(parents=True)
    (claim_dir / document_name).write_text(
        "---\n"
        f"id: {claim_id}\n"
        "type: claim\n"
        "status: pending\n"
        "date: 2026-01-01\n"
        f"{extra_frontmatter}"
        "---\n\n"
        f"# {title or claim_dir.name}\n\n"
        "Readable claim statement.\n",
        encoding="utf-8",
    )
    for role in ("architect", "adversary", "experimenter", "arbiter", "scout"):
        (claim_dir / role).mkdir(exist_ok=True)


def _claim_payload(payload: dict, claim_id: str) -> dict:
    return next(claim for claim in payload["claims"] if claim["id"] == claim_id)


def _transition(claim: dict, from_label: str, to_label: str) -> dict:
    return next(item for item in claim["transitions"] if item["from"] == from_label and item["to"] == to_label)


def test_workspace_explorer_payload_captures_claim_graph_and_steps(research_dir) -> None:
    (research_dir / ".north-star.md").write_text("# Locked\n", encoding="utf-8")
    (research_dir / ".context.md").write_text("# Context\n", encoding="utf-8")

    claim_a = research_dir / "claims" / "claim-1-foundation"
    claim_b = research_dir / "claims" / "claim-2-dependent"
    _write_claim(claim_a, "h1-foundation")
    _write_claim(claim_b, "h2-dependent", extra_frontmatter="depends_on: [h1-foundation]\n")

    (claim_a / "architect" / "round-1").mkdir(parents=True)
    (claim_a / "architect" / "round-1" / "packet.md").write_text(
        "# Dispatch Packet: architect\n\nPacket context.\n",
        encoding="utf-8",
    )
    (claim_a / "architect" / "round-1" / "prompt.md").write_text(
        "# External Prompt: architect\n\nArchitect prompt body.\n",
        encoding="utf-8",
    )
    (claim_a / "architect" / "round-1" / "result.md").write_text(
        "---\nid: a1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Architect\n\nConcrete proposal.\n",
        encoding="utf-8",
    )
    (claim_a / "adversary" / "round-1").mkdir(parents=True)
    (claim_a / "adversary" / "round-1" / "result.md").write_text(
        "---\nid: d1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Adversary\n\n**Severity**: minor\n",
        encoding="utf-8",
    )
    (claim_a / "experimenter" / "results").mkdir(parents=True)
    (claim_a / "experimenter" / "results" / "output.md").write_text(
        "---\nid: e1\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n## Results\n\nStrong evidence.\n",
        encoding="utf-8",
    )
    (claim_a / "arbiter" / "results").mkdir(parents=True)
    (claim_a / "arbiter" / "results" / "verdict.md").write_text(
        "---\n"
        "id: v1\n"
        "type: verdict\n"
        "status: active\n"
        "date: 2026-01-01\n"
        "---\n\n"
        "**Verdict**: PROVEN\n"
        "**Confidence**: high\n",
        encoding="utf-8",
    )
    (claim_a / ".post_verdict_done").write_text("2026-01-02", encoding="utf-8")

    payload = build_workspace_explorer_payload(research_dir)

    assert payload["workspace_root"] == str(research_dir)
    assert len(payload["claims"]) == 2
    assert payload["graph"]["edges"] == [
        {
            "source": "h1-foundation",
            "target": "h2-dependent",
            "relation": "depends_on",
        }
    ]
    assert payload["graph"]["waves"][0]["claim_ids"] == ["h1-foundation"]
    assert payload["graph"]["waves"][1]["claim_ids"] == ["h2-dependent"]
    assert "claims" not in payload["graph"]["waves"][0]

    claim_a_payload = _claim_payload(payload, "h1-foundation")
    assert claim_a_payload["label"] == "Claim 1"
    assert claim_a_payload["dependents"] == ["h2-dependent"]
    architect_step = next(step for step in claim_a_payload["steps"] if step["label"] == "Architect round 1")
    assert architect_step["artifact_count"] == 3
    assert architect_step["artifacts"]["packet"]["path"].endswith("architect/round-1/packet.md")
    assert "Architect prompt body." in architect_step["artifacts"]["prompt"]["content"]
    assert "Concrete proposal." in architect_step["artifacts"]["result"]["content"]
    experiment_transition = _transition(claim_a_payload, "Adversary round 1", "Experimenter")
    assert experiment_transition["status"] == "complete"
    assert "minor" in experiment_transition["reason"].lower()
    assert experiment_transition["detail"] == "Severity: minor"
    arbiter_step = next(step for step in claim_a_payload["steps"] if step["label"] == "Arbiter")
    assert arbiter_step["status"] == "complete"
    assert "PROVEN" in arbiter_step["detail"]
    recorded_step = next(step for step in claim_a_payload["steps"] if step["label"] == "Recorded")
    assert recorded_step["status"] == "complete"


def test_workspace_explorer_does_not_fabricate_extra_rounds_after_exit(research_dir) -> None:
    claim_dir = research_dir / "claims" / "claim-1-minor-exit"
    _write_claim(claim_dir, "h1-minor-exit")

    (claim_dir / "architect" / "round-1").mkdir(parents=True)
    (claim_dir / "architect" / "round-1" / "result.md").write_text(
        "---\nid: a1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Architect\n",
        encoding="utf-8",
    )
    (claim_dir / "adversary" / "round-1").mkdir(parents=True)
    (claim_dir / "adversary" / "round-1" / "result.md").write_text(
        "---\nid: d1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n**Severity**: minor\n",
        encoding="utf-8",
    )
    (claim_dir / "experimenter" / "results").mkdir(parents=True)
    (claim_dir / "experimenter" / "results" / "output.md").write_text(
        "---\nid: e1\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n## Results\n",
        encoding="utf-8",
    )

    claim = _claim_payload(build_workspace_explorer_payload(research_dir), "h1-minor-exit")

    routes = {(item["from"], item["to"]) for item in claim["transitions"]}
    assert ("Adversary round 1", "Experimenter") in routes
    assert all("round 2" not in value.lower() for route in routes for value in route)


def test_workspace_explorer_waiting_architect_round_one_shows_handoff(research_dir) -> None:
    claim_dir = research_dir / "claims" / "claim-1-waiting-architect"
    _write_claim(claim_dir, "h1-waiting-architect")

    (claim_dir / "architect" / "round-1").mkdir(parents=True)
    (claim_dir / "architect" / "round-1" / "prompt.md").write_text(
        "# External Prompt: architect\n\nWaiting on architect.\n",
        encoding="utf-8",
    )

    claim = _claim_payload(build_workspace_explorer_payload(research_dir), "h1-waiting-architect")

    architect_step = next(step for step in claim["steps"] if step["label"] == "Architect round 1")
    assert architect_step["status"] == "waiting_result"
    claim_to_architect = _transition(claim, "Claim definition", "Architect round 1")
    assert claim_to_architect["status"] == "waiting_result"
    architect_to_adversary = _transition(claim, "Architect round 1", "Adversary round 1")
    assert architect_to_adversary["status"] == "pending"


def test_workspace_explorer_uses_legacy_post_verdict_completion_fallback(research_dir) -> None:
    claim_dir = research_dir / "claims" / "claim-1-legacy-recording"
    _write_claim(claim_dir, "h1-legacy-recording")

    (claim_dir / "architect" / "round-1").mkdir(parents=True)
    (claim_dir / "architect" / "round-1" / "result.md").write_text(
        "---\nid: a1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Architect\n",
        encoding="utf-8",
    )
    (claim_dir / "adversary" / "round-1").mkdir(parents=True)
    (claim_dir / "adversary" / "round-1" / "result.md").write_text(
        "---\nid: d1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n**Severity**: minor\n",
        encoding="utf-8",
    )
    (claim_dir / "experimenter" / "results").mkdir(parents=True)
    (claim_dir / "experimenter" / "results" / "output.md").write_text(
        "---\nid: e1\ntype: evidence\nstatus: active\ndate: 2026-01-01\n---\n\n## Results\n",
        encoding="utf-8",
    )
    (claim_dir / "arbiter" / "results").mkdir(parents=True)
    verdict_file = claim_dir / "arbiter" / "results" / "verdict.md"
    verdict_file.write_text(
        "---\nid: v1\ntype: verdict\nstatus: active\ndate: 2026-01-01\n---\n\n**Verdict**: PROVEN\n",
        encoding="utf-8",
    )
    claim_file = claim_dir / "claim.md"
    verdict_mtime = verdict_file.stat().st_mtime
    os.utime(claim_file, (verdict_mtime + 10, verdict_mtime + 10))

    claim = _claim_payload(build_workspace_explorer_payload(research_dir), "h1-legacy-recording")

    recorded_step = next(step for step in claim["steps"] if step["label"] == "Recorded")
    assert recorded_step["status"] == "complete"
    assert recorded_step["detail"] == "Legacy completion fallback"
    assert _transition(claim, "Arbiter", "Post-verdict recording")["status"] == "complete"
    assert _transition(claim, "Post-verdict recording", "Complete: Proven")["status"] == "complete"


def test_workspace_explorer_distinguishes_ready_and_waiting_dispatches(research_dir) -> None:
    claim_dir = research_dir / "claims" / "claim-1-dispatch-status"
    _write_claim(claim_dir, "h1-dispatch-status")

    (claim_dir / "architect" / "round-1").mkdir(parents=True)
    (claim_dir / "architect" / "round-1" / "result.md").write_text(
        "---\nid: a1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n# Architect\n",
        encoding="utf-8",
    )
    (claim_dir / "adversary" / "round-1").mkdir(parents=True)
    (claim_dir / "adversary" / "round-1" / "result.md").write_text(
        "---\nid: d1\ntype: claim\nstatus: active\ndate: 2026-01-01\n---\n\n**Severity**: minor\n",
        encoding="utf-8",
    )

    claim = _claim_payload(build_workspace_explorer_payload(research_dir), "h1-dispatch-status")
    assert _transition(claim, "Adversary round 1", "Experimenter")["status"] == "ready_to_send"

    (claim_dir / "experimenter" / "prompt.md").write_text(
        "# External Prompt: experimenter\n\nWaiting on experimenter.\n",
        encoding="utf-8",
    )
    claim = _claim_payload(build_workspace_explorer_payload(research_dir), "h1-dispatch-status")
    assert _transition(claim, "Adversary round 1", "Experimenter")["status"] == "waiting_result"


def test_workspace_explorer_surfaces_dependency_cycles(research_dir) -> None:
    claim_a = research_dir / "claims" / "claim-1-alpha"
    claim_b = research_dir / "claims" / "claim-2-beta"
    _write_claim(claim_a, "h1-alpha", extra_frontmatter="depends_on: [h2-beta]\n")
    _write_claim(claim_b, "h2-beta", extra_frontmatter="depends_on: [h1-alpha]\n")

    payload = build_workspace_explorer_payload(research_dir)

    assert payload["graph"]["waves"][0]["kind"] == "cycle"
    assert payload["graph"]["waves"][0]["claim_ids"] == ["h1-alpha", "h2-beta"]
    assert payload["graph"]["cycle_claim_ids"] == ["h1-alpha", "h2-beta"]
    claim_a_payload = _claim_payload(payload, "h1-alpha")
    claim_b_payload = _claim_payload(payload, "h2-beta")
    assert claim_a_payload["wave"] is None
    assert claim_b_payload["wave"] is None
    assert claim_a_payload["wave_kind"] == "cycle"
    assert claim_b_payload["wave_kind"] == "cycle"


def test_workspace_explorer_distinguishes_cycle_members_from_cycle_blocked_claims(research_dir) -> None:
    claim_a = research_dir / "claims" / "claim-1-alpha"
    claim_b = research_dir / "claims" / "claim-2-beta"
    claim_c = research_dir / "claims" / "claim-3-gamma"
    _write_claim(claim_a, "h1-alpha", extra_frontmatter="depends_on: [h2-beta]\n")
    _write_claim(claim_b, "h2-beta", extra_frontmatter="depends_on: [h1-alpha]\n")
    _write_claim(claim_c, "h3-gamma", extra_frontmatter="depends_on: [h1-alpha]\n")

    payload = build_workspace_explorer_payload(research_dir)

    assert payload["graph"]["cycle_claim_ids"] == ["h1-alpha", "h2-beta"]
    assert payload["graph"]["blocked_claim_ids"] == ["h3-gamma"]
    assert payload["graph"]["waves"][0]["kind"] == "cycle"
    assert payload["graph"]["waves"][0]["claim_ids"] == ["h1-alpha", "h2-beta"]
    assert payload["graph"]["waves"][1]["kind"] == "blocked"
    assert payload["graph"]["waves"][1]["claim_ids"] == ["h3-gamma"]
    claim_c_payload = _claim_payload(payload, "h3-gamma")
    assert claim_c_payload["wave"] is None
    assert claim_c_payload["wave_kind"] == "blocked"


def test_workspace_explorer_labels_legacy_frontiers(research_dir) -> None:
    frontier_dir = research_dir / "cycles" / "cycle-1" / "unit-1-test" / "sub-1a-probe"
    _write_claim(
        frontier_dir,
        "h1-frontier",
        document_name="frontier.md",
        title="Legacy frontier",
    )

    claim = _claim_payload(build_workspace_explorer_payload(research_dir), "h1-frontier")

    assert claim["kind"] == "frontier"
    assert claim["label"] == "Frontier 1A"
    assert claim["hierarchy"] == "Cycle 1 / Unit 1"


def test_workspace_explorer_tolerates_invalid_utf8_artifacts(research_dir) -> None:
    claim_dir = research_dir / "claims" / "claim-1-invalid-prompt"
    _write_claim(claim_dir, "h1-invalid-prompt")

    (claim_dir / "architect" / "round-1").mkdir(parents=True)
    (claim_dir / "architect" / "round-1" / "prompt.md").write_bytes(b"\xff\xfe")

    _html_path, _json_path, payload = generate_workspace_explorer(research_dir)

    claim = _claim_payload(payload, "h1-invalid-prompt")
    architect_step = next(step for step in claim["steps"] if step["label"] == "Architect round 1")
    assert architect_step["status"] == "waiting_result"
    assert architect_step["artifacts"]["prompt"]["read_error"] == (
        "Artifact could not be rendered because it is not valid UTF-8."
    )
    assert "not valid UTF-8" in architect_step["artifacts"]["prompt"]["content"]


def test_generate_workspace_explorer_writes_html_and_json(research_dir) -> None:
    claim_dir = research_dir / "claims" / "claim-1-test"
    _write_claim(claim_dir, "h1-claim", title="Test Claim")

    html_path, json_path, payload = generate_workspace_explorer(research_dir)

    assert html_path == research_dir / "WORKSPACE_EXPLORER.html"
    assert json_path == research_dir / "WORKSPACE_EXPLORER.json"
    assert html_path.exists()
    assert json_path.exists()
    html_text = html_path.read_text(encoding="utf-8")
    assert "Principia Workspace Explorer" in html_text
    assert "Claim Graph" in html_text
    assert "State Transitions" in html_text
    assert "Agent Artifacts" in html_text
    assert "Drag to pan." in html_text
    assert "Test Claim" in html_text
    assert "No claim matches the current filter." in html_text
    json_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert json_payload["claims"][0]["id"] == "h1-claim"
    assert json_payload["graph"]["waves"][0]["claim_ids"] == ["h1-claim"]
    assert payload["claims"][0]["id"] == "h1-claim"
