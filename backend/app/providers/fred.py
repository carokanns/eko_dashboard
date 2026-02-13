from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
import random
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from app.core.provider_monitor import provider_monitor
from app.core.rate_limit import rate_limiter
from app.core.settings import (
    FRED_MAX_CALLS,
    FRED_PERIOD_SECONDS,
    UPSTREAM_RETRY_ATTEMPTS,
    UPSTREAM_RETRY_BASE_MS,
)


FRED_GRAPH_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
PROVIDER_NAME = "fred"


@dataclass
class FredPoint:
    t: datetime
    value: float


def fetch_series(series_id: str) -> list[FredPoint]:
    provider_monitor.record_attempt(PROVIDER_NAME)
    if not rate_limiter.allow(PROVIDER_NAME, FRED_MAX_CALLS, FRED_PERIOD_SECONDS):
        message = "FRED rate limit reached."
        provider_monitor.record_failure(PROVIDER_NAME, message)
        raise RuntimeError(message)

    query = urlencode({"id": series_id})
    payload = _with_retry(
        lambda: _download_payload(query),
        series_id=series_id,
    )

    points: list[FredPoint] = []
    reader = csv.DictReader(StringIO(payload))
    for row in reader:
        value = row.get(series_id)
        if value in (None, "", "."):
            continue
        observation_date = row.get("observation_date")
        if not observation_date:
            continue
        try:
            parsed = datetime.strptime(observation_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            numeric = float(value)
        except ValueError:
            continue
        points.append(FredPoint(t=parsed, value=numeric))
    provider_monitor.record_success(PROVIDER_NAME)
    return points


def _download_payload(query: str) -> str:
    with urlopen(f"{FRED_GRAPH_CSV_URL}?{query}", timeout=20) as response:
        return response.read().decode("utf-8")


def _with_retry(callable_fn, series_id: str) -> str:
    last_error: Exception | None = None
    attempts = max(1, UPSTREAM_RETRY_ATTEMPTS)
    for attempt in range(attempts):
        try:
            return callable_fn()
        except Exception as exc:  # pragma: no cover - upstream/network failures are hard to deterministically trigger.
            last_error = exc
            if attempt + 1 >= attempts:
                break
            provider_monitor.record_retry(PROVIDER_NAME)
            base_seconds = UPSTREAM_RETRY_BASE_MS / 1000.0
            sleep_seconds = base_seconds * (2**attempt) + random.uniform(0, base_seconds)
            time.sleep(sleep_seconds)

    provider_monitor.record_failure(PROVIDER_NAME, str(last_error))
    raise RuntimeError(f"FRED request failed for {series_id}: {last_error}")
