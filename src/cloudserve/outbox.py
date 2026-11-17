"""Compatibility alias: this module now lives in `cloudserve.application.use_cases.deliver_messages` (hexagonal layout).

Importing the old path returns the same module object, so state and monkeypatching are shared.
"""

import sys

from cloudserve.application.use_cases import deliver_messages as _module

sys.modules[__name__] = _module
