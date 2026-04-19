"""Generated workspace explorer for Principia claims and claim-state flows."""

from __future__ import annotations

import argparse
import contextlib
import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import config as _cfg
from .commands import get_dashboard_payload, get_dispatch_log_payload
from .db import build_db
from .frontmatter import get_body, get_scalar_frontmatter, parse_frontmatter
from .orchestration import (
    _check_post_verdict_complete,
    detect_state,
    extract_confidence,
    extract_severity,
    extract_verdict,
    find_completed_rounds,
    load_config,
)

_PRIMARY_CLAIM_SQL = "(file_path LIKE 'claims/claim-%/claim.md' OR file_path LIKE 'cycles/%/frontier.md')"
_EXPLORER_HTML = "WORKSPACE_EXPLORER.html"
_EXPLORER_JSON = "WORKSPACE_EXPLORER.json"
_WAITING_ROUND_RE = re.compile(r"^(architect|adversary) round (\d+)$")


def _workspace_root(root: Path | None = None) -> Path:
    if root is None:
        return _cfg.RESEARCH_DIR.resolve()
    return root.resolve()


def _workspace_label(root: Path) -> str:
    if root.name == "principia" and root.parent != root:
        return root.parent.name
    return root.name


def _format_timestamp(value: float | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_utf8_text(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, "Artifact could not be rendered because it is not valid UTF-8."
    except (OSError, ValueError):
        return None, "Artifact could not be read."


def _truncate(text: str, limit: int = 280) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _body_excerpt(path: Path, root: Path, limit: int = 280) -> str:
    if not path.exists():
        return ""
    text, error = _read_utf8_text(path)
    if text is None:
        return error or ""
    body = get_body(text).strip()
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    return _truncate_excerpt(" ".join(lines), limit=limit)


def _truncate_excerpt(text: str, limit: int = 280) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _artifact_payload(path: Path, root: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    text, error = _read_utf8_text(path)
    content = text if text is not None else f"[{error}]"
    payload = {
        "path": path.relative_to(root).as_posix(),
        "modified_at": _format_timestamp(path.stat().st_mtime),
        "line_count": len(content.splitlines()) or (1 if content else 0),
        "content": content,
    }
    if error:
        payload["read_error"] = error
    return payload


def _claim_sub_unit(file_path: str) -> str:
    return Path(file_path).parent.as_posix()


def _claim_number(name: str) -> str:
    match = re.match(r"claim-(\d+)", name)
    return match.group(1) if match else "?"


def _cycle_segment_number(name: str, prefix: str) -> str | None:
    match = re.match(rf"{prefix}-([^-]+)", name)
    if not match:
        return None
    return match.group(1)


def _claim_display_meta(sub_unit: str) -> dict[str, str | None]:
    parts = Path(sub_unit).parts
    leaf = Path(sub_unit).name
    claim_number = _claim_number(leaf)
    if claim_number != "?":
        return {
            "kind": "claim",
            "kind_label": "Claim",
            "number": claim_number,
            "label": f"Claim {claim_number}",
            "hierarchy": None,
        }

    cycle_number = _cycle_segment_number(parts[1], "cycle") if len(parts) > 1 else None
    unit_number = _cycle_segment_number(parts[2], "unit") if len(parts) > 2 else None
    frontier_number = _cycle_segment_number(parts[3], "sub") if len(parts) > 3 else None
    hierarchy_parts = []
    if cycle_number:
        hierarchy_parts.append(f"Cycle {cycle_number}")
    if unit_number:
        hierarchy_parts.append(f"Unit {unit_number.upper()}")
    frontier_label = f"Frontier {frontier_number.upper()}" if frontier_number else "Frontier"
    return {
        "kind": "frontier",
        "kind_label": "Frontier",
        "number": frontier_number.upper() if frontier_number else None,
        "label": frontier_label,
        "hierarchy": " / ".join(hierarchy_parts) or None,
    }


def _human_title(name: str) -> str:
    cleaned = re.sub(r"^(claim|cycle)-\d+-", "", name)
    return cleaned.replace("-", " ").strip().title() or name


def _read_claim_meta(path: Path, root: Path) -> tuple[dict[str, Any], str]:
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8")
    return parse_frontmatter(text, filepath=rel), _body_excerpt(path, root)


def _stage_status(packet: Path, prompt: Path, result: Path, expected: bool = False) -> str:
    if result.exists():
        return "complete"
    if prompt.exists():
        return "waiting_result"
    if packet.exists():
        return "ready_to_send"
    if expected:
        return "queued"
    return "pending"


def _relative_or_none(path: Path, root: Path) -> str | None:
    if not path.exists():
        return None
    return path.relative_to(root).as_posix()


def _step_payload(
    *,
    label: str,
    phase: str,
    status: str,
    summary: str = "",
    packet: Path | None = None,
    prompt: Path | None = None,
    result: Path | None = None,
    root: Path,
    round_num: int | None = None,
    agent: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    artifacts = {
        "packet": _artifact_payload(packet, root) if packet is not None else None,
        "prompt": _artifact_payload(prompt, root) if prompt is not None else None,
        "result": _artifact_payload(result, root) if result is not None else None,
    }
    existing = [path for path in (result, prompt, packet) if path is not None and path.exists()]
    modified_at = None
    if existing:
        modified_at = _format_timestamp(max(path.stat().st_mtime for path in existing))
    return {
        "label": label,
        "phase": phase,
        "status": status,
        "summary": summary,
        "round": round_num,
        "agent": agent,
        "detail": detail,
        "modified_at": modified_at,
        "artifact_count": sum(1 for artifact in artifacts.values() if artifact),
        "artifacts": artifacts,
        "files": {
            "packet": _relative_or_none(packet, root) if packet is not None else None,
            "prompt": _relative_or_none(prompt, root) if prompt is not None else None,
            "result": _relative_or_none(result, root) if result is not None else None,
        },
    }


def _claim_steps(
    *,
    claim_dir: Path,
    claim_file: Path,
    root: Path,
    state: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    claim_meta, claim_excerpt = _read_claim_meta(claim_file, root)
    steps = [
        _step_payload(
            label="Claim definition",
            phase="claim",
            status="complete",
            summary=claim_excerpt,
            result=claim_file,
            root=root,
            detail=get_scalar_frontmatter(
                claim_meta,
                "falsification",
                filepath=claim_file.relative_to(root).as_posix(),
            ),
            agent="claim",
        )
    ]

    scout_dir = claim_dir / "scout"
    scout_packet = scout_dir / "packet.md"
    scout_prompt = scout_dir / "prompt.md"
    scout_result = scout_dir / "result.md"
    if scout_packet.exists() or scout_prompt.exists() or scout_result.exists() or state.get("agent") == "scout":
        steps.append(
            _step_payload(
                label="Scout",
                phase="research",
                status=_stage_status(
                    scout_packet,
                    scout_prompt,
                    scout_result,
                    expected=state.get("agent") == "scout",
                ),
                summary=_body_excerpt(scout_result, root) if scout_result.exists() else "",
                packet=scout_packet,
                prompt=scout_prompt,
                result=scout_result,
                root=root,
                agent="scout",
            )
        )

    architect_rounds = find_completed_rounds(claim_dir / "architect")
    adversary_rounds = find_completed_rounds(claim_dir / "adversary")
    active_architect_round = _active_round_for_agent(state, "architect") or 0
    active_adversary_round = _active_round_for_agent(state, "adversary") or 0
    max_round = max([0, *architect_rounds, *adversary_rounds, active_architect_round, active_adversary_round])

    for round_num in range(1, max_round + 1):
        for agent, phase in (("architect", "debate"), ("adversary", "debate")):
            round_dir = claim_dir / agent / f"round-{round_num}"
            packet = round_dir / "packet.md"
            prompt = round_dir / "prompt.md"
            result = round_dir / "result.md"
            expected = state.get("agent") == agent and state.get("round") == round_num
            summary = _body_excerpt(result, root) if result.exists() else ""
            detail = None
            if agent == "adversary" and result.exists():
                from .orchestration import extract_severity

                detail = f"Severity: {extract_severity(result, config)}"
            steps.append(
                _step_payload(
                    label=f"{agent.title()} round {round_num}",
                    phase=phase,
                    status=_stage_status(packet, prompt, result, expected=expected),
                    summary=summary,
                    packet=packet,
                    prompt=prompt,
                    result=result,
                    root=root,
                    round_num=round_num,
                    agent=agent,
                    detail=detail,
                )
            )

    experimenter_dir = claim_dir / "experimenter"
    experimenter_packet = experimenter_dir / "packet.md"
    experimenter_prompt = experimenter_dir / "prompt.md"
    experimenter_result = experimenter_dir / "results" / "output.md"
    steps.append(
        _step_payload(
            label="Experimenter",
            phase="experiment",
            status=_stage_status(
                experimenter_packet,
                experimenter_prompt,
                experimenter_result,
                expected=state.get("agent") == "experimenter",
            ),
            summary=_body_excerpt(experimenter_result, root) if experimenter_result.exists() else "",
            packet=experimenter_packet,
            prompt=experimenter_prompt,
            result=experimenter_result,
            root=root,
            agent="experimenter",
        )
    )

    arbiter_dir = claim_dir / "arbiter"
    arbiter_packet = arbiter_dir / "packet.md"
    arbiter_prompt = arbiter_dir / "prompt.md"
    arbiter_result = arbiter_dir / "results" / "verdict.md"
    verdict_detail = None
    if arbiter_result.exists():
        verdict = extract_verdict(arbiter_result, config)
        confidence = extract_confidence(arbiter_result)
        verdict_detail = f"Verdict: {verdict} ({confidence})"
    steps.append(
        _step_payload(
            label="Arbiter",
            phase="verdict",
            status=_stage_status(
                arbiter_packet,
                arbiter_prompt,
                arbiter_result,
                expected=state.get("agent") == "arbiter",
            ),
            summary=_body_excerpt(arbiter_result, root) if arbiter_result.exists() else "",
            packet=arbiter_packet,
            prompt=arbiter_prompt,
            result=arbiter_result,
            root=root,
            agent="arbiter",
            detail=verdict_detail,
        )
    )

    recorded_marker = claim_dir / ".post_verdict_done"
    post_verdict_done = _check_post_verdict_complete(claim_dir)
    recorded_summary = ""
    recorded_detail = None
    if post_verdict_done:
        if recorded_marker.exists():
            recorded_summary = "Post-verdict bookkeeping completed."
        else:
            recorded_summary = "Post-verdict bookkeeping inferred from legacy claim timestamps."
            recorded_detail = "Legacy completion fallback"
    steps.append(
        _step_payload(
            label="Recorded",
            phase="recording",
            status="complete" if post_verdict_done else "pending",
            summary=recorded_summary,
            result=recorded_marker,
            root=root,
            agent="reviewer",
            detail=recorded_detail,
        )
    )
    return steps


def _transition_evidence(*paths: Path, root: Path) -> list[str]:
    evidence = []
    for path in paths:
        if path.exists():
            evidence.append(path.relative_to(root).as_posix())
    return evidence


def _transition_status(*, complete: bool, status: str = "pending") -> str:
    if complete:
        return "complete"
    return status


def _waiting_round_for_agent(state: dict[str, Any], agent: str) -> int | None:
    if str(state.get("action") or "") != "waiting":
        return None
    waiting_for = str(state.get("waiting_for") or "")
    match = _WAITING_ROUND_RE.match(waiting_for)
    if not match or match.group(1) != agent:
        return None
    return int(match.group(2))


def _active_round_for_agent(state: dict[str, Any], agent: str) -> int | None:
    action = str(state.get("action") or "")
    if action == f"dispatch_{agent}" and isinstance(state.get("round"), int):
        return int(state["round"])
    return _waiting_round_for_agent(state, agent)


def _transition_target_status(state: dict[str, Any], target: str, round_num: int | None = None) -> str:
    action = str(state.get("action") or "")
    waiting_for = str(state.get("waiting_for") or "")
    if target in {"architect", "adversary"}:
        if action == f"dispatch_{target}" and state.get("round") == round_num:
            return "ready_to_send"
        if action == "waiting" and waiting_for == f"{target} round {round_num}":
            return "waiting_result"
    if target == "experimenter":
        if action == "dispatch_experimenter":
            return "ready_to_send"
        if action == "waiting" and waiting_for == "experimenter":
            return "waiting_result"
    if target == "arbiter":
        if action == "dispatch_arbiter":
            return "ready_to_send"
        if action == "waiting" and waiting_for == "arbiter":
            return "waiting_result"
    if target == "post_verdict" and action == "post_verdict":
        return "current"
    if target == "reviewer":
        if action == "dispatch_reviewer":
            return "ready_to_send"
        if action == "waiting" and waiting_for == "reviewer":
            return "waiting_result"
    if target == "complete" and action.startswith("complete_"):
        return "current"
    return "pending"


def _transition_payload(
    *,
    key: str,
    from_label: str,
    to_label: str,
    phase: str,
    status: str,
    reason: str,
    detail: str | None = None,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "from": from_label,
        "to": to_label,
        "phase": phase,
        "status": status,
        "reason": reason,
        "detail": detail,
        "evidence": evidence or [],
    }


def _stage_started(*paths: Path) -> bool:
    return any(path.exists() for path in paths)


def _cyclic_claim_ids(claim_ids: set[str], dependencies: dict[str, list[str]]) -> set[str]:
    index = 0
    stack: list[str] = []
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    on_stack: set[str] = set()
    cyclic_ids: set[str] = set()

    def strongconnect(node_id: str) -> None:
        nonlocal index
        indices[node_id] = index
        lowlinks[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)

        for dep_id in dependencies.get(node_id, []):
            if dep_id not in claim_ids:
                continue
            if dep_id not in indices:
                strongconnect(dep_id)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[dep_id])
            elif dep_id in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indices[dep_id])

        if lowlinks[node_id] != indices[node_id]:
            return

        component: list[str] = []
        while stack:
            member = stack.pop()
            on_stack.discard(member)
            component.append(member)
            if member == node_id:
                break

        if len(component) > 1 or (len(component) == 1 and component[0] in dependencies.get(component[0], [])):
            cyclic_ids.update(component)

    for claim_id in sorted(claim_ids):
        if claim_id not in indices:
            strongconnect(claim_id)

    return cyclic_ids


def _claim_transitions(
    *,
    claim_dir: Path,
    claim_file: Path,
    root: Path,
    state: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    target = claim_dir
    debate_config = config.get("debate_loop", {})
    max_rounds = debate_config.get("max_rounds", 3)
    override_file = target / ".max_rounds_override"
    if override_file.exists():
        with contextlib.suppress(OSError, ValueError):
            max_rounds = int(override_file.read_text(encoding="utf-8").strip())

    roles = config.get("roles", [])
    roles_config = {role["name"]: role for role in roles if isinstance(role, dict) and "name" in role}
    adversary_config = roles_config.get("adversary", {})
    exit_condition = adversary_config.get("exit_condition", {})
    exit_on = exit_condition.get("exit_on", ["minor", "none"])
    continue_on = exit_condition.get("continue_on", ["fatal", "serious"])
    unknown_default = exit_condition.get("unknown", "continue")

    architect_dir = target / "architect"
    adversary_dir = target / "adversary"
    experimenter_dir = target / "experimenter"
    arbiter_dir = target / "arbiter"
    experimenter_packet = experimenter_dir / "packet.md"
    experimenter_prompt = experimenter_dir / "prompt.md"
    experimenter_result = experimenter_dir / "results" / "output.md"
    arbiter_packet = arbiter_dir / "packet.md"
    arbiter_prompt = arbiter_dir / "prompt.md"
    verdict_result = arbiter_dir / "results" / "verdict.md"
    recorded_marker = target / ".post_verdict_done"

    architect_rounds = find_completed_rounds(architect_dir)
    adversary_rounds = find_completed_rounds(adversary_dir)
    active_architect_round = _active_round_for_agent(state, "architect")
    active_adversary_round = _active_round_for_agent(state, "adversary")
    max_known_round = max(
        [0, *architect_rounds, *adversary_rounds, active_architect_round or 0, active_adversary_round or 0]
    )

    experimenter_started = _stage_started(experimenter_packet, experimenter_prompt, experimenter_result)
    has_verdict = verdict_result.exists()
    arbiter_started = _stage_started(arbiter_packet, arbiter_prompt, verdict_result)
    post_verdict_done = _check_post_verdict_complete(target)

    transitions: list[dict[str, Any]] = []
    claim_label = "Claim definition"

    if max_rounds == 0:
        transitions.append(
            _transition_payload(
                key="claim-to-experimenter",
                from_label=claim_label,
                to_label="Experimenter",
                phase="experiment",
                status=_transition_status(
                    complete=experimenter_result.exists() or arbiter_started or post_verdict_done,
                    status=_transition_target_status(state, "experimenter"),
                ),
                reason="Debate is skipped because max_rounds is 0, so the claim goes directly to experiment.",
                evidence=_transition_evidence(
                    claim_file,
                    experimenter_packet,
                    experimenter_prompt,
                    experimenter_result,
                    root=root,
                ),
            )
        )
    else:
        round_num = 1
        while True:
            architect_result = architect_dir / f"round-{round_num}" / "result.md"
            architect_prompt = architect_dir / f"round-{round_num}" / "prompt.md"
            architect_packet = architect_dir / f"round-{round_num}" / "packet.md"
            adversary_result = adversary_dir / f"round-{round_num}" / "result.md"
            adversary_prompt = adversary_dir / f"round-{round_num}" / "prompt.md"
            adversary_packet = adversary_dir / f"round-{round_num}" / "packet.md"
            architect_started = _stage_started(architect_packet, architect_prompt, architect_result)
            adversary_started = _stage_started(adversary_packet, adversary_prompt, adversary_result)
            architect_relevant = (
                architect_started
                or adversary_started
                or round_num in architect_rounds
                or round_num in adversary_rounds
                or active_architect_round == round_num
                or active_adversary_round == round_num
                or (round_num == 1 and not (experimenter_started or arbiter_started or post_verdict_done))
            )
            if not architect_relevant:
                break

            if round_num == 1:
                architect_reason = "No architect result existed yet, so the debate opens with architect round 1."
                architect_detail = None
                architect_evidence = _transition_evidence(
                    claim_file,
                    architect_packet,
                    architect_prompt,
                    architect_result,
                    root=root,
                )
            else:
                prior_result = adversary_dir / f"round-{round_num - 1}" / "result.md"
                prior_severity = extract_severity(prior_result, config) if prior_result.exists() else "unknown"
                architect_detail = f"Severity: {prior_severity}" if prior_result.exists() else None
                if prior_severity in continue_on:
                    architect_reason = (
                        f"Adversary round {round_num - 1} reported {prior_severity}, "
                        f"so the debate continues into architect round {round_num}."
                    )
                elif prior_severity == "unknown" and unknown_default == "continue":
                    architect_reason = (
                        f"Adversary round {round_num - 1} had unknown severity, and the "
                        f"config defaults unknown severities to continue debate into architect round {round_num}."
                    )
                else:
                    architect_reason = (
                        f"Workflow artifacts exist for architect round {round_num}, "
                        "so the debate advanced to another architect response."
                    )
                architect_evidence = _transition_evidence(
                    prior_result,
                    architect_packet,
                    architect_prompt,
                    architect_result,
                    root=root,
                )
            architect_complete = (
                architect_result.exists()
                or adversary_started
                or round_num < max_known_round
                or experimenter_started
                or arbiter_started
                or post_verdict_done
            )
            transitions.append(
                _transition_payload(
                    key=f"architect-{round_num}",
                    from_label=claim_label if round_num == 1 else f"Adversary round {round_num - 1}",
                    to_label=f"Architect round {round_num}",
                    phase="debate",
                    status=_transition_status(
                        complete=architect_complete,
                        status=_transition_target_status(state, "architect", round_num),
                    ),
                    reason=architect_reason,
                    detail=architect_detail,
                    evidence=architect_evidence,
                )
            )

            adversary_complete = (
                adversary_result.exists()
                or round_num < max_known_round
                or experimenter_started
                or arbiter_started
                or post_verdict_done
            )
            transitions.append(
                _transition_payload(
                    key=f"adversary-{round_num}",
                    from_label=f"Architect round {round_num}",
                    to_label=f"Adversary round {round_num}",
                    phase="debate",
                    status=_transition_status(
                        complete=adversary_complete,
                        status=_transition_target_status(state, "adversary", round_num),
                    ),
                    reason=(
                        f"Architect round {round_num} completed, so adversary round "
                        f"{round_num} reviews the same proposal."
                    ),
                    evidence=_transition_evidence(
                        architect_result,
                        adversary_packet,
                        adversary_prompt,
                        adversary_result,
                        root=root,
                    ),
                )
            )

            if not adversary_result.exists():
                break

            severity = extract_severity(adversary_result, config)
            if round_num >= max_rounds:
                transitions.append(
                    _transition_payload(
                        key=f"experimenter-{round_num}",
                        from_label=f"Adversary round {round_num}",
                        to_label="Experimenter",
                        phase="experiment",
                        status=_transition_status(
                            complete=experimenter_result.exists() or arbiter_started or post_verdict_done,
                            status=_transition_target_status(state, "experimenter"),
                        ),
                        reason=(
                            f"Adversary round {round_num} closed the final allowed debate "
                            "round, so the workflow exits to experimenter."
                        ),
                        detail=f"Severity: {severity}",
                        evidence=_transition_evidence(
                            adversary_result,
                            experimenter_packet,
                            experimenter_prompt,
                            experimenter_result,
                            root=root,
                        ),
                    )
                )
                break

            if severity in exit_on:
                transitions.append(
                    _transition_payload(
                        key=f"experimenter-{round_num}",
                        from_label=f"Adversary round {round_num}",
                        to_label="Experimenter",
                        phase="experiment",
                        status=_transition_status(
                            complete=experimenter_result.exists() or arbiter_started or post_verdict_done,
                            status=_transition_target_status(state, "experimenter"),
                        ),
                        reason=(
                            f"Adversary round {round_num} reported {severity}, which "
                            "matches the configured debate exit condition."
                        ),
                        detail=f"Severity: {severity}",
                        evidence=_transition_evidence(
                            adversary_result,
                            experimenter_packet,
                            experimenter_prompt,
                            experimenter_result,
                            root=root,
                        ),
                    )
                )
                break

            if severity in continue_on:
                round_num += 1
                continue

            if unknown_default == "continue":
                round_num += 1
                continue

            transitions.append(
                _transition_payload(
                    key=f"experimenter-{round_num}",
                    from_label=f"Adversary round {round_num}",
                    to_label="Experimenter",
                    phase="experiment",
                    status=_transition_status(
                        complete=experimenter_result.exists() or arbiter_started or post_verdict_done,
                        status=_transition_target_status(state, "experimenter"),
                    ),
                    reason=(
                        f"Adversary round {round_num} had unknown severity, and the "
                        "config defaults unknown severities to exit debate."
                    ),
                    detail=f"Severity: {severity}",
                    evidence=_transition_evidence(
                        adversary_result,
                        experimenter_packet,
                        experimenter_prompt,
                        experimenter_result,
                        root=root,
                    ),
                )
            )
            break

    transitions.append(
        _transition_payload(
            key="experimenter-to-arbiter",
            from_label="Experimenter",
            to_label="Arbiter",
            phase="verdict",
            status=_transition_status(
                complete=has_verdict or post_verdict_done,
                status=_transition_target_status(state, "arbiter"),
            ),
            reason="Once experimenter evidence exists, the arbiter can produce a verdict.",
            evidence=_transition_evidence(
                experimenter_result,
                arbiter_packet,
                arbiter_prompt,
                verdict_result,
                root=root,
            ),
        )
    )

    if config.get("auto_review", True):
        recording_label = "Post-verdict recording"
        recording_target = "post_verdict"
        recording_reason = (
            "When the arbiter writes a verdict, the workflow runs post-verdict bookkeeping automatically."
        )
        if has_verdict:
            recording_reason = (
                "The arbiter wrote a verdict, so the workflow runs post-verdict bookkeeping automatically."
            )
    else:
        recording_label = "Reviewer dispatch"
        recording_target = "reviewer"
        recording_reason = "When the arbiter writes a verdict, a reviewer must record the outcome."
        if has_verdict:
            recording_reason = "The arbiter wrote a verdict, so a reviewer must record the outcome."

    transitions.append(
        _transition_payload(
            key="verdict-to-recording",
            from_label="Arbiter",
            to_label=recording_label,
            phase="recording",
            status=_transition_status(
                complete=post_verdict_done,
                status=_transition_target_status(state, recording_target),
            ),
            reason=recording_reason,
            evidence=_transition_evidence(
                verdict_result,
                recorded_marker,
                claim_file if post_verdict_done and not recorded_marker.exists() else Path("__missing__"),
                root=root,
            ),
        )
    )

    verdict = extract_verdict(verdict_result, config) if verdict_result.exists() else "UNKNOWN"
    complete_reason = (
        f"Post-verdict bookkeeping is complete, so the claim settles into the final workflow state: {verdict}."
        if post_verdict_done
        else "The claim becomes complete only after the arbiter writes a verdict and recording finishes."
    )
    transitions.append(
        _transition_payload(
            key="recording-to-complete",
            from_label=recording_label,
            to_label=f"Complete: {verdict.title() if verdict != 'UNKNOWN' else 'Unknown'}",
            phase="complete",
            status=_transition_status(
                complete=post_verdict_done,
                status=_transition_target_status(state, "complete"),
            ),
            reason=complete_reason,
            evidence=_transition_evidence(
                recorded_marker,
                verdict_result,
                claim_file if post_verdict_done and not recorded_marker.exists() else Path("__missing__"),
                root=root,
            ),
        )
    )

    return transitions


def _claim_waves(
    claims: list[dict[str, Any]],
    dependencies: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], dict[str, int], set[str], set[str]]:
    claim_ids = {claim["id"] for claim in claims}
    claim_files = {claim["id"]: claim["file"] for claim in claims}
    deps = {claim["id"]: [dep for dep in dependencies.get(claim["id"], []) if dep in claim_ids] for claim in claims}
    remaining = set(claim_ids)
    in_degree = {claim_id: len(deps[claim_id]) for claim_id in claim_ids}
    waves: list[dict[str, Any]] = []
    while remaining:
        ready = sorted(
            [claim_id for claim_id in remaining if in_degree.get(claim_id, 0) == 0],
            key=lambda claim_id: claim_files.get(claim_id, claim_id),
        )
        if not ready:
            cycle_ids = _cyclic_claim_ids(remaining, deps)
            cycle_claim_ids = sorted(cycle_ids, key=lambda claim_id: claim_files.get(claim_id, claim_id))
            blocked_claim_ids = sorted(remaining - cycle_ids, key=lambda claim_id: claim_files.get(claim_id, claim_id))
            if cycle_claim_ids:
                waves.append(
                    {
                        "kind": "cycle",
                        "index": None,
                        "claim_ids": cycle_claim_ids,
                        "detail": (
                            "These claims depend on one another and cannot be scheduled until the cycle is broken."
                        ),
                    }
                )
            if blocked_claim_ids:
                waves.append(
                    {
                        "kind": "blocked",
                        "index": None,
                        "claim_ids": blocked_claim_ids,
                        "detail": "These claims are blocked by an upstream dependency cycle.",
                    }
                )
            remaining.clear()
            break
        wave_number = len([wave for wave in waves if wave["kind"] == "wave"]) + 1
        waves.append(
            {
                "kind": "wave",
                "index": wave_number,
                "claim_ids": ready,
                "detail": "Independent claims that can run in parallel.",
            }
        )
        for claim_id in ready:
            remaining.discard(claim_id)
            for other in remaining:
                if claim_id in deps.get(other, []):
                    in_degree[other] -= 1
    wave_index_map = {
        claim_id: int(wave["index"]) for wave in waves if wave["kind"] == "wave" for claim_id in wave["claim_ids"]
    }
    cycle_ids = {claim_id for wave in waves if wave["kind"] == "cycle" for claim_id in wave["claim_ids"]}
    blocked_ids = {claim_id for wave in waves if wave["kind"] == "blocked" for claim_id in wave["claim_ids"]}
    return waves, wave_index_map, cycle_ids, blocked_ids


def _dashboard_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def build_workspace_explorer_payload(root: Path | None = None) -> dict[str, Any]:
    research_root = _workspace_root(root)
    config = load_config(_cfg.DEFAULT_ORCH_CONFIG)
    dashboard = get_dashboard_payload(root=research_root)
    dispatch_log = get_dispatch_log_payload(root=research_root)
    conn = build_db(root=research_root)
    try:
        claim_rows = conn.execute(
            f"SELECT id, status, confidence, maturity, title, file_path, file_mtime "
            f"FROM nodes WHERE {_PRIMARY_CLAIM_SQL} ORDER BY file_path"
        ).fetchall()
        claim_ids = {row["id"] for row in claim_rows}
        node_titles = {
            row["id"]: {"title": row["title"], "file": row["file_path"], "status": row["status"]}
            for row in conn.execute("SELECT id, title, file_path, status FROM nodes").fetchall()
        }
        edge_rows = conn.execute(
            "SELECT source_id, target_id, relation FROM edges WHERE relation IN ('depends_on', 'assumes') "
            "ORDER BY source_id, relation, target_id"
        ).fetchall()
        ledger_rows = conn.execute(
            "SELECT timestamp, event, node_id, details, agent FROM ledger ORDER BY timestamp, event, node_id"
        ).fetchall()
    finally:
        conn.close()

    blocked_map: dict[str, list[str]] = {}
    for item in _dashboard_items(dashboard.get("blocked")):
        blocked_map.setdefault(str(item["id"]), []).append(str(item["blocked_by"]))

    dependencies: dict[str, list[str]] = {claim_id: [] for claim_id in claim_ids}
    external_dependencies: dict[str, list[dict[str, Any]]] = {claim_id: [] for claim_id in claim_ids}
    dependents: dict[str, list[str]] = {claim_id: [] for claim_id in claim_ids}
    graph_edges: list[dict[str, str]] = []

    for edge in edge_rows:
        source_id = str(edge["source_id"])
        target_id = str(edge["target_id"])
        if source_id not in claim_ids:
            continue
        if target_id in claim_ids:
            dependencies[source_id].append(target_id)
            dependents[target_id].append(source_id)
            graph_edges.append({"source": target_id, "target": source_id, "relation": str(edge["relation"])})
        else:
            node = node_titles.get(target_id)
            external_dependencies[source_id].append(
                {
                    "id": target_id,
                    "title": (node or {}).get("title") or target_id,
                    "file": (node or {}).get("file"),
                    "status": (node or {}).get("status"),
                    "relation": str(edge["relation"]),
                }
            )

    claim_payloads: list[dict[str, Any]] = []
    claim_event_map: dict[str, list[dict[str, Any]]] = {claim_id: [] for claim_id in claim_ids}
    dispatch_by_sub_unit: dict[str, list[dict[str, Any]]] = {}
    for row in dispatch_log:
        sub_unit = row.get("sub_unit")
        if isinstance(sub_unit, str):
            dispatch_by_sub_unit.setdefault(sub_unit, []).append(row)

    for row in ledger_rows:
        node_id = row["node_id"]
        if node_id not in claim_ids:
            continue
        claim_event_map[node_id].append(
            {
                "timestamp": row["timestamp"],
                "kind": "ledger",
                "event": row["event"],
                "label": str(row["event"]).replace("_", " ").title(),
                "agent": row["agent"],
                "details": row["details"] or "",
            }
        )

    for row in claim_rows:
        file_path = str(row["file_path"])
        sub_unit = _claim_sub_unit(file_path)
        claim_dir = research_root / sub_unit
        claim_file = research_root / file_path
        state = detect_state(research_root, sub_unit, config)
        meta, excerpt = _read_claim_meta(claim_file, research_root)
        claim_id = str(row["id"])
        display_meta = _claim_display_meta(sub_unit)
        claim_dispatches = [
            {
                "timestamp": event["timestamp"],
                "kind": "dispatch",
                "event": event["action"],
                "label": f"{event['agent']} {event['action']}",
                "agent": event["agent"],
                "details": event.get("details") or "",
                "round": event.get("round"),
            }
            for event in dispatch_by_sub_unit.get(sub_unit, [])
        ]
        events = sorted(
            claim_event_map[claim_id] + claim_dispatches,
            key=lambda item: (item["timestamp"], item["label"]),
        )
        claim_payloads.append(
            {
                "id": claim_id,
                "kind": display_meta["kind"],
                "kind_label": display_meta["kind_label"],
                "number": display_meta["number"],
                "label": display_meta["label"],
                "hierarchy": display_meta["hierarchy"],
                "slug": Path(sub_unit).name,
                "title": row["title"] or _human_title(Path(sub_unit).name),
                "file": file_path,
                "sub_unit": sub_unit,
                "directory": str(claim_dir),
                "status": row["status"],
                "confidence": row["confidence"],
                "maturity": row["maturity"],
                "modified_at": _format_timestamp(row["file_mtime"]),
                "statement": excerpt,
                "falsification": get_scalar_frontmatter(
                    meta, "falsification", filepath=claim_file.relative_to(research_root).as_posix()
                ),
                "state": state,
                "depends_on": dependencies.get(claim_id, []),
                "depends_on_external": external_dependencies.get(claim_id, []),
                "dependents": dependents.get(claim_id, []),
                "blocked_by": blocked_map.get(claim_id, []),
                "steps": _claim_steps(
                    claim_dir=claim_dir,
                    claim_file=claim_file,
                    root=research_root,
                    state=state,
                    config=config,
                ),
                "transitions": _claim_transitions(
                    claim_dir=claim_dir,
                    claim_file=claim_file,
                    root=research_root,
                    state=state,
                    config=config,
                ),
                "events": events,
            }
        )

    waves, wave_index, cycle_ids, blocked_ids = _claim_waves(claim_payloads, dependencies)
    for claim in claim_payloads:
        claim["wave"] = wave_index.get(claim["id"])
        if claim["id"] in cycle_ids:
            claim["wave_kind"] = "cycle"
        elif claim["id"] in blocked_ids:
            claim["wave_kind"] = "blocked"
        else:
            claim["wave_kind"] = "wave"

    selected_claim = dashboard.get("active_claim")
    if not isinstance(selected_claim, str) or selected_claim not in {claim["sub_unit"] for claim in claim_payloads}:
        pending = _dashboard_items(dashboard.get("pending_decisions"))
        if pending:
            pending_file = pending[0].get("file")
            if isinstance(pending_file, str):
                selected_claim = _claim_sub_unit(pending_file)
    if not isinstance(selected_claim, str) and claim_payloads:
        selected_claim = claim_payloads[0]["sub_unit"]

    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "workspace_root": str(research_root),
        "workspace_label": _workspace_label(research_root),
        "dashboard": dashboard,
        "selected_claim": selected_claim,
        "graph": {
            "waves": waves,
            "edges": graph_edges,
            "cycle_claim_ids": sorted(cycle_ids),
            "blocked_claim_ids": sorted(blocked_ids),
        },
        "claims": claim_payloads,
    }


_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Principia Workspace Explorer - __WORKSPACE_LABEL__</title>
  <style>
    :root {
      --bg: #f3efe8;
      --panel: rgba(255, 251, 246, 0.92);
      --panel-strong: rgba(255, 255, 255, 0.96);
      --border: rgba(27, 39, 49, 0.14);
      --ink: #15212c;
      --muted: #5f6c77;
      --accent: #0f766e;
      --accent-soft: rgba(15, 118, 110, 0.14);
      --warn: #c27a1f;
      --warn-soft: rgba(194, 122, 31, 0.16);
      --danger: #b64633;
      --danger-soft: rgba(182, 70, 51, 0.14);
      --ok: #25745f;
      --ok-soft: rgba(37, 116, 95, 0.14);
      --shadow: 0 24px 60px rgba(33, 39, 44, 0.08);
      --radius: 24px;
      --mono: "JetBrains Mono", "Cascadia Mono", "SFMono-Regular", Consolas, monospace;
      --sans: "Segoe UI Variable", Aptos, "IBM Plex Sans", "Trebuchet MS", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: var(--sans);
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.10), transparent 34%),
        radial-gradient(circle at top right, rgba(194, 122, 31, 0.10), transparent 28%),
        linear-gradient(180deg, #f7f3eb 0%, #efe9de 100%);
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(21, 33, 44, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(21, 33, 44, 0.04) 1px, transparent 1px);
      background-size: 36px 36px;
      mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.15), transparent 72%);
    }
    .page {
      position: relative;
      padding: 24px;
      display: grid;
      gap: 18px;
    }
    .header,
    .warning-strip,
    .main-shell,
    .artifact-shell,
    .timeline-shell {
      border: 1px solid var(--border);
      background: var(--panel);
      backdrop-filter: blur(22px);
      box-shadow: var(--shadow);
      border-radius: var(--radius);
    }
    .header {
      padding: 22px 24px 20px;
      display: grid;
      gap: 18px;
    }
    .header-top {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
    }
    .eyebrow {
      font-size: 11px;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 10px;
      font-weight: 700;
    }
    .headline {
      font-size: clamp(2rem, 3vw, 3.2rem);
      line-height: 0.96;
      margin: 0;
      max-width: 9ch;
    }
    .subhead {
      margin: 10px 0 0;
      max-width: 64ch;
      color: var(--muted);
      font-size: 0.98rem;
      line-height: 1.6;
    }
    .meta-column {
      min-width: 220px;
      display: grid;
      gap: 10px;
      justify-items: end;
    }
    .stamp {
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.84);
      border: 1px solid rgba(21, 33, 44, 0.08);
      font-size: 0.78rem;
      color: var(--muted);
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
    }
    .summary-metric {
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.76);
      border: 1px solid rgba(21, 33, 44, 0.07);
      transition: transform 160ms ease, border-color 160ms ease;
    }
    .summary-metric:hover { transform: translateY(-2px); border-color: rgba(21, 33, 44, 0.16); }
    .summary-label {
      font-size: 0.76rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.14em;
      margin-bottom: 8px;
    }
    .summary-value {
      font-size: 1.8rem;
      line-height: 1;
      font-weight: 700;
    }
    .summary-detail {
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.9rem;
      line-height: 1.4;
    }
    .warning-strip {
      padding: 14px 18px;
      display: none;
      gap: 12px;
    }
    .warning-strip.active { display: grid; }
    .warning-item {
      border-left: 4px solid var(--warn);
      padding-left: 12px;
      display: grid;
      gap: 4px;
    }
    .warning-item[data-severity="warning"] { border-left-color: var(--warn); }
    .warning-item[data-severity="danger"] { border-left-color: var(--danger); }
    .warning-code {
      font-size: 0.72rem;
      color: var(--muted);
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    .main-shell {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(340px, 420px);
      min-height: 62vh;
      overflow: hidden;
    }
    .graph-shell {
      border-right: 1px solid var(--border);
      display: grid;
      grid-template-rows: auto auto 1fr;
      min-height: 0;
    }
    .section-head {
      padding: 20px 22px 14px;
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
    }
    .section-title {
      margin: 0;
      font-size: 1rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .section-detail {
      color: var(--muted);
      font-size: 0.84rem;
    }
    .toolbar {
      padding: 0 22px 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }
    .graph-hint {
      margin-left: auto;
      font-size: 0.8rem;
      color: var(--muted);
      line-height: 1.5;
    }
    .search {
      min-width: 260px;
      flex: 1 1 320px;
      padding: 12px 14px;
      border-radius: 999px;
      border: 1px solid rgba(21, 33, 44, 0.12);
      background: rgba(255, 255, 255, 0.78);
      font: inherit;
      color: var(--ink);
      outline: none;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .legend-chip,
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid rgba(21, 33, 44, 0.12);
      background: rgba(255, 255, 255, 0.78);
      font-size: 0.8rem;
      color: var(--muted);
    }
    .dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--muted);
    }
    .graph-board {
      position: relative;
      min-height: 0;
      overflow: auto;
      padding: 0 12px 18px 22px;
      cursor: grab;
      touch-action: none;
      background:
        linear-gradient(rgba(21, 33, 44, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(21, 33, 44, 0.04) 1px, transparent 1px);
      background-size: 28px 28px;
      background-position: 22px 0;
    }
    .graph-board.dragging { cursor: grabbing; }
    .graph-grid {
      position: relative;
      display: grid;
      gap: 20px;
      align-items: start;
      min-width: max-content;
      padding-right: 20px;
      padding-bottom: 28px;
    }
    .wave-column {
      width: 280px;
      display: grid;
      gap: 12px;
      align-content: start;
      padding: 14px;
      border-radius: 24px;
      border: 1px solid rgba(21, 33, 44, 0.08);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(246, 241, 234, 0.76));
    }
    .wave-column.cycle {
      border-color: rgba(194, 122, 31, 0.26);
      background: linear-gradient(180deg, rgba(255, 250, 241, 0.88), rgba(250, 239, 226, 0.82));
    }
    .wave-column.blocked {
      border-color: rgba(95, 108, 119, 0.22);
      background: linear-gradient(180deg, rgba(249, 248, 246, 0.88), rgba(239, 237, 233, 0.82));
    }
    .wave-heading {
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.84);
      border: 1px solid rgba(21, 33, 44, 0.08);
      font-size: 0.76rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--muted);
      position: sticky;
      top: 0;
      z-index: 1;
      backdrop-filter: blur(18px);
    }
    .claim-node {
      position: relative;
      width: 100%;
      padding: 14px 14px 13px;
      border-radius: 18px;
      border: 1px solid rgba(21, 33, 44, 0.10);
      background: rgba(255, 255, 255, 0.88);
      text-align: left;
      color: inherit;
      cursor: pointer;
      transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease, background 180ms ease;
    }
    .claim-node:hover {
      transform: translateY(-2px);
      box-shadow: 0 16px 28px rgba(21, 33, 44, 0.10);
      border-color: rgba(21, 33, 44, 0.20);
    }
    .claim-node.selected {
      border-color: rgba(15, 118, 110, 0.48);
      box-shadow: 0 20px 34px rgba(15, 118, 110, 0.14);
      background: rgba(235, 250, 247, 0.92);
    }
    .claim-node.linked { background: rgba(15, 118, 110, 0.08); }
    .claim-node.dimmed {
      opacity: 0.28;
      transform: none;
      box-shadow: none;
    }
    .claim-node.hidden { display: none; }
    .claim-kicker {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      margin-bottom: 8px;
    }
    .claim-number {
      font-size: 0.76rem;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 0;
    }
    .claim-roundup {
      font-size: 0.72rem;
      color: var(--muted);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .claim-title {
      font-size: 1rem;
      font-weight: 700;
      line-height: 1.25;
      margin-bottom: 10px;
    }
    .claim-node .claim-summary {
      font-size: 0.88rem;
      color: var(--muted);
      line-height: 1.45;
    }
    .claim-badges {
      margin-top: 12px;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .claim-badge {
      display: inline-flex;
      align-items: center;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(21, 33, 44, 0.05);
      font-size: 0.7rem;
      color: var(--muted);
      letter-spacing: 0.04em;
    }
    .claim-node.selected .claim-badge,
    .claim-node.linked .claim-badge {
      background: rgba(15, 118, 110, 0.10);
      color: var(--ink);
    }
    .claim-node.cycle-node {
      border-style: dashed;
      border-color: rgba(194, 122, 31, 0.32);
      background: rgba(255, 250, 241, 0.92);
    }
    .claim-node.blocked-node {
      border-style: dashed;
      border-color: rgba(95, 108, 119, 0.22);
      background: rgba(247, 246, 243, 0.92);
    }
    .status-tag {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      margin-top: 12px;
      font-size: 0.76rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .status-tag .dot { background: var(--muted); }
    .status-proven .dot { background: var(--ok); }
    .status-disproven .dot { background: var(--danger); }
    .status-partial .dot,
    .status-weakened .dot,
    .status-inconclusive .dot { background: var(--warn); }
    .status-active .dot,
    .status-pending .dot { background: var(--accent); }
    .graph-links {
      position: absolute;
      inset: 0;
      pointer-events: none;
      overflow: visible;
    }
    .graph-link {
      fill: none;
      stroke: rgba(21, 33, 44, 0.12);
      stroke-width: 2;
      transition: stroke 180ms ease, opacity 180ms ease;
    }
    .graph-link.relation-assumes { stroke-dasharray: 7 6; }
    .graph-link.active {
      stroke: rgba(15, 118, 110, 0.65);
      opacity: 1;
    }
    .graph-link.muted { opacity: 0.18; }
    .edge-label {
      fill: rgba(21, 33, 44, 0.62);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      paint-order: stroke;
      stroke: rgba(255, 251, 246, 0.96);
      stroke-width: 4px;
      stroke-linejoin: round;
    }
    .inspector {
      display: grid;
      grid-template-rows: auto auto auto 1fr;
      min-height: 0;
    }
    .inspector-head {
      padding: 22px 22px 18px;
      border-bottom: 1px solid var(--border);
      display: grid;
      gap: 14px;
      background: var(--panel-strong);
    }
    .inspector-title {
      margin: 0;
      font-size: 1.45rem;
      line-height: 1.08;
    }
    .inspector-summary {
      color: var(--muted);
      line-height: 1.6;
      font-size: 0.94rem;
    }
    .inspector-meta,
    .dependency-strip {
      padding: 18px 22px;
      display: grid;
      gap: 12px;
      border-bottom: 1px solid var(--border);
    }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px 12px;
    }
    .meta-item {
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.72);
      border: 1px solid rgba(21, 33, 44, 0.07);
    }
    .meta-item label {
      display: block;
      font-size: 0.7rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 7px;
    }
    .meta-item div {
      font-size: 0.88rem;
      line-height: 1.45;
      word-break: break-word;
    }
    .dependency-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .dependency-row button,
    .dependency-row .pill {
      border: 1px solid rgba(21, 33, 44, 0.10);
      background: rgba(255, 255, 255, 0.78);
      border-radius: 999px;
      padding: 8px 12px;
      font: inherit;
      color: var(--ink);
      cursor: pointer;
    }
    .dependency-row button:hover { border-color: rgba(15, 118, 110, 0.36); }
    .step-shell {
      padding: 18px 22px 22px;
      overflow: auto;
      display: grid;
      gap: 16px;
      align-content: start;
    }
    .step-row {
      position: relative;
      padding-left: 24px;
      display: grid;
      gap: 6px;
    }
    .step-row::before {
      content: "";
      position: absolute;
      left: 7px;
      top: 4px;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: rgba(21, 33, 44, 0.18);
    }
    .step-row::after {
      content: "";
      position: absolute;
      left: 11px;
      top: 20px;
      bottom: -18px;
      width: 2px;
      background: rgba(21, 33, 44, 0.10);
    }
    .step-row:last-child::after { display: none; }
    .step-row[data-status="complete"]::before { background: var(--ok); }
    .step-row[data-status="waiting_result"]::before { background: var(--warn); }
    .step-row[data-status="ready_to_send"]::before,
    .step-row[data-status="queued"]::before { background: var(--accent); }
    .step-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      font-size: 0.9rem;
    }
    .step-title {
      font-weight: 700;
      line-height: 1.25;
    }
    .step-state {
      font-size: 0.74rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .step-summary,
    .step-detail,
    .step-files {
      color: var(--muted);
      font-size: 0.84rem;
      line-height: 1.5;
    }
    .step-files {
      display: grid;
      gap: 4px;
      font-family: var(--mono);
      font-size: 0.74rem;
      color: #54606a;
    }
    .transition-shell {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
    }
    .transition-list {
      padding: 0 22px 22px;
      display: grid;
      gap: 12px;
    }
    .transition-card {
      border: 1px solid rgba(21, 33, 44, 0.10);
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.76);
      padding: 14px 16px;
      display: grid;
      gap: 10px;
    }
    .transition-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }
    .transition-route {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      line-height: 1.4;
      font-weight: 700;
    }
    .transition-arrow {
      color: var(--muted);
      font-weight: 400;
    }
    .transition-phase {
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .transition-status {
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      border: 1px solid rgba(21, 33, 44, 0.12);
      color: var(--muted);
      white-space: nowrap;
    }
    .transition-status[data-status="complete"] {
      background: var(--ok-soft);
      color: var(--ok);
      border-color: rgba(37, 116, 95, 0.22);
    }
    .transition-status[data-status="current"] {
      background: var(--accent-soft);
      color: var(--accent);
      border-color: rgba(15, 118, 110, 0.20);
    }
    .transition-status[data-status="ready_to_send"] {
      background: var(--accent-soft);
      color: var(--accent);
      border-color: rgba(15, 118, 110, 0.20);
    }
    .transition-status[data-status="waiting_result"] {
      background: var(--warn-soft);
      color: var(--warn);
      border-color: rgba(194, 122, 31, 0.24);
    }
    .transition-status[data-status="pending"] {
      background: rgba(21, 33, 44, 0.04);
    }
    .transition-reason,
    .transition-detail {
      color: var(--muted);
      font-size: 0.9rem;
      line-height: 1.6;
    }
    .transition-evidence {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .transition-evidence .pill {
      font-family: var(--mono);
      font-size: 0.72rem;
      color: #52606b;
    }
    .artifact-shell {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
    }
    .artifact-list {
      padding: 0 22px 22px;
      display: grid;
      gap: 12px;
    }
    .artifact-step {
      border: 1px solid rgba(21, 33, 44, 0.10);
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.74);
      overflow: hidden;
    }
    .artifact-step summary {
      list-style: none;
      cursor: pointer;
      padding: 14px 16px;
    }
    .artifact-step summary::-webkit-details-marker { display: none; }
    .artifact-step-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }
    .artifact-step-title {
      font-size: 0.95rem;
      font-weight: 700;
      line-height: 1.3;
    }
    .artifact-step-state {
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      white-space: nowrap;
    }
    .artifact-step-meta,
    .artifact-step-caption {
      color: var(--muted);
      font-size: 0.84rem;
      line-height: 1.5;
      margin-top: 6px;
    }
    .artifact-panels {
      padding: 0 16px 16px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .artifact-card {
      min-width: 0;
      border: 1px solid rgba(21, 33, 44, 0.08);
      border-radius: 16px;
      background: rgba(252, 249, 244, 0.92);
      overflow: hidden;
      display: grid;
      grid-template-rows: auto auto 1fr;
    }
    .artifact-card.is-empty {
      opacity: 0.7;
      background: rgba(255, 255, 255, 0.62);
    }
    .artifact-card-head {
      padding: 12px 12px 10px;
      display: grid;
      gap: 6px;
      border-bottom: 1px solid rgba(21, 33, 44, 0.08);
    }
    .artifact-kind {
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .artifact-path,
    .artifact-modified {
      font-family: var(--mono);
      font-size: 0.72rem;
      color: #52606b;
      line-height: 1.5;
      word-break: break-word;
    }
    .artifact-code {
      margin: 0;
      padding: 12px;
      font-family: var(--mono);
      font-size: 0.76rem;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
      overflow: auto;
      max-height: 360px;
      color: var(--ink);
      background: rgba(255, 255, 255, 0.72);
    }
    .artifact-empty {
      padding: 12px;
      color: var(--muted);
      font-size: 0.84rem;
      line-height: 1.5;
    }
    .timeline-shell {
      min-height: 220px;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
    }
    .timeline-list {
      padding: 6px 22px 24px;
      display: grid;
      gap: 10px;
    }
    .timeline-item {
      display: grid;
      grid-template-columns: 160px 120px 1fr;
      gap: 14px;
      align-items: start;
      padding: 10px 0;
      border-bottom: 1px dashed rgba(21, 33, 44, 0.10);
      font-size: 0.88rem;
    }
    .timeline-item:last-child { border-bottom: none; }
    .timeline-stamp {
      font-family: var(--mono);
      color: #52606b;
      font-size: 0.74rem;
      line-height: 1.4;
    }
    .timeline-kind {
      color: var(--muted);
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-size: 0.72rem;
      padding-top: 2px;
    }
    .timeline-main {
      display: grid;
      gap: 4px;
    }
    .timeline-label { font-weight: 700; }
    .timeline-details { color: var(--muted); line-height: 1.5; }
    .empty {
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.6;
      padding: 0 22px 22px;
    }
    @media (max-width: 1180px) {
      .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .main-shell { grid-template-columns: 1fr; }
      .graph-shell { border-right: none; border-bottom: 1px solid var(--border); }
      .artifact-panels { grid-template-columns: 1fr; }
    }
    @media (max-width: 720px) {
      .page { padding: 14px; }
      .header-top { flex-direction: column; }
      .meta-column { justify-items: start; }
      .summary-grid { grid-template-columns: 1fr; }
      .toolbar { padding-right: 18px; }
      .graph-hint { margin-left: 0; }
      .graph-board { padding-right: 12px; }
      .timeline-item { grid-template-columns: 1fr; gap: 4px; }
      .meta-grid { grid-template-columns: 1fr; }
      .transition-top { flex-direction: column; }
      .artifact-step-head { flex-direction: column; }
    }
  </style>
</head>
<body>
  <div class="page">
    <section class="header">
      <div class="header-top">
        <div>
          <div class="eyebrow">Principia Workspace Explorer</div>
          <h1 class="headline">__WORKSPACE_LABEL__</h1>
          <p class="subhead" id="breadcrumb"></p>
        </div>
        <div class="meta-column">
          <div class="stamp" id="workspace-root"></div>
          <div class="stamp" id="generated-at"></div>
        </div>
      </div>
      <div class="summary-grid" id="summary-grid"></div>
    </section>

    <section class="warning-strip" id="warning-strip"></section>

    <section class="main-shell">
      <div class="graph-shell">
        <div class="section-head">
          <div>
            <h2 class="section-title">Claim Graph</h2>
            <div class="section-detail">Dependency waves and claim-state overview.</div>
          </div>
          <div class="section-detail" id="graph-detail"></div>
        </div>
        <div class="toolbar">
          <input
            class="search"
            id="claim-search"
            type="search"
            placeholder="Filter by claim number, title, status, or id"
          >
          <div class="legend">
            <div class="legend-chip"><span class="dot" style="background: var(--ok)"></span> Proven</div>
            <div class="legend-chip"><span class="dot" style="background: var(--warn)"></span> Partial / Weakened</div>
            <div class="legend-chip"><span class="dot" style="background: var(--danger)"></span> Disproven</div>
            <div class="legend-chip"><span class="dot" style="background: var(--accent)"></span> Pending / Active</div>
          </div>
          <div class="graph-hint">
            Drag to pan. Click a claim to inspect it. Arrows run from prerequisite to dependent claim.
          </div>
        </div>
        <div class="graph-board" id="graph-board">
          <svg class="graph-links" id="graph-links"></svg>
          <div class="graph-grid" id="graph-grid"></div>
        </div>
      </div>

      <aside class="inspector">
        <div class="inspector-head">
          <div class="eyebrow" id="inspector-kicker"></div>
          <div>
            <h2 class="inspector-title" id="inspector-title"></h2>
            <div class="inspector-summary" id="inspector-summary"></div>
          </div>
        </div>
        <div class="inspector-meta">
          <div class="meta-grid" id="meta-grid"></div>
        </div>
        <div class="dependency-strip">
          <div>
            <div class="section-detail">Depends on</div>
            <div class="dependency-row" id="depends-row"></div>
          </div>
          <div>
            <div class="section-detail">Dependents</div>
            <div class="dependency-row" id="dependents-row"></div>
          </div>
          <div>
            <div class="section-detail">External blockers</div>
            <div class="dependency-row" id="external-row"></div>
          </div>
        </div>
        <div class="step-shell" id="step-shell"></div>
      </aside>
    </section>

    <section class="transition-shell">
      <div class="section-head">
        <div>
          <h2 class="section-title">State Transitions</h2>
          <div class="section-detail">
            Why the selected claim moved from one workflow state to the next.
          </div>
        </div>
        <div class="section-detail" id="transition-detail"></div>
      </div>
      <div class="transition-list" id="transition-list"></div>
    </section>

    <section class="artifact-shell">
      <div class="section-head">
        <div>
          <h2 class="section-title">Agent Artifacts</h2>
          <div class="section-detail">
            Full packet, prompt, and response detail for every recorded agent step in the selected claim.
          </div>
        </div>
        <div class="section-detail" id="artifact-detail"></div>
      </div>
      <div class="artifact-list" id="artifact-list"></div>
    </section>

    <section class="timeline-shell">
      <div class="section-head">
        <div>
          <h2 class="section-title">Event Timeline</h2>
          <div class="section-detail">Dispatch and verdict bookkeeping for the selected claim.</div>
        </div>
        <div class="section-detail" id="timeline-detail"></div>
      </div>
      <div class="timeline-list" id="timeline-list"></div>
    </section>
  </div>

  <script id="workspace-data" type="application/json">__DATA__</script>
  <script>
    const data = JSON.parse(document.getElementById("workspace-data").textContent);
    const claimById = new Map(data.claims.map((claim) => [claim.id, claim]));
    const claimBySubUnit = new Map(data.claims.map((claim) => [claim.sub_unit, claim]));
    const graphBoard = document.getElementById("graph-board");
    const graphGrid = document.getElementById("graph-grid");
    const graphLinks = document.getElementById("graph-links");
    const searchInput = document.getElementById("claim-search");
    const transitionList = document.getElementById("transition-list");
    const artifactList = document.getElementById("artifact-list");
    const state = {
      selectedId: claimBySubUnit.get(data.selected_claim)?.id || data.claims[0]?.id || null,
      query: "",
      hasRendered: false,
      graphSnapshot: null
    };
    const dragState = {
      active: false,
      pointerId: null,
      startX: 0,
      startY: 0,
      startScrollLeft: 0,
      startScrollTop: 0,
      moved: false,
      suppressClick: false
    };
    let linkFrame = 0;
    let searchTimer = 0;

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function titleCase(value) {
      return String(value ?? "")
        .replaceAll("_", " ")
        .replace(/\\b\\w/g, (char) => char.toUpperCase());
    }

    function statusClass(status) {
      return `status-${String(status || "pending").toLowerCase()}`;
    }

    function statusLabel(status) {
      return titleCase(status || "pending");
    }

    function scheduleDrawLinks() {
      if (linkFrame) {
        return;
      }
      linkFrame = window.requestAnimationFrame(() => {
        linkFrame = 0;
        drawLinks();
      });
    }

    function centerClaimNode(claimId, behavior = "smooth") {
      if (!claimId) {
        return;
      }
      const snapshot = state.graphSnapshot;
      const node = snapshot?.nodeById?.get(claimId)
        || graphGrid.querySelector(`[data-claim-id="${CSS.escape(claimId)}"]`);
      if (!node) {
        return;
      }
      const left = Math.max(0, node.offsetLeft - (graphBoard.clientWidth - node.offsetWidth) / 2);
      const top = Math.max(0, node.offsetTop - (graphBoard.clientHeight - node.offsetHeight) / 2);
      graphBoard.scrollTo({ left, top, behavior });
      scheduleDrawLinks();
    }

    function selectClaim(claimId, { center = true } = {}) {
      if (!claimById.has(claimId)) {
        return;
      }
      state.selectedId = claimId;
      renderSelection({ centerSelected: center });
    }

    function renderHeader() {
      document.getElementById("breadcrumb").textContent =
        data.dashboard.breadcrumb || "Live claim graph and state explorer.";
      document.getElementById("workspace-root").textContent = data.workspace_root;
      document.getElementById("generated-at").textContent = `Generated ${data.generated_at}`;
      const summaryGrid = document.getElementById("summary-grid");
      const dashboardClaims = data.dashboard.claims || {};
      const warningCount = (data.dashboard.warnings || []).reduce(
        (sum, warning) => sum + Number(warning.count || 0),
        0
      );
      const metrics = [
        {
          label: "Phase",
          value: titleCase(data.dashboard.phase || "unknown"),
          detail: `Action: ${titleCase(data.dashboard.action || "unknown")}`
        },
        {
          label: "Claims",
          value: data.claims.length,
          detail: `${dashboardClaims.proven || 0} proven / ${dashboardClaims.disproven || 0} disproven`
        },
        {
          label: "Pending Decisions",
          value: (data.dashboard.pending_decisions || []).length,
          detail: `${dashboardClaims.partial || 0} partial / ${dashboardClaims.inconclusive || 0} inconclusive`
        },
        {
          label: "Warnings",
          value: warningCount,
          detail: warningCount ? "North-star or dispatch drift needs review." : "No live workspace warnings."
        },
        {
          label: "Autonomy",
          value: titleCase(
            data.dashboard.preferences?.workflow_autonomy ||
            data.dashboard.autonomy?.mode ||
            "unknown"
          ),
          detail: `Active claim: ${data.dashboard.active_claim || "none"}`
        }
      ];
      summaryGrid.innerHTML = metrics.map((metric) => `
        <article class="summary-metric">
          <div class="summary-label">${escapeHtml(metric.label)}</div>
          <div class="summary-value">${escapeHtml(metric.value)}</div>
          <div class="summary-detail">${escapeHtml(metric.detail)}</div>
        </article>
      `).join("");

      const warningStrip = document.getElementById("warning-strip");
      const warnings = data.dashboard.warnings || [];
      warningStrip.classList.toggle("active", warnings.length > 0);
      warningStrip.innerHTML = warnings.map((warning) => `
        <div class="warning-item" data-severity="${escapeHtml(warning.severity || "warning")}">
          <div class="warning-code">${escapeHtml(warning.code || "warning")}</div>
          <div>${escapeHtml(warning.message || "")}</div>
        </div>
      `).join("");
    }

    function visibleClaimIds() {
      if (!state.query) {
        return new Set(data.claims.map((claim) => claim.id));
      }
      const needle = state.query.toLowerCase();
      return new Set(
        data.claims
          .filter((claim) => {
            const haystack = [
              claim.id,
              claim.label,
              claim.kind_label,
              claim.hierarchy,
              claim.title,
              claim.slug,
              claim.status,
              claim.confidence,
              claim.statement,
              claim.state?.action,
              claim.state?.phase
            ]
              .filter(Boolean)
              .join(" ")
              .toLowerCase();
            return haystack.includes(needle);
          })
          .map((claim) => claim.id)
      );
    }

    function claimsForWave(wave) {
      return (wave.claim_ids || []).map((claimId) => claimById.get(claimId)).filter(Boolean);
    }

    function selectedClaimForVisibleIds(visibleIds) {
      if (state.selectedId && visibleIds.has(state.selectedId)) {
        return claimById.get(state.selectedId) || null;
      }
      if (!visibleIds.size) {
        return null;
      }
      state.selectedId = Array.from(visibleIds)[0];
      return claimById.get(state.selectedId) || null;
    }

    function buildGraphSnapshot() {
      const visibleIds = visibleClaimIds();
      const selectedClaim = selectedClaimForVisibleIds(visibleIds);
      return {
        visibleIds,
        selectedClaim,
        waves: data.graph.waves
          .map((wave) => ({ ...wave, claims: claimsForWave(wave).filter((claim) => visibleIds.has(claim.id)) }))
          .filter((wave) => wave.claims.length),
        edges: data.graph.edges.filter(
          (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)
        ),
        cycleIds: (data.graph.cycle_claim_ids || []).filter((claimId) => visibleIds.has(claimId)),
        blockedIds: (data.graph.blocked_claim_ids || []).filter((claimId) => visibleIds.has(claimId)),
        nodeById: new Map()
      };
    }

    function currentGraphSnapshot() {
      if (!state.graphSnapshot) {
        state.graphSnapshot = buildGraphSnapshot();
      }
      return state.graphSnapshot;
    }

    function claimPlacement(claim) {
      if (!claim) {
        return "";
      }
      if (claim.hierarchy) {
        return claim.hierarchy;
      }
      if (claim.wave_kind === "cycle") {
        return "Dependency cycle";
      }
      if (claim.wave_kind === "blocked") {
        return "Blocked by cyclic dependency";
      }
      if (claim.wave) {
        return `Wave ${claim.wave}`;
      }
      return "Unscheduled";
    }

    function linkedIds(selectedClaim) {
      if (!selectedClaim) {
        return new Set();
      }
      return new Set([
        selectedClaim.id,
        ...(selectedClaim.depends_on || []),
        ...(selectedClaim.dependents || [])
      ]);
    }

    function renderGraphDetail(snapshot, selectedClaim) {
      const visibleCount = snapshot.visibleIds.size;
      const parts = [
        `${visibleCount} visible / ${data.claims.length} claim(s)`,
        `${snapshot.edges.length} dependency link(s)`
      ];
      const cycleCount = snapshot.cycleIds.length;
      if (cycleCount) {
        parts.push(`${cycleCount} claim(s) in dependency cycles`);
      }
      const blockedCount = snapshot.blockedIds.length;
      if (blockedCount) {
        parts.push(`${blockedCount} claim(s) blocked by cycles`);
      }
      if (selectedClaim) {
        const upstreamTotal = (selectedClaim.depends_on || []).length;
        const upstreamVisible = (selectedClaim.depends_on || []).filter((id) => snapshot.visibleIds.has(id)).length;
        const downstreamTotal = (selectedClaim.dependents || []).length;
        const downstreamVisible = (selectedClaim.dependents || []).filter((id) => snapshot.visibleIds.has(id)).length;
        parts.push(
          upstreamVisible === upstreamTotal
            ? `${upstreamTotal} upstream`
            : `${upstreamVisible} / ${upstreamTotal} upstream visible`
        );
        parts.push(
          downstreamVisible === downstreamTotal
            ? `${downstreamTotal} downstream`
            : `${downstreamVisible} / ${downstreamTotal} downstream visible`
        );
      }
      document.getElementById("graph-detail").textContent = parts.join(" / ");
    }

    function renderGraph() {
      const snapshot = buildGraphSnapshot();
      state.graphSnapshot = snapshot;

      if (!snapshot.visibleIds.size) {
        graphGrid.style.gridTemplateColumns = "minmax(280px, 360px)";
        graphGrid.innerHTML = `<div class="empty">No claims match the current filter.</div>`;
        graphLinks.innerHTML = "";
        return snapshot;
      }

      graphGrid.style.gridTemplateColumns = `repeat(${snapshot.waves.length || 1}, 280px)`;
      graphGrid.innerHTML = snapshot.waves.map((wave) => {
        const nodes = wave.claims
          .map((claim) => {
            const placement = claimPlacement(claim);
            const classes = [
              "claim-node",
              statusClass(claim.status),
              claim.wave_kind === "cycle" ? "cycle-node" : "",
              claim.wave_kind === "blocked" ? "blocked-node" : ""
            ].filter(Boolean).join(" ");
            const badges = [
              `Upstream ${(claim.depends_on || []).length}`,
              `Downstream ${(claim.dependents || []).length}`,
              `Phase ${titleCase(claim.state.phase || "unknown")}`
            ];
            if (claim.wave_kind === "cycle") {
              badges.push("Dependency Cycle");
            }
            if (claim.wave_kind === "blocked") {
              badges.push("Blocked by Cycle");
            }
            return `
              <button class="${classes}" data-claim-id="${escapeHtml(claim.id)}">
                <div class="claim-kicker">
                  <div class="claim-number">${escapeHtml(claim.label || claim.id)}</div>
                  <div class="claim-roundup">${escapeHtml(placement)}</div>
                </div>
                <div class="claim-title">${escapeHtml(claim.title)}</div>
                <div class="claim-summary">${escapeHtml(claim.statement || "No statement excerpt available.")}</div>
                <div class="claim-badges">
                  ${badges.map((badge) => `<span class="claim-badge">${escapeHtml(badge)}</span>`).join("")}
                </div>
                <div class="status-tag ${statusClass(claim.status)}">
                  <span class="dot"></span>${escapeHtml(statusLabel(claim.status))}
                </div>
              </button>
            `;
          })
          .join("");
        const heading = wave.kind === "cycle"
          ? `Dependency cycle - ${wave.claims.length} claim(s)`
          : wave.kind === "blocked"
            ? `Blocked by cycle - ${wave.claims.length} claim(s)`
          : `Wave ${wave.index} - ${wave.claims.length} claim(s)`;
        return `
          <section class="wave-column ${escapeHtml(wave.kind || "wave")}">
            <div class="wave-heading">${escapeHtml(heading)}</div>
            ${nodes}
          </section>
        `;
      }).join("");

      snapshot.nodeById = new Map();
      graphGrid.querySelectorAll(".claim-node").forEach((button) => {
        snapshot.nodeById.set(button.getAttribute("data-claim-id"), button);
        button.addEventListener("click", () => {
          if (dragState.suppressClick) {
            return;
          }
          selectClaim(button.getAttribute("data-claim-id"));
        });
      });
      return snapshot;
    }

    function drawLinks() {
      const snapshot = currentGraphSnapshot();
      if (!snapshot.nodeById.size || !snapshot.edges.length) {
        graphLinks.innerHTML = "";
        return;
      }
      const boardRect = graphBoard.getBoundingClientRect();
      graphLinks.setAttribute("width", String(graphBoard.scrollWidth));
      graphLinks.setAttribute("height", String(graphBoard.scrollHeight));
      graphLinks.setAttribute("viewBox", `0 0 ${graphBoard.scrollWidth} ${graphBoard.scrollHeight}`);
      const selectedClaim = snapshot.selectedClaim || null;
      const related = linkedIds(selectedClaim);
      const scrollLeft = graphBoard.scrollLeft;
      const scrollTop = graphBoard.scrollTop;
      const positions = new Map();
      snapshot.nodeById.forEach((node, claimId) => {
        const rect = node.getBoundingClientRect();
        positions.set(claimId, {
          right: rect.right - boardRect.left + scrollLeft,
          left: rect.left - boardRect.left + scrollLeft,
          centerY: rect.top - boardRect.top + scrollTop + rect.height / 2
        });
      });
      const defs = `
        <defs>
          <marker id="graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(21, 33, 44, 0.18)"></path>
          </marker>
          <marker
            id="graph-arrow-active"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(15, 118, 110, 0.65)"></path>
          </marker>
        </defs>
      `;
      const paths = [];
      const labels = [];
      for (const edge of snapshot.edges) {
        const source = positions.get(edge.source);
        const target = positions.get(edge.target);
        if (!source || !target) {
          continue;
        }
        const startX = source.right;
        const startY = source.centerY;
        const endX = target.left;
        const endY = target.centerY;
        const control = Math.max(72, (endX - startX) * 0.42);
        const d = `M ${startX} ${startY} C ${startX + control} ${startY}, ${endX - control} ${endY}, ${endX} ${endY}`;
        const relation = String(edge.relation || "depends_on");
        const active = selectedClaim && related.has(edge.source) && related.has(edge.target);
        const classes = [
          "graph-link",
          `relation-${relation}`,
          active ? "active" : "",
          selectedClaim && !active ? "muted" : ""
        ].filter(Boolean).join(" ");
        const marker = active ? "url(#graph-arrow-active)" : "url(#graph-arrow)";
        paths.push(`<path class="${classes}" marker-end="${marker}" d="${d}"></path>`);
        if (selectedClaim && active) {
          const midX = startX + (endX - startX) / 2;
          const midY = startY + (endY - startY) / 2 - 10;
          const label = escapeHtml(titleCase(relation));
          labels.push(
            `<text class="edge-label" x="${midX}" y="${midY}" text-anchor="middle">${label}</text>`
          );
        }
      }
      graphLinks.innerHTML = defs + paths.join("") + labels.join("");
    }

    function applyGraphSelection(snapshot, selectedClaim) {
      const related = linkedIds(selectedClaim);
      snapshot.nodeById.forEach((node, claimId) => {
        const isSelected = selectedClaim && selectedClaim.id === claimId;
        const isRelated = selectedClaim && related.has(claimId);
        node.classList.toggle("selected", Boolean(isSelected));
        node.classList.toggle("linked", Boolean(selectedClaim && !isSelected && isRelated));
        node.classList.toggle("dimmed", Boolean(selectedClaim && !isSelected && !isRelated));
      });
      renderGraphDetail(snapshot, selectedClaim);
      scheduleDrawLinks();
    }

    function pillButton(claimId) {
      const claim = claimById.get(claimId);
      if (!claim) {
        return `<span class="pill">${escapeHtml(claimId)}</span>`;
      }
      return `
        <button type="button" data-jump="${escapeHtml(claim.id)}">
          ${escapeHtml(claim.label || claim.id)} - ${escapeHtml(claim.title)}
        </button>
      `.trim();
    }

    function attachJumpHandlers() {
      document.querySelectorAll("[data-jump]").forEach((button) => {
        button.addEventListener("click", () => {
          selectClaim(button.getAttribute("data-jump"));
        });
      });
    }

    function artifactKindsForStep(step) {
      if (step.agent === "claim" || step.agent === "reviewer") {
        return ["result"];
      }
      return ["packet", "prompt", "result"];
    }

    function artifactTitle(kind, step) {
      if (kind === "packet") {
        return "Dispatch Packet";
      }
      if (kind === "prompt") {
        return "Prompt";
      }
      if (step.agent === "claim") {
        return "Claim Source";
      }
      if (step.agent === "arbiter") {
        return "Verdict";
      }
      if (step.agent === "reviewer") {
        return "Record Marker";
      }
      return "Response";
    }

    function artifactEmpty(kind, step) {
      if (kind === "packet") {
        return "No dispatch packet has been written for this step yet.";
      }
      if (kind === "prompt") {
        return "No prompt artifact has been written for this step yet.";
      }
      if (step.agent === "reviewer") {
        return "Post-verdict recording has not completed yet.";
      }
      return "No response artifact is recorded for this step yet.";
    }

    function renderArtifactCard(kind, artifact, step) {
      const title = artifactTitle(kind, step);
      if (!artifact) {
        return `
          <article class="artifact-card is-empty">
            <div class="artifact-card-head">
              <div class="artifact-kind">${escapeHtml(title)}</div>
            </div>
            <div class="artifact-empty">${escapeHtml(artifactEmpty(kind, step))}</div>
          </article>
        `;
      }
      return `
        <article class="artifact-card">
          <div class="artifact-card-head">
            <div class="artifact-kind">${escapeHtml(title)}</div>
            <div class="artifact-path">${escapeHtml(artifact.path || "")}</div>
            <div class="artifact-modified">
              ${escapeHtml(artifact.modified_at || "Unknown modified time")}
              / ${escapeHtml(artifact.line_count || 0)} line(s)
            </div>
          </div>
          <pre class="artifact-code"><code>${escapeHtml(artifact.content || "")}</code></pre>
        </article>
      `;
    }

    function renderTransitions(claim) {
      const transitions = claim.transitions || [];
      document.getElementById("transition-detail").textContent =
        `${transitions.length} transition(s) / current action ${titleCase(claim.state.action || "unknown")}`;
      if (!transitions.length) {
        transitionList.innerHTML = `<div class="empty">No state transitions are available for this claim.</div>`;
        return;
      }
      transitionList.innerHTML = transitions.map((transition, index) => {
        const evidence = (transition.evidence || [])
          .map((item) => `<span class="pill">${escapeHtml(item)}</span>`)
          .join("");
        return `
          <article class="transition-card">
            <div class="transition-top">
              <div>
                <div class="transition-phase">
                  ${escapeHtml(`Step ${index + 1} / ${titleCase(transition.phase || "unknown")}`)}
                </div>
                <div class="transition-route">
                  <span>${escapeHtml(transition.from || "Unknown")}</span>
                  <span class="transition-arrow">-></span>
                  <span>${escapeHtml(transition.to || "Unknown")}</span>
                </div>
              </div>
              <div class="transition-status" data-status="${escapeHtml(transition.status || "pending")}">
                ${escapeHtml(statusLabel(transition.status || "pending"))}
              </div>
            </div>
            <div class="transition-reason">${escapeHtml(transition.reason || "")}</div>
            ${transition.detail ? `<div class="transition-detail">${escapeHtml(transition.detail)}</div>` : ""}
            ${evidence ? `<div class="transition-evidence">${evidence}</div>` : ""}
          </article>
        `;
      }).join("");
    }

    function renderArtifacts(claim) {
      const totalArtifacts = claim.steps.reduce(
        (sum, step) => sum + Number(step.artifact_count || 0),
        0
      );
      document.getElementById("artifact-detail").textContent =
        `${totalArtifacts} artifact(s) across ${claim.steps.length} step(s)`;
      artifactList.innerHTML = claim.steps.map((step) => {
        const kinds = artifactKindsForStep(step);
        const panels = kinds
          .map((kind) => renderArtifactCard(kind, step.artifacts?.[kind], step))
          .join("");
        const meta = [
          titleCase(step.phase || "unknown"),
          statusLabel(step.status),
          step.modified_at || "No files yet"
        ].filter(Boolean).join(" / ");
        const caption = [step.detail, step.summary].filter(Boolean).join(" ");
        const open = step.artifact_count && step.status !== "pending" ? " open" : "";
        return `
          <details class="artifact-step"${open}>
            <summary>
              <div class="artifact-step-head">
                <div class="artifact-step-title">${escapeHtml(step.label)}</div>
                <div class="artifact-step-state">${escapeHtml(statusLabel(step.status))}</div>
              </div>
              <div class="artifact-step-meta">${escapeHtml(meta)}</div>
              ${caption ? `<div class="artifact-step-caption">${escapeHtml(caption)}</div>` : ""}
            </summary>
            <div class="artifact-panels">${panels}</div>
          </details>
        `;
      }).join("");
    }

    function renderEmptyInspector(message) {
      document.getElementById("inspector-kicker").textContent = "No selected claim";
      document.getElementById("inspector-title").textContent = "No visible claim";
      document.getElementById("inspector-summary").textContent = message;
      document.getElementById("meta-grid").innerHTML = "";
      document.getElementById("depends-row").innerHTML = `<span class="pill">${escapeHtml(message)}</span>`;
      document.getElementById("dependents-row").innerHTML = `<span class="pill">${escapeHtml(message)}</span>`;
      document.getElementById("external-row").innerHTML = `<span class="pill">${escapeHtml(message)}</span>`;
      document.getElementById("step-shell").innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
      document.getElementById("transition-detail").textContent = "0 transition(s)";
      transitionList.innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
      document.getElementById("artifact-detail").textContent = "0 artifact(s) across 0 step(s)";
      artifactList.innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
      document.getElementById("timeline-detail").textContent = "0 event(s)";
      document.getElementById("timeline-list").innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
    }

    function renderInspector(selectedClaim = null) {
      const claim = selectedClaim || claimById.get(state.selectedId) || data.claims[0];
      if (!claim) {
        renderEmptyInspector("No claims are available in this workspace yet.");
        return;
      }
      document.getElementById("inspector-kicker").textContent =
        [claim.label || claim.id, claimPlacement(claim)].filter(Boolean).join(" - ");
      document.getElementById("inspector-title").textContent = claim.title;
      document.getElementById("inspector-summary").textContent =
        claim.statement || "No claim summary available.";
      const metaItems = [
        ["Kind", claim.kind_label || "Claim"],
        ["Status", statusLabel(claim.status)],
        ["Confidence", claim.confidence || "n/a"],
        ["Current phase", titleCase(claim.state.phase || "unknown")],
        ["Current action", titleCase(claim.state.action || "unknown")],
        ["Placement", claimPlacement(claim)],
        ["Upstream", (claim.depends_on || []).length],
        ["Downstream", (claim.dependents || []).length],
        ["File", claim.file],
        ["Falsification", claim.falsification || "No falsification criterion recorded."]
      ];
      document.getElementById("meta-grid").innerHTML = metaItems.map(([label, value]) => `
        <div class="meta-item">
          <label>${escapeHtml(label)}</label>
          <div>${escapeHtml(value)}</div>
        </div>
      `).join("");

      document.getElementById("depends-row").innerHTML = claim.depends_on?.length
        ? claim.depends_on.map((id) => pillButton(id)).join("")
        : `<span class="pill">No claim dependencies</span>`;
      document.getElementById("dependents-row").innerHTML = claim.dependents?.length
        ? claim.dependents.map((id) => pillButton(id)).join("")
        : `<span class="pill">No dependents</span>`;
      const external = claim.depends_on_external || [];
      document.getElementById("external-row").innerHTML = external.length
        ? external
            .map((item) => {
              const status = item.status ? ` - ${escapeHtml(item.status)}` : "";
              return `<span class="pill">${escapeHtml(item.title || item.id)}${status}</span>`;
            })
            .join("")
        : `<span class="pill">No external blockers</span>`;

      document.getElementById("step-shell").innerHTML = claim.steps.map((step) => {
        const fileLines = Object.entries(step.files || {})
          .filter(([, value]) => value)
          .map(([kind, value]) => `<div>${escapeHtml(kind)}: ${escapeHtml(value)}</div>`)
          .join("");
        const stepMeta = [
          step.modified_at ? `Updated ${step.modified_at}` : "",
          step.artifact_count ? `${step.artifact_count} artifact(s)` : ""
        ].filter(Boolean).join(" / ");
        return `
          <div class="step-row" data-status="${escapeHtml(step.status)}">
            <div class="step-header">
              <div class="step-title">${escapeHtml(step.label)}</div>
              <div class="step-state">${escapeHtml(statusLabel(step.status))}</div>
            </div>
            ${step.detail ? `<div class="step-detail">${escapeHtml(step.detail)}</div>` : ""}
            ${step.summary ? `<div class="step-summary">${escapeHtml(step.summary)}</div>` : ""}
            ${stepMeta ? `<div class="step-detail">${escapeHtml(stepMeta)}</div>` : ""}
            ${fileLines ? `<div class="step-files">${fileLines}</div>` : ""}
          </div>
        `;
      }).join("");

      renderTransitions(claim);
      renderArtifacts(claim);

      const timeline = document.getElementById("timeline-list");
      document.getElementById("timeline-detail").textContent =
        `${claim.events.length} event(s) for ${claim.title}`;
      if (!claim.events.length) {
        timeline.innerHTML =
          `<div class="empty">No dispatch or ledger events are recorded for this claim yet.</div>`;
      } else {
        timeline.innerHTML = claim.events.map((event) => `
          <div class="timeline-item">
            <div class="timeline-stamp">${escapeHtml(event.timestamp || "unknown time")}</div>
            <div class="timeline-kind">${escapeHtml(titleCase(event.kind || "event"))}</div>
            <div class="timeline-main">
              <div class="timeline-label">${escapeHtml(event.label || event.event || "Event")}</div>
              <div class="timeline-details">${escapeHtml(event.details || "")}</div>
            </div>
          </div>
        `).join("");
      }
      attachJumpHandlers();
    }

    function renderSelection({ centerSelected = false } = {}) {
      const snapshot = currentGraphSnapshot();
      const selectedClaim = selectedClaimForVisibleIds(snapshot.visibleIds);
      snapshot.selectedClaim = selectedClaim;
      renderGraphDetail(snapshot, selectedClaim);
      if (!snapshot.visibleIds.size) {
        graphLinks.innerHTML = "";
        renderEmptyInspector("No claim matches the current filter.");
      } else {
        applyGraphSelection(snapshot, selectedClaim);
        if (centerSelected && state.selectedId) {
          const behavior = state.hasRendered ? "smooth" : "auto";
          window.requestAnimationFrame(() => centerClaimNode(state.selectedId, behavior));
        }
        renderInspector(selectedClaim);
      }
      state.hasRendered = true;
    }

    function renderAll({ centerSelected = false } = {}) {
      renderGraph();
      renderSelection({ centerSelected });
    }

    function beginBoardDrag(event) {
      if (event.button !== 0) {
        return;
      }
      dragState.active = true;
      dragState.pointerId = event.pointerId;
      dragState.startX = event.clientX;
      dragState.startY = event.clientY;
      dragState.startScrollLeft = graphBoard.scrollLeft;
      dragState.startScrollTop = graphBoard.scrollTop;
      dragState.moved = false;
      graphBoard.classList.add("dragging");
      graphBoard.setPointerCapture(event.pointerId);
    }

    function moveBoardDrag(event) {
      if (!dragState.active || dragState.pointerId !== event.pointerId) {
        return;
      }
      const dx = event.clientX - dragState.startX;
      const dy = event.clientY - dragState.startY;
      if (!dragState.moved && Math.hypot(dx, dy) > 4) {
        dragState.moved = true;
        dragState.suppressClick = true;
      }
      if (!dragState.moved) {
        return;
      }
      graphBoard.scrollLeft = dragState.startScrollLeft - dx;
      graphBoard.scrollTop = dragState.startScrollTop - dy;
      scheduleDrawLinks();
    }

    function endBoardDrag(event) {
      if (!dragState.active || dragState.pointerId !== event.pointerId) {
        return;
      }
      const moved = dragState.moved;
      dragState.active = false;
      dragState.pointerId = null;
      dragState.moved = false;
      graphBoard.classList.remove("dragging");
      if (graphBoard.hasPointerCapture(event.pointerId)) {
        graphBoard.releasePointerCapture(event.pointerId);
      }
      if (moved) {
        window.setTimeout(() => {
          dragState.suppressClick = false;
        }, 0);
      }
    }

    searchInput.addEventListener("input", (event) => {
      const nextQuery = event.target.value.trim();
      if (searchTimer) {
        window.clearTimeout(searchTimer);
      }
      searchTimer = window.setTimeout(() => {
        searchTimer = 0;
        if (state.query === nextQuery) {
          return;
        }
        state.query = nextQuery;
        renderAll();
      }, 100);
    });
    graphBoard.addEventListener("pointerdown", beginBoardDrag);
    graphBoard.addEventListener("pointermove", moveBoardDrag);
    graphBoard.addEventListener("pointerup", endBoardDrag);
    graphBoard.addEventListener("pointercancel", endBoardDrag);
    graphBoard.addEventListener("scroll", scheduleDrawLinks);
    window.addEventListener("resize", scheduleDrawLinks);
    renderHeader();
    renderAll({ centerSelected: true });
  </script>
</body>
</html>
"""


def render_workspace_explorer_html(payload: dict[str, Any]) -> str:
    data_json = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    return _HTML_TEMPLATE.replace("__DATA__", data_json).replace(
        "__WORKSPACE_LABEL__", html.escape(str(payload["workspace_label"]))
    )


def generate_workspace_explorer(root: Path | None = None) -> tuple[Path, Path, dict[str, Any]]:
    research_root = _workspace_root(root)
    payload = build_workspace_explorer_payload(root=research_root)
    html_path = research_root / _EXPLORER_HTML
    json_path = research_root / _EXPLORER_JSON
    _cfg._atomic_write(json_path, json.dumps(payload, separators=(",", ":")))
    _cfg._atomic_write(html_path, render_workspace_explorer_html(payload))
    return html_path, json_path, payload


def cmd_visualize(args: argparse.Namespace) -> None:
    html_path, json_path, payload = generate_workspace_explorer(root=_cfg.RESEARCH_DIR)
    print(
        json.dumps(
            {
                "html_path": str(html_path),
                "json_path": str(json_path),
                "claim_count": len(payload["claims"]),
                "phase": payload["dashboard"]["phase"],
                "selected_claim": payload["selected_claim"],
            },
            indent=2,
        )
    )
