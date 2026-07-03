from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
import json
import math
from urllib.error import URLError
from urllib.request import Request, urlopen


SEK_TO_THB_FALLBACK_RATE = 3.43
SEK_TO_THB_ENDPOINT = "https://api.frankfurter.dev/v1/latest?base=SEK&symbols=THB"
SEK_TO_THB_PAIR = "SEKTHB"


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
    ticker=SEK_TO_THB_PAIR,
    is_fallback=True,
    stale_reason="not_fetched",
)


def refresh_startup_exchange_rates() -> None:
    global _sek_to_thb

    try:
        request = Request(SEK_TO_THB_ENDPOINT, headers={"User-Agent": "EkonomiDashboard/1.0"})
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        rate = float(payload["rates"]["THB"])
        rate_date = datetime.combine(datetime.fromisoformat(payload["date"]).date(), time.min, tzinfo=timezone.utc)
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("Frankfurter returned an invalid SEK to THB rate.")
    except (KeyError, TypeError, ValueError, URLError, TimeoutError, OSError) as exc:
        _sek_to_thb = _sek_to_thb.__class__(
            base="SEK",
            quote="THB",
            rate=SEK_TO_THB_FALLBACK_RATE,
            fetched_at=datetime.now(timezone.utc),
            source="fallback",
            ticker=SEK_TO_THB_PAIR,
            is_fallback=True,
            stale_reason=str(exc) or "frankfurter_error",
        )
        return

    _sek_to_thb = ExchangeRate(
        base="SEK",
        quote="THB",
        rate=round(rate, 6),
        fetched_at=rate_date,
        source="frankfurter",
        ticker=SEK_TO_THB_PAIR,
    )


def sek_to_thb_rate() -> ExchangeRate:
    return _sek_to_thb
