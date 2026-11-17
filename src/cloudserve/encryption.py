"""Compatibility alias: this module now lives in `cloudserve.adapters.persistence.encryption` (hexagonal layout).

Importing the old path returns the same module object, so state and monkeypatching are shared.
"""

import sys

from cloudserve.adapters.persistence import encryption as _module

sys.modules[__name__] = _module
