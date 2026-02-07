from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any


DEFAULT_TTL_SECONDS = 60


@dataclass
class CacheEntry:
    value: Any
    expires_at: datetime
    fetched_at: datetime


class InMemoryTTLCache:
    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, CacheEntry] = {}
        self._last_update: datetime | None = None
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
            }

    def last_update(self) -> datetime | None:
        with self._lock:
            return self._last_update

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._last_update = None


cache = InMemoryTTLCache(ttl_seconds=DEFAULT_TTL_SECONDS)
