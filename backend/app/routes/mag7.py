from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.cache import cache
from app.core.config import load_instruments
from app.routes.response_utils import normalize_summary_items, to_stockholm_timestamp
from app.services.market_data import fetch_summary_for_instruments

router = APIRouter(prefix="/api/mag7", tags=["mag7"])


@router.get("/summary")
def mag7_summary():
    cache_key = "mag7_summary"
    cached = cache.get(cache_key)
    if cached is not None:
        items = normalize_summary_items(cached.value, force_stale=cache.is_globally_stale())
        return {
            "items": items,
            "meta": {
                "source": "yahoo_finance",
                "cached": True,
                "fetched_at": to_stockholm_timestamp(cached.fetched_at),
            },
        }

    instruments = [i for i in load_instruments() if i.module == "mag7"]
    items, _errors = fetch_summary_for_instruments(instruments)
    fetched_at = datetime.now(timezone.utc)
    has_fresh_values = any(item.last is not None for item in items)
    cache.set(cache_key, items, fetched_at=fetched_at, update_last_update=has_fresh_values)
    normalized_items = normalize_summary_items(items, force_stale=cache.is_globally_stale())
    return {
        "items": normalized_items,
        "meta": {
            "source": "yahoo_finance",
            "cached": False,
            "fetched_at": to_stockholm_timestamp(fetched_at),
        },
    }
