from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math

from app.providers import yahoo_finance


SEK_TO_THB_FALLBACK_RATE = 3.43
SEK_TO_THB_TICKER = "THBSEK=X"


@dataclass(frozen=True)
class ExchangeRate:
    base: str
    quote: str
    rate: float
    fetched_at: datetime
    source: str
    ticker: str
    is_fallback: bool = False
    stale_reason: str | None = None


_sek_to_thb = ExchangeRate(
    base="SEK",
    quote="THB",
    rate=SEK_TO_THB_FALLBACK_RATE,
    fetched_at=datetime.now(timezone.utc),
    source="fallback",
    ticker=SEK_TO_THB_TICKER,
    is_fallback=True,
    stale_reason="not_fetched",
)


def refresh_startup_exchange_rates() -> None:
    global _sek_to_thb

    snapshots, errors = yahoo_finance.fetch_quotes_with_history([SEK_TO_THB_TICKER], period="5d")
    snapshot = snapshots.get(SEK_TO_THB_TICKER)
    if snapshot is None or snapshot.last is None or not math.isfinite(snapshot.last) or snapshot.last <= 0:
        _sek_to_thb = _sek_to_thb.__class__(
            base="SEK",
            quote="THB",
            rate=SEK_TO_THB_FALLBACK_RATE,
            fetched_at=datetime.now(timezone.utc),
            source="fallback",
            ticker=SEK_TO_THB_TICKER,
            is_fallback=True,
            stale_reason=errors.get(SEK_TO_THB_TICKER) or "no_valid_rate",
        )
        return

    _sek_to_thb = ExchangeRate(
        base="SEK",
        quote="THB",
        rate=round(1 / snapshot.last, 6),
        fetched_at=snapshot.timestamp or datetime.now(timezone.utc),
        source="yahoo_finance",
        ticker=SEK_TO_THB_TICKER,
    )


def sek_to_thb_rate() -> ExchangeRate:
    return _sek_to_thb
