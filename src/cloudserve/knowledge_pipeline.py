"""Compatibility alias: this module now lives in `cloudserve.application.use_cases.govern_knowledge` (hexagonal layout).

Importing the old path returns the same module object, so state and monkeypatching are shared.
"""

import sys

from cloudserve.application.use_cases import govern_knowledge as _module

sys.modules[__name__] = _module
