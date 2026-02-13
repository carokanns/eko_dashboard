from __future__ import annotations

from datetime import datetime

from app.core.time import to_stockholm
from app.models.summary import SummaryItem


def to_stockholm_timestamp(value: datetime) -> datetime:
    return to_stockholm(value)


def normalize_summary_items(items: list[SummaryItem], force_stale: bool) -> list[SummaryItem]:
    return [
        item.model_copy(
            update={
                "timestamp_local": to_stockholm(item.timestamp_local),
                "is_stale": force_stale or item.is_stale,
            }
        )
        for item in items
    ]
