from __future__ import annotations

from datetime import timedelta

from app.core.config import InstrumentConfig
from app.models.summary import SparkPoint, SummaryItem
from app.providers import fred
from app.providers.yahoo_finance import HistoryPoint
from app.services.market_data import calculate_metrics


RANGE_TO_MONTHS = {
    "1m": 1,
    "3m": 3,
    "6m": 6,
    "1y": 12,
}


def _round_value(value: float | None, precision: int) -> float | None:
    if value is None:
        return None
    return round(value, precision)


def _empty_item(instrument: InstrumentConfig) -> SummaryItem:
    return SummaryItem(
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


def _to_yoy_points(points: list[fred.FredPoint]) -> list[HistoryPoint]:
    sorted_points = sorted(points, key=lambda point: point.t)
    by_year_month = {(point.t.year, point.t.month): point.value for point in sorted_points}

    output: list[HistoryPoint] = []
    for point in sorted_points:
        reference = by_year_month.get((point.t.year - 1, point.t.month))
        if reference in (None, 0):
            continue
        yoy = (point.value - reference) / reference * 100.0
        output.append(HistoryPoint(t=point.t, close=yoy))
    return output


def _filter_by_range(points: list[HistoryPoint], range_key: str) -> list[HistoryPoint]:
    months = RANGE_TO_MONTHS.get(range_key)
    if months is None:
        raise ValueError(f"Unsupported range: {range_key}")
    if not points:
        return []
    cutoff = points[-1].t - timedelta(days=31 * months)
    return [point for point in points if point.t >= cutoff]


def fetch_summary_for_instruments(
    instruments: list[InstrumentConfig],
) -> tuple[list[SummaryItem], dict[str, str]]:
    ordered = sorted(instruments, key=lambda item: item.sort_order)
    items: list[SummaryItem] = []
    errors: dict[str, str] = {}

    for instrument in ordered:
        try:
            raw_points = fred.fetch_series(series_id=instrument.ticker)
            yoy_points = _to_yoy_points(raw_points)
            if not yoy_points:
                raise ValueError("No YoY data returned from source.")

            latest = yoy_points[-1]
            prev = yoy_points[-2].close if len(yoy_points) > 1 else None
            metrics = calculate_metrics(last=latest.close, prev_close=prev, history=yoy_points)
            sparkline_points = [
                SparkPoint(t=point.t, v=_round_value(point.close, instrument.precision) or point.close)
                for point in yoy_points[-30:]
            ]

            items.append(
                SummaryItem(
                    id=instrument.id,
                    name=instrument.name_sv,
                    unit=instrument.unit_label,
                    price_type=instrument.price_type,
                    last=_round_value(latest.close, instrument.precision),
                    day_abs=_round_value(metrics["day_abs"], instrument.precision),
                    day_pct=_round_value(metrics["day_pct"], 2),
                    w1_pct=_round_value(metrics["w1_pct"], 2),
                    ytd_pct=_round_value(metrics["ytd_pct"], 2),
                    y1_pct=_round_value(metrics["y1_pct"], 2),
                    timestamp_local=latest.t,
                    is_stale=False,
                    sparkline=sparkline_points,
                )
            )
        except Exception as exc:
            errors[instrument.ticker] = str(exc)
            items.append(_empty_item(instrument))

    return items, errors


def fetch_series_for_instrument(instrument: InstrumentConfig, range_key: str) -> list[SparkPoint]:
    raw_points = fred.fetch_series(series_id=instrument.ticker)
    yoy_points = _to_yoy_points(raw_points)
    filtered_points = _filter_by_range(yoy_points, range_key)
    return [SparkPoint(t=point.t, v=round(point.close, instrument.precision)) for point in filtered_points]
