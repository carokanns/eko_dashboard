from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    if parsed <= 0:
        return default
    return parsed


YAHOO_MAX_CALLS = _int_env("APP_YAHOO_MAX_CALLS", 120)
YAHOO_PERIOD_SECONDS = _int_env("APP_YAHOO_PERIOD_SECONDS", 60)
FRED_MAX_CALLS = _int_env("APP_FRED_MAX_CALLS", 60)
FRED_PERIOD_SECONDS = _int_env("APP_FRED_PERIOD_SECONDS", 60)

UPSTREAM_RETRY_ATTEMPTS = _int_env("APP_UPSTREAM_RETRY_ATTEMPTS", 3)
UPSTREAM_RETRY_BASE_MS = _int_env("APP_UPSTREAM_RETRY_BASE_MS", 250)
