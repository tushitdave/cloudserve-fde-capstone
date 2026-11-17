"""Compatibility alias: this module now lives in `cloudserve.adapters.azure.openai_client` (hexagonal layout).

Importing the old path returns the same module object, so state and monkeypatching are shared.
"""

import sys

from cloudserve.adapters.azure import openai_client as _module

sys.modules[__name__] = _module
