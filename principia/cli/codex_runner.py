from __future__ import annotations

import argparse
import json
from pathlib import Path

from principia.api.engine import PrincipiaEngine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("principia"))
    parser.add_argument(
        "command",
        choices=["build", "dashboard", "next", "packet", "prompt", "dispatch-log", "patch-status", "validate", "results"],
    )
    parser.add_argument("--path", default="auto")
    parser.add_argument("--cycle", default=None)
    args = parser.parse_args()

    engine = PrincipiaEngine(root=args.root)
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
    if args.command == "validate" and not payload.get("valid", True):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
