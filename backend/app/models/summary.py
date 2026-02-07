from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SparkPoint(BaseModel):
    t: datetime
    v: float


class SummaryItem(BaseModel):
    id: str
    name: str
    unit: Optional[str] = None
    price_type: Optional[str] = None
    last: Optional[float] = None
    day_abs: Optional[float] = None
    day_pct: Optional[float] = None
    w1_pct: Optional[float] = None
    ytd_pct: Optional[float] = None
    y1_pct: Optional[float] = None
    timestamp_local: Optional[datetime] = None
    is_stale: bool = True
    sparkline: List[SparkPoint] = Field(default_factory=list)
