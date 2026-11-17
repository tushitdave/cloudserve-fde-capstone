"""Compatibility alias: this module now lives in `cloudserve.domain.models.contracts` (hexagonal layout).

Importing the old path returns the same module object, so state and monkeypatching are shared.
"""

import sys

from cloudserve.domain.models import contracts as _module

sys.modules[__name__] = _module
