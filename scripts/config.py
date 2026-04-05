from principia.core import config as _config
from principia.core.config import *  # noqa: F403

for _name in ("RESEARCH_DIR", "DB_PATH", "CONTEXT_DIR", "PROGRESS_PATH", "FOUNDATIONS_PATH"):
    globals().pop(_name, None)


def __getattr__(name: str) -> object:
    return getattr(_config, name)
