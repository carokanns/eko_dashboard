from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import random
import time
from typing import Iterable

import yfinance as yf

from app.core.provider_monitor import provider_monitor
from app.core.rate_limit import rate_limiter
from app.core.settings import (
    UPSTREAM_RETRY_ATTEMPTS,
    UPSTREAM_RETRY_BASE_MS,
    YAHOO_MAX_CALLS,
    YAHOO_PERIOD_SECONDS,
)


RANGE_TO_PERIOD = {
    "1m": "1mo",
    "3m": "3mo",
    "6m": "6mo",
    "1y": "1y",
}
PROVIDER_NAME = "yahoo_finance"


@dataclass
class HistoryPoint:
    t: datetime
    close: float


@dataclass
class QuoteSnapshot:
    timestamp: datetime | None
    last: float | None
    prev_close: float | None
    history: list[HistoryPoint]


def _to_utc(value: object) -> datetime | None:
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _extract_history_points(dataframe: object) -> list[HistoryPoint]:
    if dataframe is None:
        return []
    try:
        close_series = dataframe["Close"]
    except Exception:
        return []

    points: list[HistoryPoint] = []
    for timestamp, close in close_series.items():
        if close is None:
            continue
        try:
            numeric = float(close)
        except (TypeError, ValueError):
            continue
        point_time = _to_utc(timestamp)
        if point_time is None:
            continue
        points.append(HistoryPoint(t=point_time, close=numeric))
    return points


def fetch_quotes_with_history(
    tickers: Iterable[str],
    period: str = "1y",
    interval: str = "1d",
) -> tuple[dict[str, QuoteSnapshot], dict[str, str]]:
    snapshots: dict[str, QuoteSnapshot] = {}
    errors: dict[str, str] = {}

    for ticker in tickers:
        try:
            if not rate_limiter.allow(PROVIDER_NAME, YAHOO_MAX_CALLS, YAHOO_PERIOD_SECONDS):
                raise RuntimeError("Yahoo Finance rate limit reached.")

            dataframe = _with_retry(
                lambda: yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False),
                ticker=ticker,
            )
            history = _extract_history_points(dataframe)
            if not history:
                errors[ticker] = "No data returned from Yahoo Finance."
                provider_monitor.record_failure(PROVIDER_NAME, errors[ticker])
                continue
            latest = history[-1]
            prev_close = history[-2].close if len(history) > 1 else None
            snapshots[ticker] = QuoteSnapshot(
                timestamp=latest.t,
                last=latest.close,
                prev_close=prev_close,
                history=history,
            )
            provider_monitor.record_success(PROVIDER_NAME)
        except Exception as exc:
            errors[ticker] = str(exc)
            provider_monitor.record_failure(PROVIDER_NAME, str(exc))
    return snapshots, errors


def fetch_history(ticker: str, range_key: str) -> list[HistoryPoint]:
    period = RANGE_TO_PERIOD.get(range_key)
    if period is None:
        raise ValueError(f"Unsupported range: {range_key}")

    if not rate_limiter.allow(PROVIDER_NAME, YAHOO_MAX_CALLS, YAHOO_PERIOD_SECONDS):
        message = "Yahoo Finance rate limit reached."
        provider_monitor.record_failure(PROVIDER_NAME, message)
        raise RuntimeError(message)

    dataframe = _with_retry(
        lambda: yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False),
        ticker=ticker,
    )
    provider_monitor.record_success(PROVIDER_NAME)
    return _extract_history_points(dataframe)


def _with_retry(callable_fn, ticker: str) -> object:
    provider_monitor.record_attempt(PROVIDER_NAME)
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

    raise RuntimeError(f"Yahoo request failed for {ticker}: {last_error}")
