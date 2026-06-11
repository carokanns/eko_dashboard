from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.summary import SparkPoint


class PortfolioHolding(BaseModel):
    id: str
    name: str
    short_name: Optional[str] = None
    isin: Optional[str] = None
    instrument_type: str
    market: Optional[str] = None
    currency: Optional[str] = None
    quantity: float
    current_value: float
    acquisition_price_sek: Optional[float] = None
    acquisition_value: Optional[float] = None
    gain_abs: Optional[float] = None
    gain_pct: Optional[float] = None
    ticker: Optional[str] = None
    chart_source: Optional[str] = None
    chart_label: Optional[str] = None
    has_chart: bool = False
    last: Optional[float] = None
    day_abs: Optional[float] = None
    day_pct: Optional[float] = None
    w1_pct: Optional[float] = None
    ytd_pct: Optional[float] = None
    y1_pct: Optional[float] = None
    timestamp_local: Optional[datetime] = None
    is_stale: bool = True
    sparkline: list[SparkPoint] = Field(default_factory=list)


class PortfolioTotals(BaseModel):
    current_value: float
    acquisition_value: float
    gain_abs: float
    gain_pct: Optional[float] = None
    holding_count: int
    chart_count: int


class PortfolioSummaryResponse(BaseModel):
    enabled: bool
    holdings: list[PortfolioHolding]
    totals: PortfolioTotals
    meta: dict[str, object]
