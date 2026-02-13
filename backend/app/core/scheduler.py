from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from app.core.cache import cache
from app.core.config import load_instruments
from app.db.repository import (
    complete_job_run,
    create_job_run,
    record_provider_stats_snapshot,
    replace_series_points,
    store_summary_items,
    upsert_instruments,
)
from app.db.session import session_scope
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

    started_at = datetime.now(timezone.utc)
    fetched_at = started_at

    with session_scope() as session:
        instrument_ids = upsert_instruments(session, instruments)
        job_run = create_job_run(session, "cache_refresh", started_at)
        ok_count = 0
        fail_count = 0
        notes_parts: list[str] = []

        commodity_items, commodity_errors = fetch_market_summary_for_instruments(commodities)
        commodity_fresh = any(item.last is not None for item in commodity_items)
        cache.set(
            "commodities_summary",
            commodity_items,
            fetched_at=fetched_at,
            update_last_update=commodity_fresh,
            module="commodities",
        )
        store_summary_items(session, instrument_ids, commodity_items, fetched_at)
        ok_count += len(commodity_items) - len(commodity_errors)
        fail_count += len(commodity_errors)
        if commodity_errors:
            notes_parts.append(f"commodities_errors={len(commodity_errors)}")

        mag7_items, mag7_errors = fetch_market_summary_for_instruments(mag7)
        mag7_fresh = any(item.last is not None for item in mag7_items)
        cache.set("mag7_summary", mag7_items, fetched_at=fetched_at, update_last_update=mag7_fresh, module="mag7")
        store_summary_items(session, instrument_ids, mag7_items, fetched_at)
        ok_count += len(mag7_items) - len(mag7_errors)
        fail_count += len(mag7_errors)
        if mag7_errors:
            notes_parts.append(f"mag7_errors={len(mag7_errors)}")

        inflation_items, inflation_errors = fetch_inflation_summary_for_instruments(inflation)
        inflation_fresh = any(item.last is not None for item in inflation_items)
        cache.set(
            "inflation_summary",
            inflation_items,
            fetched_at=fetched_at,
            update_last_update=inflation_fresh,
            module="inflation",
        )
        store_summary_items(session, instrument_ids, inflation_items, fetched_at)
        ok_count += len(inflation_items) - len(inflation_errors)
        fail_count += len(inflation_errors)
        if inflation_errors:
            notes_parts.append(f"inflation_errors={len(inflation_errors)}")

        for instrument in commodities:
            for range_key in COMMODITY_RANGES:
                try:
                    points = fetch_market_series_for_instrument(instrument, range_key)
                    cache.set(f"series:{instrument.id}:{range_key}", points, fetched_at=fetched_at, update_last_update=False)
                    instrument_id = instrument_ids.get(instrument.id)
                    if instrument_id is not None:
                        replace_series_points(
                            session,
                            instrument_id=instrument_id,
                            series_type="commodities",
                            range_key=range_key,
                            points=points,
                            fetched_at=fetched_at,
                        )
                except Exception:
                    fail_count += 1
                    logger.exception("Commodity series refresh failed for %s range=%s", instrument.id, range_key)

        for instrument in inflation:
            for range_key in INFLATION_RANGES:
                try:
                    points = fetch_inflation_series_for_instrument(instrument, range_key)
                    cache.set(f"inflation_series:{instrument.id}:{range_key}", points, fetched_at=fetched_at, update_last_update=False)
                    instrument_id = instrument_ids.get(instrument.id)
                    if instrument_id is not None:
                        replace_series_points(
                            session,
                            instrument_id=instrument_id,
                            series_type="inflation",
                            range_key=range_key,
                            points=points,
                            fetched_at=fetched_at,
                        )
                except Exception:
                    fail_count += 1
                    logger.exception("Inflation series refresh failed for %s range=%s", instrument.id, range_key)

        record_provider_stats_snapshot(session, created_at=datetime.now(timezone.utc))
        finished_at = datetime.now(timezone.utc)
        complete_job_run(
            session,
            job_run,
            finished_at=finished_at,
            status="partial" if fail_count > 0 else "success",
            ok_count=ok_count,
            fail_count=fail_count,
            notes=", ".join(notes_parts) if notes_parts else None,
        )


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
