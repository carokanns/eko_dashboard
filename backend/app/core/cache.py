from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from threading import Lock
from typing import Any


DEFAULT_TTL_SECONDS = 60
DEFAULT_STALE_THRESHOLD_SECONDS = 600


@dataclass
class CacheEntry:
    value: Any
    expires_at: datetime
    fetched_at: datetime


class InMemoryTTLCache:
    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.stale_threshold_seconds = stale_threshold_seconds
        self._store: dict[str, CacheEntry] = {}
        self._last_update: datetime | None = None
        self._last_success_by_module: dict[str, datetime | None] = {
            "commodities": None,
            "mag7": None,
            "inflation": None,
        }
        self._lock = Lock()

    def get(self, key: str) -> CacheEntry | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._store.pop(key, None)
                return None
            return entry

    def set(
        self,
        key: str,
        value: Any,
        fetched_at: datetime | None = None,
        update_last_update: bool = True,
        module: str | None = None,
    ) -> CacheEntry:
        fetch_time = fetched_at or datetime.now(timezone.utc)
        entry = CacheEntry(
            value=value,
            fetched_at=fetch_time,
            expires_at=fetch_time + timedelta(seconds=self.ttl_seconds),
        )
        with self._lock:
            self._store[key] = entry
            if update_last_update:
                self._last_update = fetch_time
                if module in self._last_success_by_module:
                    self._last_success_by_module[module] = fetch_time
        return entry

    def stats(self) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        with self._lock:
            expired_keys = [key for key, value in self._store.items() if value.expires_at <= now]
            for key in expired_keys:
                self._store.pop(key, None)
            return {
                "entries": len(self._store),
                "ttl_seconds": self.ttl_seconds,
                "stale_threshold_seconds": self.stale_threshold_seconds,
            }

    def last_update(self) -> datetime | None:
        with self._lock:
            return self._last_update

    def is_globally_stale(self) -> bool:
        now = datetime.now(timezone.utc)
        with self._lock:
            if self._last_update is None:
                return True
            return (now - self._last_update).total_seconds() > self.stale_threshold_seconds

    def last_success_by_module(self) -> dict[str, datetime | None]:
        with self._lock:
            return dict(self._last_success_by_module)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._last_update = None
            for module in self._last_success_by_module:
                self._last_success_by_module[module] = None


def _stale_threshold_from_env() -> int:
    raw = os.getenv("APP_STALE_THRESHOLD_SECONDS")
    if raw is None:
        return DEFAULT_STALE_THRESHOLD_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_STALE_THRESHOLD_SECONDS
    if value <= 0:
        return DEFAULT_STALE_THRESHOLD_SECONDS
    return value


cache = InMemoryTTLCache(
    ttl_seconds=DEFAULT_TTL_SECONDS,
    stale_threshold_seconds=_stale_threshold_from_env(),
)
