from __future__ import annotations

from datetime import datetime, timezone
import os

from app.core.config import InstrumentConfig
from app.core.scheduler import _refresh_once_sync
from app.db.migrations import upgrade_to_head
from app.db.session import reset_database_engine
from app.models.summary import SparkPoint, SummaryItem


def _instrument(item_id: str, module: str, ticker: str) -> InstrumentConfig:
    return InstrumentConfig(
        id=item_id,
        name_sv=item_id,
        ticker=ticker,
        unit_label="USD",
        price_type="Spot",
        badge_symbol=item_id,
        precision=2,
        display_group="cards",
        sort_order=1,
        module=module,
    )


def _summary_item(item_id: str) -> SummaryItem:
    now = datetime.now(timezone.utc)
    return SummaryItem(
        id=item_id,
        name=item_id,
        unit="USD",
        price_type="Spot",
        last=101.0,
        day_abs=1.0,
        day_pct=1.0,
        w1_pct=2.0,
        ytd_pct=3.0,
        y1_pct=4.0,
        timestamp_local=now,
        is_stale=False,
        sparkline=[SparkPoint(t=now, v=101.0)],
    )


def _setup_scheduler_db(monkeypatch, tmp_path) -> str:
    db_file = tmp_path / "scheduler-logging-test.db"
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{db_file}")
    reset_database_engine()
    upgrade_to_head()
    return str(db_file)


def _base_instruments() -> list[InstrumentConfig]:
    return [
        _instrument("brent", "commodities", "BZ=F"),
        _instrument("aapl", "mag7", "AAPL"),
        _instrument("inflation_us", "inflation", "CPIAUCSL"),
    ]


def test_scheduler_logs_structured_success(monkeypatch, tmp_path):
    db_file = _setup_scheduler_db(monkeypatch, tmp_path)
    instruments = _base_instruments()
    info_events: list[tuple[str, dict[str, object]]] = []
    error_events: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr("app.core.scheduler._log_info", lambda event, **fields: info_events.append((event, fields)))
    monkeypatch.setattr(
        "app.core.scheduler._log_exception",
        lambda event, **fields: error_events.append((event, fields)),
    )

    monkeypatch.setattr("app.core.scheduler.load_instruments", lambda: instruments)
    monkeypatch.setattr(
        "app.core.scheduler.fetch_market_summary_for_instruments",
        lambda items: ([_summary_item(item.id) for item in items], {}),
    )
    monkeypatch.setattr(
        "app.core.scheduler.fetch_inflation_summary_for_instruments",
        lambda items: ([_summary_item(item.id) for item in items], {}),
    )
    monkeypatch.setattr(
        "app.core.scheduler.fetch_market_series_for_instrument",
        lambda _instrument, _range: [SparkPoint(t=datetime.now(timezone.utc), v=100.0)],
    )
    monkeypatch.setattr(
        "app.core.scheduler.fetch_inflation_series_for_instrument",
        lambda _instrument, _range: [SparkPoint(t=datetime.now(timezone.utc), v=2.1)],
    )

    _refresh_once_sync()

    completion_events = [fields for event, fields in info_events if event == "scheduler.refresh.completed"]
    assert len(completion_events) == 1
    completion = completion_events[0]
    assert completion["status"] == "success"
    assert completion["fail_count"] == 0
    assert completion["ok_count"] > 0
    assert completion["duration_ms"] >= 0

    module_events = [fields for event, fields in info_events if event == "scheduler.refresh.module_summary"]
    assert len(module_events) == 3
    assert len(error_events) == 0

    reset_database_engine()
    if os.path.exists(db_file):
        os.remove(db_file)


def test_scheduler_logs_structured_series_failures(monkeypatch, tmp_path):
    db_file = _setup_scheduler_db(monkeypatch, tmp_path)
    instruments = _base_instruments()
    info_events: list[tuple[str, dict[str, object]]] = []
    error_events: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr("app.core.scheduler._log_info", lambda event, **fields: info_events.append((event, fields)))
    monkeypatch.setattr(
        "app.core.scheduler._log_exception",
        lambda event, **fields: error_events.append((event, fields)),
    )

    monkeypatch.setattr("app.core.scheduler.load_instruments", lambda: instruments)
    monkeypatch.setattr(
        "app.core.scheduler.fetch_market_summary_for_instruments",
        lambda items: ([_summary_item(item.id) for item in items], {}),
    )
    monkeypatch.setattr(
        "app.core.scheduler.fetch_inflation_summary_for_instruments",
        lambda items: ([_summary_item(item.id) for item in items], {}),
    )

    def _broken_market_series(_instrument, _range):
        raise RuntimeError("forced series error")

    monkeypatch.setattr("app.core.scheduler.fetch_market_series_for_instrument", _broken_market_series)
    monkeypatch.setattr(
        "app.core.scheduler.fetch_inflation_series_for_instrument",
        lambda _instrument, _range: [SparkPoint(t=datetime.now(timezone.utc), v=2.1)],
    )

    _refresh_once_sync()

    series_failures = [fields for event, fields in error_events if event == "scheduler.refresh.series_failed"]
    assert len(series_failures) == 3
    assert all(record["module"] == "commodities" for record in series_failures)
    assert all(record["instrument_id"] == "brent" for record in series_failures)

    completion_events = [fields for event, fields in info_events if event == "scheduler.refresh.completed"]
    assert len(completion_events) == 1
    assert completion_events[0]["status"] == "partial"
    assert completion_events[0]["fail_count"] >= 3

    reset_database_engine()
    if os.path.exists(db_file):
        os.remove(db_file)
