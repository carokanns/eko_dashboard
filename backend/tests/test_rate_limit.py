from __future__ import annotations

from app.core.rate_limit import SlidingWindowRateLimiter


def test_sliding_window_rate_limiter_blocks_after_threshold():
    limiter = SlidingWindowRateLimiter()
    key = "provider:test"
    assert limiter.allow(key, max_calls=2, period_seconds=60) is True
    assert limiter.allow(key, max_calls=2, period_seconds=60) is True
    assert limiter.allow(key, max_calls=2, period_seconds=60) is False
