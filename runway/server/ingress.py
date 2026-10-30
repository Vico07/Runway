"""Home Assistant's authenticated Ingress boundary; never trust forwarded headers from other peers."""
from __future__ import annotations

import os
import hmac
import re

GATEWAY = "172.30.32.2"  # Supervisor's documented Ingress proxy, not an HTTP header supplied by a client.
PATH = re.compile(r"/api/hassio_ingress/[A-Za-z0-9_-]+\Z")


def enabled() -> bool:
    return os.environ.get("RUNWAY_HA_INGRESS") == "1"


def manual_only() -> bool:
    return enabled() or os.environ.get("RUNWAY_MANUAL_ONLY") == "1"


def base_path(peer: str, headers) -> str | None:
    if peer != GATEWAY:
        return None
    value = headers.get("X-Ingress-Path", "").rstrip("/")
    return value if PATH.fullmatch(value) else None


def allowed(path: str) -> bool:
    """Manual-only deployments cannot open bank connections, trigger syncs, or grant assistants alternate access."""
    return not path.startswith(("/api/connect", "/api/plaid", "/api/carta", "/api/sync", "/api/investments/sync",
                                "/api/ext/", "/api/retail/token", "/mcp", "/oauth/", "/.well-known/"))


def resource_paths(value, base: str):
    if isinstance(value, str) and value.startswith(("/api/", "/logos/", "/banks/", "/fonts/", "/auth/")):
        return base + value
    if isinstance(value, list):
        return [resource_paths(v, base) for v in value]
    if isinstance(value, dict):
        return {k: resource_paths(v, base) for k, v in value.items()}
    return value


SENSOR_PATHS = frozenset({"/api/ha/summary", "/api/ha/upcoming", "/api/ha/cashflow", "/api/ha/budget"})


def sensor_authorized(headers) -> bool:
    token = os.environ.get("RUNWAY_HA_SENSOR_TOKEN", "")
    supplied = headers.get("Authorization", "")
    return len(token) >= 32 and hmac.compare_digest(supplied.encode(), ("Bearer " + token).encode())
