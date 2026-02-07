from __future__ import annotations

from fastapi import APIRouter

from app.core.config import load_instruments
from app.services.summary_builder import build_placeholder_summary

router = APIRouter(prefix="/api/mag7", tags=["mag7"])


@router.get("/summary")
def mag7_summary():
    instruments = [i for i in load_instruments() if i.module == "mag7"]
    return {
        "items": build_placeholder_summary(instruments),
    }
