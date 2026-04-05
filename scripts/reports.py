from principia.core import reports as _reports
from principia.core.reports import *  # noqa: F403


def __getattr__(name: str) -> object:
    return getattr(_reports, name)
