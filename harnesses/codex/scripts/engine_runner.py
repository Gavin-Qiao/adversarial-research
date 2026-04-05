from __future__ import annotations

import argparse
import io
import json
import sys
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
project_root = str(_PROJECT_ROOT)
if project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)

from principia.api.engine import PrincipiaEngine
from principia.core.reports import cmd_results
from principia.core.validation import cmd_validate


def _run_validate() -> tuple[dict[str, object], int]:
    buffer = io.StringIO()
    exit_code = 0

    with redirect_stdout(buffer):
        try:
            cmd_validate(Namespace(json=True))
        except SystemExit as exc:
            exit_code = int(exc.code) if isinstance(exc.code, int) else 1

    return json.loads(buffer.getvalue()), exit_code


def _run_results(root: Path) -> tuple[dict[str, object], int]:
    buffer = io.StringIO()

    with redirect_stdout(buffer):
        cmd_results(Namespace())

    results_path = root / "RESULTS.md"
    return {
        "results_path": str(results_path),
        "exists": results_path.exists(),
        "message": buffer.getvalue().strip(),
    }, 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("command", choices=["build", "dashboard", "validate", "results"])
    args = parser.parse_args()

    engine = PrincipiaEngine(root=args.root)

    if args.command == "validate":
        payload, exit_code = _run_validate()
    elif args.command == "results":
        payload, exit_code = _run_results(args.root)
    else:
        payload = getattr(engine, args.command)()
        exit_code = 0

    print(json.dumps(payload, indent=2))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
