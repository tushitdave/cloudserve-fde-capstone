"""Compatibility alias: this module now lives in `cloudserve.adapters.ml.classifier` (hexagonal layout).

Importing the old path returns the same module object, so state and monkeypatching are shared.
"""

import sys

from cloudserve.adapters.ml import classifier as _module

sys.modules[__name__] = _module
