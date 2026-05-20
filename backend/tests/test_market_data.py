from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

from app.providers.yahoo_finance import HistoryPoint, _extract_history_points
from app.services.market_data import calculate_metrics


def test_calculate_metrics_with_full_history():
    now = datetime.now(timezone.utc)
    history = [
        HistoryPoint(t=now - timedelta(days=400), close=80.0),
        HistoryPoint(t=now - timedelta(days=200), close=90.0),
        HistoryPoint(t=now - timedelta(days=20), close=95.0),
        HistoryPoint(t=now - timedelta(days=8), close=99.0),
        HistoryPoint(t=now - timedelta(days=1), close=100.0),
    ]

    metrics = calculate_metrics(last=100.0, prev_close=99.0, history=history)
    assert metrics["day_abs"] == 1.0
    assert metrics["day_pct"] is not None
    assert metrics["w1_pct"] is not None
    assert metrics["y1_pct"] is not None


def test_calculate_metrics_handles_missing_references():
    now = datetime.now(timezone.utc)
    history = [HistoryPoint(t=now - timedelta(days=2), close=100.0)]
    metrics = calculate_metrics(last=100.0, prev_close=None, history=history)
    assert metrics["day_abs"] is None
    assert metrics["day_pct"] is None
    assert metrics["w1_pct"] is None
    assert metrics["y1_pct"] is None


def test_extract_history_points_skips_nan_close_values():
    now = datetime.now(timezone.utc)

    class FakeCloseSeries:
        def items(self):
            return [(now - timedelta(days=1), 100.0), (now, math.nan)]

    class FakeDataFrame:
        def __getitem__(self, key):
            assert key == "Close"
            return FakeCloseSeries()

    points = _extract_history_points(FakeDataFrame())

    assert len(points) == 1
    assert points[0].close == 100.0
