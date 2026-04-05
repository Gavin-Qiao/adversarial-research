import sys

from principia.core import db as _db

sys.modules[__name__] = _db
