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
    latest_portfolio_source_files,
    latest_portfolio_refresh_files,
    load_portfolio_accounts_from_ledger,
    load_portfolio_holdings_from_ledger,
    portfolio_base_data_dir,
    portfolio_ledger_path,
    portfolio_meta,
    update_portfolio_ledger_from_transactions,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/status")
def portfolio_status():
    enabled = local_portfolio_enabled()
    data_dir = portfolio_base_data_dir()
    source_files = latest_portfolio_source_files(data_dir) if enabled else []
    has_ledger = portfolio_ledger_path(data_dir).exists() if enabled else False
    return {
        "enabled": enabled and (bool(source_files) or has_ledger),
        "configured": enabled,
        "has_data": bool(source_files) or has_ledger,
    }


def _require_enabled() -> None:
    if not local_portfolio_enabled():
        raise HTTPException(status_code=404, detail="Local portfolio is not enabled.")


@router.get("/summary", response_model=PortfolioSummaryResponse)
def portfolio_summary():
    _require_enabled()
    data_dir = portfolio_base_data_dir()
    source_files = latest_portfolio_source_files(data_dir)
    has_ledger = portfolio_ledger_path(data_dir).exists()
    if not source_files and not has_ledger:
        raise HTTPException(status_code=404, detail="No local Avanza position export found.")

    ledger_update = update_portfolio_ledger_from_transactions(data_dir)
    refresh_files = latest_portfolio_refresh_files(data_dir)
    ledger_path = portfolio_ledger_path(data_dir)
    cache_parts = [f"ledger:{ledger_path}:{ledger_path.stat().st_mtime_ns}" if ledger_path.exists() else "ledger:missing"]
    cache_parts.extend(f"{owner_id}:{kind}:{source_file}:{source_file.stat().st_mtime_ns}" for owner_id, _, _, kind, source_file in refresh_files)
    cache_key = f"portfolio_summary:{'|'.join(cache_parts)}"
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
    base_holdings = load_portfolio_holdings_from_ledger(data_dir)
    holdings = enrich_holdings_with_market_data(base_holdings)
    totals = build_portfolio_totals(holdings)
    accounts = load_portfolio_accounts_from_ledger(data_dir)
    payload = PortfolioSummaryResponse(
        enabled=True,
        holdings=holdings,
        totals=totals,
        accounts=accounts,
        meta={
            **portfolio_meta(
                cached=False,
                fetched_at=to_stockholm_timestamp(fetched_at),
                data_dir=data_dir,
                source_files=[(owner_id, source_file) for owner_id, _, _, source_file in source_files],
                refresh_files=[(owner_id, kind, source_file) for owner_id, _, _, kind, source_file in refresh_files],
            ),
            "ledger_file": str(ledger_path),
            "ledger_applied_transactions": ledger_update["applied_count"],
            "age_seconds": age_seconds_since(fetched_at),
        },
    )
    cache.set(cache_key, payload, fetched_at=fetched_at, update_last_update=False)
    return payload


@router.get("/series")
def portfolio_series(id: str, range: str = Query(default="1m", pattern="^(1m|3m|6m|1y)$")):
    _require_enabled()
    holdings = load_portfolio_holdings_from_ledger()
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
