from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import InstrumentConfig
from app.models.summary import SummaryItem


def build_placeholder_summary(items: list[InstrumentConfig]) -> list[SummaryItem]:
    now = datetime.now(timezone.utc)
    return [
        SummaryItem(
            id=item.id,
            name=item.name_sv,
            unit=item.unit_label,
            price_type=item.price_type,
            last=None,
            day_abs=None,
            day_pct=None,
            w1_pct=None,
            ytd_pct=None,
            y1_pct=None,
            timestamp_local=now,
            is_stale=True,
            sparkline=[],
        )
        for item in items
    ]
