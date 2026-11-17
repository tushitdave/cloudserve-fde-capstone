"""Compatibility alias: this module now lives in `cloudserve.application.reliability` (hexagonal layout).

Importing the old path returns the same module object, so state and monkeypatching are shared.
"""

import sys

from cloudserve.application import reliability as _module

sys.modules[__name__] = _module
