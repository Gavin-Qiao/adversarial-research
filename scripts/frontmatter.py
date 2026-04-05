from principia.core import frontmatter as _frontmatter
from principia.core.frontmatter import *  # noqa: F403


def __getattr__(name: str) -> object:
    return getattr(_frontmatter, name)
