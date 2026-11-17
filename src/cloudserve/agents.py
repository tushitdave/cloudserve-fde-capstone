"""Compatibility alias: this module now lives in `cloudserve.orchestration.agents.roles` (hexagonal layout).

Importing the old path returns the same module object, so state and monkeypatching are shared.
"""

import sys

from cloudserve.orchestration.agents import roles as _module

sys.modules[__name__] = _module
