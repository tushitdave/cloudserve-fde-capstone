"""Compatibility alias: this module now lives in `cloudserve.domain.policies.guardrails` (hexagonal layout).

Importing the old path returns the same module object, so state and monkeypatching are shared.
"""

import sys

from cloudserve.domain.policies import guardrails as _module

sys.modules[__name__] = _module
