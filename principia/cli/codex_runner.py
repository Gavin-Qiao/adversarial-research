from __future__ import annotations

import argparse
import json
from pathlib import Path

from principia.api.engine import PrincipiaEngine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("command", choices=["build", "dashboard", "validate", "results"])
    args = parser.parse_args()

    engine = PrincipiaEngine(root=args.root)
    payload = getattr(engine, args.command)()
    print(json.dumps(payload, indent=2))
    if args.command == "validate" and not payload.get("valid", True):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
