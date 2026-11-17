"""API identity, role-based access, tenant isolation, quotas and encryption at rest.

Research/02 "Reliability, observability and acceptance" and Research/03 "API security":
identity on every API call, role and object-level authorization (a customer can
never read another tenant's ticket), per-caller request quotas, secrets kept out of
code, and restricted storage for raw customer text.

API keys come from `CLOUDSERVE_API_KEYS` (JSON list of {key, key_id, role, tenant}).
If it is unset, five *local demo* keys are enabled so the README demo works
(`CLOUDSERVE_DEMO_KEYS=0` disables them). They are documented, not secret, and must
be replaced before any non-local use.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Header, HTTPException

from cloudserve.config import setting

ROLES = ("customer", "support_agent", "knowledge_owner", "operator", "admin")
DEMO_KEYS = [
    {"key": "demo-customer-key", "key_id": "demo-customer", "role": "customer", "tenant": "CUST-DEMO"},
    {"key": "demo-agent-key", "key_id": "demo-agent", "role": "support_agent", "tenant": "*"},
    {"key": "demo-knowledge-key", "key_id": "demo-knowledge-owner", "role": "knowledge_owner", "tenant": "*"},
    {"key": "demo-operator-key", "key_id": "demo-operator", "role": "operator", "tenant": "*"},
    {"key": "demo-admin-key", "key_id": "demo-admin", "role": "admin", "tenant": "*"},
]


@dataclass(frozen=True)
class Principal:
    key_id: str
    role: str
    tenant: str  # "*" = all tenants (staff roles)

    def can_see_tenant(self, tenant: str | None) -> bool:
        return self.tenant == "*" or (tenant is not None and hmac.compare_digest(self.tenant, tenant))


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@lru_cache(maxsize=1)
def _key_table() -> dict[str, Principal]:
    raw = setting("CLOUDSERVE_API_KEYS", "")
    entries = json.loads(raw) if raw.strip() else ([] if setting("CLOUDSERVE_DEMO_KEYS", "1") == "0" else DEMO_KEYS)
    table = {}
    for entry in entries:
        if entry["role"] not in ROLES:
            raise ValueError(f"unknown role {entry['role']}")
        table[_digest(entry["key"])] = Principal(entry["key_id"], entry["role"], entry.get("tenant", "*"))
    return table


def reload_keys() -> None:
    _key_table.cache_clear()


# ---------------------------------------------------------------- quotas
class RateLimiter:
    """Sliding one-minute window per API key."""

    def __init__(self):
        self.calls: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key_id: str, limit: int) -> int | None:
        now = time.monotonic()
        with self.lock:
            window = self.calls[key_id]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= limit:
                return int(60 - (now - window[0])) + 1
            window.append(now)
        return None


LIMITER = RateLimiter()


def authenticate(x_api_key: str | None) -> Principal:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header", headers={"WWW-Authenticate": "ApiKey"})
    principal = _key_table().get(_digest(x_api_key))
    if principal is None:
        raise HTTPException(status_code=401, detail="Unknown API key", headers={"WWW-Authenticate": "ApiKey"})
    retry = LIMITER.check(principal.key_id, int(setting("CLOUDSERVE_RATE_LIMIT_PER_MIN", "600")))
    if retry is not None:
        raise HTTPException(status_code=429, detail="Request quota exceeded", headers={"Retry-After": str(retry)})
    return principal


def require(*roles: str):
    """FastAPI dependency: authenticated caller whose role is allowed (admin is always allowed)."""
    allowed = set(roles) | {"admin"}

    def dependency(x_api_key: str | None = Header(default=None)) -> Principal:
        principal = authenticate(x_api_key)
        if principal.role not in allowed:
            raise HTTPException(status_code=403, detail=f"Role {principal.role} may not perform this action")
        return principal

    return dependency
