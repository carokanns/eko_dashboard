from __future__ import annotations

from fastapi import APIRouter

from app.core.config import load_instruments
from app.services.summary_builder import build_placeholder_summary

router = APIRouter(prefix="/api/commodities", tags=["commodities"])


@router.get("/summary")
def commodities_summary():
    instruments = [i for i in load_instruments() if i.module == "commodities"]
    return {
        "items": build_placeholder_summary(instruments),
    }


@router.get("/series")
def commodities_series(id: str, range: str = "1m"):
    return {
        "id": id,
        "range": range,
        "points": [],
    }
