from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


STOCKHOLM_TZ = ZoneInfo("Europe/Stockholm")


def to_stockholm(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(STOCKHOLM_TZ)
