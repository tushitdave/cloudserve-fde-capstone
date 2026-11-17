"""Encryption at rest for stored ticket records (Fernet: AES-128-CBC + HMAC-SHA256).

The key comes from `CLOUDSERVE_DATA_KEY` or, for local use, a generated key file
`<runtime>/data.key` (mode 0600, git-ignored). Records written before encryption was
enabled are read as plain text.
"""

import os
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from cloudserve.config import runtime_dir, setting


@lru_cache(maxsize=4)
def _fernet(key_path: str) -> Fernet:
    configured = os.environ.get("CLOUDSERVE_DATA_KEY") or setting("CLOUDSERVE_DATA_KEY", "")
    if configured:
        return Fernet(configured.encode())
    path = Path(key_path)
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
        path.chmod(0o600)
    return Fernet(path.read_bytes().strip())


def cipher() -> Fernet:
    return _fernet(str(runtime_dir() / "data.key"))


PREFIX = "enc:v1:"


def encrypt(text: str) -> str:
    return PREFIX + cipher().encrypt(text.encode()).decode()


def decrypt(value: str) -> str:
    if not value.startswith(PREFIX):
        return value  # rows written before encryption was enabled
    try:
        return cipher().decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken as error:
        raise RuntimeError("Stored record cannot be decrypted with the configured data key") from error
