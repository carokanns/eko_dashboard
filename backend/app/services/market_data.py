from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import InstrumentConfig
from app.models.summary import SparkPoint, SummaryItem
from app.providers import yahoo_finance
from app.providers.yahoo_finance import HistoryPoint, QuoteSnapshot


def _round_value(value: float | None, precision: int) -> float | None:
    if value is None:
        return None
    return round(value, precision)


def _pct_change(current: float | None, reference: float | None) -> float | None:
    if current is None or reference in (None, 0):
        return None
    return (current - reference) / reference * 100.0


def _point_before(points: list[HistoryPoint], target: datetime) -> HistoryPoint | None:
    for point in reversed(points):
        if point.t <= target:
            return point
    return None


def _first_point_of_year(points: list[HistoryPoint], year: int) -> HistoryPoint | None:
    for point in points:
        if point.t.year == year:
            return point
    return None


def calculate_metrics(last: float | None, prev_close: float | None, history: list[HistoryPoint]) -> dict[str, float | None]:
    now = datetime.now(timezone.utc)
    one_week_reference = _point_before(history, now - timedelta(days=7))
    previous_year_reference = _point_before(history, now - timedelta(days=365))
    ytd_reference = _first_point_of_year(history, now.year)

    day_abs = (last - prev_close) if (last is not None and prev_close is not None) else None
    return {
        "day_abs": day_abs,
        "day_pct": _pct_change(last, prev_close),
        "w1_pct": _pct_change(last, one_week_reference.close if one_week_reference else None),
        "ytd_pct": _pct_change(last, ytd_reference.close if ytd_reference else None),
        "y1_pct": _pct_change(last, previous_year_reference.close if previous_year_reference else None),
    }


def build_summary_items(
    instruments: list[InstrumentConfig],
    snapshots: dict[str, QuoteSnapshot],
    errors: dict[str, str] | None = None,
) -> list[SummaryItem]:
    errors = errors or {}
    ordered = sorted(instruments, key=lambda item: item.sort_order)
    output: list[SummaryItem] = []

    for instrument in ordered:
        snapshot = snapshots.get(instrument.ticker)
        has_error = instrument.ticker in errors
        if snapshot is None or snapshot.last is None:
            output.append(
                SummaryItem(
                    id=instrument.id,
                    name=instrument.name_sv,
                    unit=instrument.unit_label,
                    price_type=instrument.price_type,
                    last=None,
                    day_abs=None,
                    day_pct=None,
                    w1_pct=None,
                    ytd_pct=None,
                    y1_pct=None,
                    timestamp_local=None,
                    is_stale=True,
                    sparkline=[],
                )
            )
            continue

        metrics = calculate_metrics(snapshot.last, snapshot.prev_close, snapshot.history)
        sparkline_points = [
            SparkPoint(t=point.t, v=_round_value(point.close, instrument.precision) or point.close)
            for point in snapshot.history[-30:]
        ]
        output.append(
            SummaryItem(
                id=instrument.id,
                name=instrument.name_sv,
                unit=instrument.unit_label,
                price_type=instrument.price_type,
                last=_round_value(snapshot.last, instrument.precision),
                day_abs=_round_value(metrics["day_abs"], instrument.precision),
                day_pct=_round_value(metrics["day_pct"], 2),
                w1_pct=_round_value(metrics["w1_pct"], 2),
                ytd_pct=_round_value(metrics["ytd_pct"], 2),
                y1_pct=_round_value(metrics["y1_pct"], 2),
                timestamp_local=snapshot.timestamp,
                is_stale=has_error,
                sparkline=sparkline_points,
            )
        )
    return output


def fetch_summary_for_instruments(
    instruments: list[InstrumentConfig],
) -> tuple[list[SummaryItem], dict[str, str]]:
    tickers = [item.ticker for item in instruments]
    snapshots, errors = yahoo_finance.fetch_quotes_with_history(tickers=tickers, period="1y")
    items = build_summary_items(instruments=instruments, snapshots=snapshots, errors=errors)
    return items, errors


def fetch_series_for_instrument(instrument: InstrumentConfig, range_key: str) -> list[SparkPoint]:
    points = yahoo_finance.fetch_history(ticker=instrument.ticker, range_key=range_key)
    return [SparkPoint(t=point.t, v=round(point.close, instrument.precision)) for point in points]
