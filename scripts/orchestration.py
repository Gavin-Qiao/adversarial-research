from principia.core import orchestration as _orchestration
from principia.core.orchestration import *  # noqa: F403


def __getattr__(name: str) -> object:
    return getattr(_orchestration, name)
