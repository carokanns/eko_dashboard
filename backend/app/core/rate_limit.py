from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
import time


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, max_calls: int, period_seconds: int) -> bool:
        if max_calls <= 0 or period_seconds <= 0:
            return True

        now = time.time()
        cutoff = now - period_seconds
        with self._lock:
            queue = self._events[key]
            while queue and queue[0] <= cutoff:
                queue.popleft()

            if len(queue) >= max_calls:
                return False

            queue.append(now)
            return True


rate_limiter = SlidingWindowRateLimiter()
