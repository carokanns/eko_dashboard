from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock


class ProviderMonitor:
    def __init__(self) -> None:
        self._lock = Lock()
        self._stats: dict[str, dict[str, object]] = defaultdict(
            lambda: {
                "attempts": 0,
                "success": 0,
                "fail": 0,
                "retries": 0,
                "last_error": None,
                "last_failure_at": None,
            }
        )

    def record_attempt(self, provider: str) -> None:
        with self._lock:
            self._stats[provider]["attempts"] = int(self._stats[provider]["attempts"]) + 1

    def record_success(self, provider: str) -> None:
        with self._lock:
            self._stats[provider]["success"] = int(self._stats[provider]["success"]) + 1

    def record_failure(self, provider: str, error: str) -> None:
        with self._lock:
            row = self._stats[provider]
            row["fail"] = int(row["fail"]) + 1
            row["last_error"] = error
            row["last_failure_at"] = datetime.now(timezone.utc).isoformat()

    def record_retry(self, provider: str) -> None:
        with self._lock:
            self._stats[provider]["retries"] = int(self._stats[provider]["retries"]) + 1

    def snapshot(self) -> dict[str, dict[str, object]]:
        with self._lock:
            return {provider: dict(values) for provider, values in self._stats.items()}

    def clear(self) -> None:
        with self._lock:
            self._stats.clear()


provider_monitor = ProviderMonitor()
