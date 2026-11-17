"""Compatibility alias: this module now lives in `cloudserve.adapters.persistence.knowledge_store` (hexagonal layout).

Importing the old path returns the same module object, so state and monkeypatching are shared.
"""

import sys

from cloudserve.adapters.persistence import knowledge_store as _module

sys.modules[__name__] = _module
