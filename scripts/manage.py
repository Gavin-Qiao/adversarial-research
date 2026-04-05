from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
project_root = str(_PROJECT_ROOT)
if project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)


def __getattr__(name: str) -> object:
    from principia.cli import manage as _manage

    return getattr(_manage, name)


def main() -> None:
    from principia.cli.manage import main as package_main

    package_main()


if __name__ == "__main__":
    main()
