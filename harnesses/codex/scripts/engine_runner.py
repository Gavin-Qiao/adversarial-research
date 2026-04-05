from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
project_root = str(_PROJECT_ROOT)
if project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)

_REPO_CHECKOUT_REQUIRED = (
    "ERROR: The Codex harness requires a full Principia repository checkout. "
    "Use the repo-local harness at `harnesses/codex` inside the Principia repo; "
    "copying `harnesses/codex` by itself is unsupported."
)


def _load_engine():
    if not (_PROJECT_ROOT / "principia").is_dir():
        print(_REPO_CHECKOUT_REQUIRED, file=sys.stderr)
        raise SystemExit(2)

    try:
        from principia.api.engine import PrincipiaEngine
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.split(".")[0] == "principia":
            print(_REPO_CHECKOUT_REQUIRED, file=sys.stderr)
            raise SystemExit(2) from None
        raise

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
