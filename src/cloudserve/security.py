"""Compatibility alias: this module now lives in `cloudserve.api.security` (hexagonal layout).

Importing the old path returns the same module object, so state and monkeypatching are shared.
"""

import sys

from cloudserve.api import security as _module

sys.modules[__name__] = _module
