from principia.core import db as _db
from principia.core.db import *  # noqa: F403


def __getattr__(name: str) -> object:
    return getattr(_db, name)
