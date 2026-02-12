from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from app.core.cache import cache
from app.core.config import load_instruments
from app.services.inflation_data import fetch_series_for_instrument as fetch_inflation_series_for_instrument
from app.services.inflation_data import fetch_summary_for_instruments as fetch_inflation_summary_for_instruments
from app.services.market_data import fetch_series_for_instrument as fetch_market_series_for_instrument
from app.services.market_data import fetch_summary_for_instruments as fetch_market_summary_for_instruments


logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 60
COMMODITY_RANGES = ("1m", "3m", "1y")
INFLATION_RANGES = ("1m", "3m", "6m", "1y")


def scheduler_enabled() -> bool:
    return os.getenv("APP_DISABLE_SCHEDULER", "0").lower() not in {"1", "true", "yes", "on"}


def _refresh_once_sync() -> None:
    instruments = load_instruments()
    commodities = [item for item in instruments if item.module == "commodities"]
    mag7 = [item for item in instruments if item.module == "mag7"]
    inflation = [item for item in instruments if item.module == "inflation"]

    fetched_at = datetime.now(timezone.utc)

    commodity_items, _commodity_errors = fetch_market_summary_for_instruments(commodities)
    commodity_fresh = any(item.last is not None for item in commodity_items)
    cache.set("commodities_summary", commodity_items, fetched_at=fetched_at, update_last_update=commodity_fresh)

    mag7_items, _mag7_errors = fetch_market_summary_for_instruments(mag7)
    mag7_fresh = any(item.last is not None for item in mag7_items)
    cache.set("mag7_summary", mag7_items, fetched_at=fetched_at, update_last_update=mag7_fresh)

    inflation_items, _inflation_errors = fetch_inflation_summary_for_instruments(inflation)
    inflation_fresh = any(item.last is not None for item in inflation_items)
    cache.set("inflation_summary", inflation_items, fetched_at=fetched_at, update_last_update=inflation_fresh)

    for instrument in commodities:
        for range_key in COMMODITY_RANGES:
            try:
                points = fetch_market_series_for_instrument(instrument, range_key)
                cache.set(f"series:{instrument.id}:{range_key}", points, fetched_at=fetched_at, update_last_update=False)
            except Exception:
                logger.exception("Commodity series refresh failed for %s range=%s", instrument.id, range_key)

    for instrument in inflation:
        for range_key in INFLATION_RANGES:
            try:
                points = fetch_inflation_series_for_instrument(instrument, range_key)
                cache.set(f"inflation_series:{instrument.id}:{range_key}", points, fetched_at=fetched_at, update_last_update=False)
            except Exception:
                logger.exception("Inflation series refresh failed for %s range=%s", instrument.id, range_key)


class CacheRefreshScheduler:
    def __init__(self, interval_seconds: int = REFRESH_INTERVAL_SECONDS) -> None:
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if not scheduler_enabled() or self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="cache-refresh-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        await self._task
        self._task = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await asyncio.to_thread(_refresh_once_sync)
            except Exception:
                logger.exception("Scheduled cache refresh failed")

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                continue


scheduler = CacheRefreshScheduler()
