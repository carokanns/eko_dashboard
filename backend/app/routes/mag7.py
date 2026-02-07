from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.cache import cache
from app.core.config import load_instruments
from app.services.market_data import fetch_summary_for_instruments

router = APIRouter(prefix="/api/mag7", tags=["mag7"])


@router.get("/summary")
def mag7_summary():
    cache_key = "mag7_summary"
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

    instruments = [i for i in load_instruments() if i.module == "mag7"]
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
