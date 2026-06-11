from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.core.cache import cache
from app.core.settings import local_portfolio_enabled
from app.models.portfolio import PortfolioSummaryResponse
from app.routes.response_utils import age_seconds_since, to_stockholm_timestamp
from app.services.portfolio_data import (
    build_portfolio_totals,
    enrich_holdings_with_market_data,
    fetch_portfolio_series,
    load_portfolio_holdings,
    portfolio_data_dir,
    portfolio_meta,
    save_portfolio_snapshot,
    _latest_position_file,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/status")
def portfolio_status():
    enabled = local_portfolio_enabled()
    data_dir = portfolio_data_dir()
    source_file = _latest_position_file(data_dir) if enabled and data_dir.exists() else None
    return {
        "enabled": enabled and source_file is not None,
        "configured": enabled,
        "has_data": source_file is not None,
    }


def _require_enabled() -> None:
    if not local_portfolio_enabled():
        raise HTTPException(status_code=404, detail="Local portfolio is not enabled.")


@router.get("/summary", response_model=PortfolioSummaryResponse)
def portfolio_summary():
    _require_enabled()
    data_dir = portfolio_data_dir()
    source_file = _latest_position_file(data_dir)
    if source_file is None:
        raise HTTPException(status_code=404, detail="No local Avanza position export found.")

    cache_key = f"portfolio_summary:{source_file}:{source_file.stat().st_mtime_ns}"
    cached = cache.get(cache_key)
    if cached is not None:
        cached_payload = cached.value
        return cached_payload.model_copy(
            update={
                "meta": {
                    **cached_payload.meta,
                    "cached": True,
                    "fetched_at": to_stockholm_timestamp(cached.fetched_at),
                    "age_seconds": age_seconds_since(cached.fetched_at),
                }
            }
        )

    fetched_at = datetime.now(timezone.utc)
    base_holdings = load_portfolio_holdings(data_dir)
    save_portfolio_snapshot(data_dir, source_file, base_holdings)
    holdings = enrich_holdings_with_market_data(base_holdings)
    totals = build_portfolio_totals(holdings)
    payload = PortfolioSummaryResponse(
        enabled=True,
        holdings=holdings,
        totals=totals,
        meta={
            **portfolio_meta(cached=False, fetched_at=to_stockholm_timestamp(fetched_at), data_dir=data_dir, source_file=source_file),
            "age_seconds": age_seconds_since(fetched_at),
        },
    )
    cache.set(cache_key, payload, fetched_at=fetched_at, update_last_update=False)
    return payload


@router.get("/series")
def portfolio_series(id: str, range: str = Query(default="1m", pattern="^(1m|3m|6m|1y)$")):
    _require_enabled()
    holdings = load_portfolio_holdings()
    holding = next((item for item in holdings if item.id == id), None)
    if holding is None:
        raise HTTPException(status_code=404, detail=f"Unknown portfolio holding id: {id}")
    if not holding.ticker:
        return {
            "id": id,
            "range": range,
            "points": [],
            "meta": {
                "source": "local_avanza_export",
                "cached": False,
                "fetched_at": to_stockholm_timestamp(datetime.now(timezone.utc)),
                "stale_reason": "no_ticker_mapping",
                "age_seconds": 0,
            },
        }

    cache_key = f"series:portfolio:{id}:{range}:{holding.ticker}"
    cached = cache.get(cache_key)
    if cached is not None:
        return {
            "id": id,
            "range": range,
            "points": cached.value,
            "meta": {
                "source": "yahoo_finance",
                "cached": True,
                "fetched_at": to_stockholm_timestamp(cached.fetched_at),
                "stale_reason": "none",
                "age_seconds": age_seconds_since(cached.fetched_at),
            },
        }

    points = fetch_portfolio_series(holding, range)
    fetched_at = datetime.now(timezone.utc)
    cache.set(cache_key, points, fetched_at=fetched_at, update_last_update=False)
    return {
        "id": id,
        "range": range,
        "points": points,
        "meta": {
            "source": "yahoo_finance",
            "cached": False,
            "fetched_at": to_stockholm_timestamp(fetched_at),
            "stale_reason": "none" if points else "provider_error",
            "age_seconds": age_seconds_since(fetched_at),
        },
    }
