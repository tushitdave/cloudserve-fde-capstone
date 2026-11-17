"""Compatibility alias: this module now lives in `cloudserve.adapters.retrieval.knowledge_index` (hexagonal layout).

Importing the old path returns the same module object, so state and monkeypatching are shared.
"""

import sys

from cloudserve.adapters.retrieval import knowledge_index as _module

sys.modules[__name__] = _module
