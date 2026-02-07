from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import yfinance as yf


RANGE_TO_PERIOD = {
    "1m": "1mo",
    "3m": "3mo",
    "1y": "1y",
}


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
            ticker_client = yf.Ticker(ticker)
            dataframe = ticker_client.history(period=period, interval=interval, auto_adjust=False)
            history = _extract_history_points(dataframe)
            if not history:
                errors[ticker] = "No data returned from Yahoo Finance."
                continue
            latest = history[-1]
            prev_close = history[-2].close if len(history) > 1 else None
            snapshots[ticker] = QuoteSnapshot(
                timestamp=latest.t,
                last=latest.close,
                prev_close=prev_close,
                history=history,
            )
        except Exception as exc:
            errors[ticker] = str(exc)
    return snapshots, errors


def fetch_history(ticker: str, range_key: str) -> list[HistoryPoint]:
    period = RANGE_TO_PERIOD.get(range_key)
    if period is None:
        raise ValueError(f"Unsupported range: {range_key}")

    ticker_client = yf.Ticker(ticker)
    dataframe = ticker_client.history(period=period, interval="1d", auto_adjust=False)
    return _extract_history_points(dataframe)
