from __future__ import annotations

from importlib import import_module

__all__ = ["codex_runner"]


def __getattr__(name: str) -> object:
    if name == "codex_runner":
        return import_module("principia.cli.codex_runner")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
