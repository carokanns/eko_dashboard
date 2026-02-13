from __future__ import annotations

from fastapi import APIRouter

from app.core.config import load_instruments

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
def config_summary():
    instruments = load_instruments()
    return {
        "instruments": [
            {
                "id": item.id,
                "name_sv": item.name_sv,
                "ticker": item.ticker,
                "unit_label": item.unit_label,
                "price_type": item.price_type,
                "badge_symbol": item.badge_symbol,
                "precision": item.precision,
                "display_group": item.display_group,
                "sort_order": item.sort_order,
                "module": item.module,
            }
            for item in instruments
        ]
    }
