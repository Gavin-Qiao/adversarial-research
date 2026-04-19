from __future__ import annotations

import argparse
import json
from pathlib import Path

from principia.api.engine import PrincipiaEngine


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m principia.cli.codex_runner",
        description=(
            "Codex-friendly Principia control plane. "
            "Use `dashboard` for live state, `next` for the preferred next move, "
            "`patch-status` for drift, `results` for synthesis, and `visualize` for the explorer."
        ),
        epilog=(
            "Common flow: dashboard -> next. If claims drift from the north star, run patch-status. "
            "Use packet/prompt/dispatch-log for stateful handoffs, then results or visualize. "
            "The --root path points at the generated workflow workspace, usually `principia/`."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("principia"),
        help="Workflow workspace root. This is the generated `principia/` directory, not the Python package path.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="command")

    subparsers.add_parser("build", help="Rebuild the workspace database and return node and edge counts.")
    subparsers.add_parser("dashboard", help="Return live state, warnings, and operator guidance for the workspace.")

    next_parser = subparsers.add_parser(
        "next",
        help="Return the preferred next action for a claim, or recovery guidance when no claim is selected.",
    )
    next_parser.add_argument("--path", default="auto", help="Claim path such as claims/claim-1-example, or `auto`.")

    packet_parser = subparsers.add_parser(
        "packet",
        help="Materialize the canonical packet for a stateful external or sidecar handoff.",
    )
    packet_parser.add_argument("--path", required=True, help="Claim path such as claims/claim-1-example.")

    prompt_parser = subparsers.add_parser(
        "prompt",
        help="Materialize the packet and prompt needed to send a claim handoff.",
    )
    prompt_parser.add_argument("--path", required=True, help="Claim path such as claims/claim-1-example.")

    dispatch_log_parser = subparsers.add_parser(
        "dispatch-log",
        help="Inspect the audit trail for a handoff, including stale or waiting external work.",
    )
    dispatch_log_parser.add_argument("--cycle", default=None, help="Claim slug such as claim-1-example.")

    subparsers.add_parser(
        "patch-status",
        help="Inspect north-star version drift and reconciliation needs across claim files.",
    )
    subparsers.add_parser("validate", help="Run workspace integrity checks and exit nonzero on invalid state.")
    subparsers.add_parser("results", help="Regenerate RESULTS.md and return stakeholder-facing trust signals.")
    subparsers.add_parser("visualize", help="Generate the workspace explorer HTML and JSON for structural inspection.")
    args = parser.parse_args()

    engine = PrincipiaEngine(root=args.root)
    payload: object
    if args.command == "next":
        payload = engine.next(path=args.path)
    elif args.command == "packet":
        payload = engine.packet(path=args.path)
    elif args.command == "prompt":
        payload = engine.prompt(path=args.path)
    elif args.command == "dispatch-log":
        payload = engine.dispatch_log(cycle=args.cycle)
    elif args.command == "patch-status":
        payload = engine.patch_status()
    else:
        payload = getattr(engine, args.command)()
    print(json.dumps(payload, indent=2))
    if args.command == "validate" and isinstance(payload, dict) and not payload.get("valid", True):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
