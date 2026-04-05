from principia.core import validation as _validation
from principia.core.validation import *  # noqa: F403


def __getattr__(name: str) -> object:
    return getattr(_validation, name)
