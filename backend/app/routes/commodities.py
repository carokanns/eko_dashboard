from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query

from app.core.cache import cache
from app.core.config import load_instruments
from app.services.market_data import fetch_series_for_instrument, fetch_summary_for_instruments

router = APIRouter(prefix="/api/commodities", tags=["commodities"])


@router.get("/summary")
def commodities_summary():
    cache_key = "commodities_summary"
    cached = cache.get(cache_key)
    if cached is not None:
        return {
            "items": cached.value,
            "meta": {
                "source": "yahoo_finance",
                "cached": True,
                "fetched_at": cached.fetched_at,
            },
        }

    instruments = [i for i in load_instruments() if i.module == "commodities"]
    items, _errors = fetch_summary_for_instruments(instruments)
    fetched_at = datetime.now(timezone.utc)
    has_fresh_values = any(item.last is not None for item in items)
    cache.set(cache_key, items, fetched_at=fetched_at, update_last_update=has_fresh_values)
    return {
        "items": items,
        "meta": {
            "source": "yahoo_finance",
            "cached": False,
            "fetched_at": fetched_at,
        },
    }


@router.get("/series")
def commodities_series(id: str, range: str = Query(default="1m", pattern="^(1m|3m|1y)$")):
    cache_key = f"series:{id}:{range}"
    cached = cache.get(cache_key)
    if cached is not None:
        return {
            "id": id,
            "range": range,
            "points": cached.value,
            "meta": {
                "source": "yahoo_finance",
                "cached": True,
                "fetched_at": cached.fetched_at,
            },
        }

    instruments = [i for i in load_instruments() if i.module == "commodities"]
    instrument = next((item for item in instruments if item.id == id), None)
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"Unknown commodity id: {id}")

    points = fetch_series_for_instrument(instrument, range)
    fetched_at = datetime.now(timezone.utc)
    cache.set(cache_key, points, fetched_at=fetched_at, update_last_update=bool(points))
    return {
        "id": id,
        "range": range,
        "points": points,
        "meta": {
            "source": "yahoo_finance",
            "cached": False,
            "fetched_at": fetched_at,
        },
    }
