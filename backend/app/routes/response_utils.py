from __future__ import annotations

from datetime import datetime
from datetime import timezone

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


def age_seconds_since(value: datetime) -> int:
    now = datetime.now(timezone.utc)
    return max(0, int((now - value).total_seconds()))


def stale_reason_for_items(items: list[SummaryItem], global_stale: bool) -> str:
    if global_stale:
        return "global_threshold"
    if any(item.is_stale for item in items):
        return "provider_error"
    return "none"
