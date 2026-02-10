from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import InstrumentConfig
from app.providers.fred import FredPoint
from app.services.inflation_data import fetch_series_for_instrument, fetch_summary_for_instruments


def _instrument() -> InstrumentConfig:
    return InstrumentConfig(
        id="inflation_us",
        name_sv="USA KPI (YoY)",
        ticker="CPIAUCSL",
        unit_label="%",
        price_type="KPI",
        badge_symbol="US",
        precision=2,
        display_group="cards",
        sort_order=1,
        module="inflation",
    )


def test_inflation_summary_computes_yoy(monkeypatch):
    instrument = _instrument()
    data = [
        FredPoint(t=datetime(2024, 1, 1, tzinfo=timezone.utc), value=300.0),
        FredPoint(t=datetime(2025, 1, 1, tzinfo=timezone.utc), value=306.0),
        FredPoint(t=datetime(2026, 1, 1, tzinfo=timezone.utc), value=312.0),
    ]
    monkeypatch.setattr("app.services.inflation_data.fred.fetch_series", lambda series_id: data)

    items, errors = fetch_summary_for_instruments([instrument])
    assert errors == {}
    assert len(items) == 1
    assert items[0].is_stale is False
    assert items[0].last == 1.96
    assert len(items[0].sparkline) == 2


def test_inflation_series_respects_range(monkeypatch):
    instrument = _instrument()
    data = [
        FredPoint(t=datetime(2024, 1, 1, tzinfo=timezone.utc), value=300.0),
        FredPoint(t=datetime(2024, 7, 1, tzinfo=timezone.utc), value=302.0),
        FredPoint(t=datetime(2025, 1, 1, tzinfo=timezone.utc), value=303.0),
        FredPoint(t=datetime(2025, 7, 1, tzinfo=timezone.utc), value=306.0),
        FredPoint(t=datetime(2026, 1, 1, tzinfo=timezone.utc), value=309.0),
        FredPoint(t=datetime(2026, 7, 1, tzinfo=timezone.utc), value=312.0),
    ]
    monkeypatch.setattr("app.services.inflation_data.fred.fetch_series", lambda series_id: data)

    points = fetch_series_for_instrument(instrument, "6m")
    assert len(points) == 2
    assert points[-1].v == 1.96
