"""Publish the approved passage index using the configured Azure embedding deployment."""

import json

from cloudserve.knowledge import build_dense_index


if __name__ == "__main__":
    print(json.dumps(build_dense_index(), indent=2))
