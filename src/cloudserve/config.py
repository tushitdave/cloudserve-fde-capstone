"""Runtime configuration without logging or serializing secrets."""

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]


def _dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


LOCAL_ENV = _dotenv(APP_ROOT / ".env")
PARENT_ENV = _dotenv(APP_ROOT.parent / ".env")


def setting(name: str, default: str = "") -> str:
    return os.environ.get(name) or LOCAL_ENV.get(name) or PARENT_ENV.get(name) or default


def supplied(name: str) -> Path:
    return APP_ROOT / "data" / "supplied" / name


def runtime_dir() -> Path:
    path = Path(setting("CLOUDSERVE_RUNTIME_DIR", str(APP_ROOT / "data" / "runtime")))
    path.mkdir(parents=True, exist_ok=True)
    return path
