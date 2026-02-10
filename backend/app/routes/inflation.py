from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query

from app.core.cache import cache
from app.core.config import load_instruments
from app.services.inflation_data import fetch_series_for_instrument, fetch_summary_for_instruments

router = APIRouter(prefix="/api/inflation", tags=["inflation"])


@router.get("/summary")
def inflation_summary():
    cache_key = "inflation_summary"
    cached = cache.get(cache_key)
    if cached is not None:
        return {
            "items": cached.value,
            "meta": {
                "source": "fred",
                "cached": True,
                "fetched_at": cached.fetched_at,
            },
        }

    instruments = [i for i in load_instruments() if i.module == "inflation"]
    items, _errors = fetch_summary_for_instruments(instruments)
    fetched_at = datetime.now(timezone.utc)
    has_fresh_values = any(item.last is not None for item in items)
    cache.set(cache_key, items, fetched_at=fetched_at, update_last_update=has_fresh_values)
    return {
        "items": items,
        "meta": {
            "source": "fred",
            "cached": False,
            "fetched_at": fetched_at,
        },
    }


@router.get("/series")
def inflation_series(id: str, range: str = Query(default="3m", pattern="^(1m|3m|6m|1y)$")):
    cache_key = f"inflation_series:{id}:{range}"
    cached = cache.get(cache_key)
    if cached is not None:
        return {
            "id": id,
            "range": range,
            "points": cached.value,
            "meta": {
                "source": "fred",
                "cached": True,
                "fetched_at": cached.fetched_at,
            },
        }

    instruments = [i for i in load_instruments() if i.module == "inflation"]
    instrument = next((item for item in instruments if item.id == id), None)
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"Unknown inflation id: {id}")

    points = fetch_series_for_instrument(instrument, range)
    fetched_at = datetime.now(timezone.utc)
    cache.set(cache_key, points, fetched_at=fetched_at, update_last_update=bool(points))
    return {
        "id": id,
        "range": range,
        "points": points,
        "meta": {
            "source": "fred",
            "cached": False,
            "fetched_at": fetched_at,
        },
    }
