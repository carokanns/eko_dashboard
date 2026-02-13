from __future__ import annotations

from datetime import datetime, timezone
import os

from app.core.config import InstrumentConfig
from app.core.scheduler import _refresh_once_sync
from app.db.migrations import upgrade_to_head
from app.db.models import JobRun, ProviderEvent, QuoteSnapshot, SeriesPoint
from app.db.session import reset_database_engine, session_scope
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


def test_refresh_persists_scheduler_data(monkeypatch, tmp_path):
    db_file = tmp_path / "scheduler-test.db"
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{db_file}")
    reset_database_engine()
    upgrade_to_head()

    instruments = [
        _instrument("brent", "commodities", "BZ=F"),
        _instrument("aapl", "mag7", "AAPL"),
        _instrument("inflation_us", "inflation", "CPIAUCSL"),
    ]

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

    with session_scope() as session:
        assert session.query(JobRun).count() == 1
        assert session.query(ProviderEvent).count() >= 0
        assert session.query(QuoteSnapshot).count() == len(instruments)
        assert session.query(SeriesPoint).count() > 0

    reset_database_engine()
    if os.path.exists(db_file):
        os.remove(db_file)
