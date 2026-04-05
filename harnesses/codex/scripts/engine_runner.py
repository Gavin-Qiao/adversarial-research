from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
project_root = str(_PROJECT_ROOT)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def _load_engine():
    from principia.api.engine import PrincipiaEngine

    return PrincipiaEngine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("command", choices=["build", "dashboard", "validate", "results"])
    args = parser.parse_args()

    engine_class = _load_engine()
    engine = engine_class(root=args.root)
    payload = getattr(engine, args.command)()
    print(json.dumps(payload, indent=2))
    if args.command == "validate" and not payload.get("valid", True):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
