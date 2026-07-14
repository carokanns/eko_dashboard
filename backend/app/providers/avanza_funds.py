from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
from urllib.request import Request, urlopen

from app.core.provider_monitor import provider_monitor
from app.core.rate_limit import rate_limiter
from app.core.settings import AVANZA_FUND_MAX_CALLS, AVANZA_FUND_PERIOD_SECONDS


FUND_LIST_URL = "https://www.avanza.se/_api/fund-guide/list?shouldCheckFundExcludedFromPromotion=true"
PRICE_CHART_URL = "https://www.avanza.se/_api/price-chart/stock/{orderbook_id}"
PROVIDER_NAME = "avanza_funds"
RANGE_TO_TIME_PERIOD = {
    "1m": "one_month",
    "3m": "three_months",
    "6m": "six_months",
    "1y": "one_year",
}


@dataclass(frozen=True)
class FundHistoryPoint:
    t: datetime
    close: float


@dataclass(frozen=True)
class FundNav:
    isin: str
    name: str
    nav: float
    nav_date: datetime | None
    currency: str | None
    orderbook_id: str | None
    history: list[FundHistoryPoint] = field(default_factory=list)


def _search_payload(name: str) -> dict[str, object]:
    return {
        "startIndex": 0,
        "maxNoResults": 20,
        "managedType": "ANY",
        "svanenMark": False,
        "commonRegionFilter": [],
        "otherRegionFilter": [],
        "alignmentFilter": [],
        "industryFilter": [],
        "fundTypeFilter": [],
        "interestTypeFilter": [],
        "sortField": "developmentThreeYears",
        "sortDirection": "DESCENDING",
        "name": name,
        "recommendedHoldingPeriodFilter": [],
        "companyFilter": [],
        "productInvolvementsFilter": [],
        "ratingFilter": [],
        "riskFilter": [],
        "currencyCodeFilter": [],
        "sustainabilityRatingFilter": [],
        "environmentalRatingFilter": [],
        "socialRatingFilter": [],
        "governanceRatingFilter": [],
        "sustainableDevelopmentGoalsAlignmentFilter": [],
        "euArticleTypeFilter": [],
        "maxTotalFee": None,
        "cashDividends": False,
    }


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _post_json(payload: dict[str, object]) -> dict[str, object]:
    request = Request(
        FUND_LIST_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Avanza returned an unexpected fund list response.")
    return parsed


def _get_json(url: str) -> dict[str, object]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Avanza returned an unexpected price chart response.")
    return parsed


def _fetch_fund_history(orderbook_id: str, range_key: str) -> list[FundHistoryPoint]:
    time_period = RANGE_TO_TIME_PERIOD.get(range_key)
    if time_period is None:
        raise ValueError(f"Unsupported fund history range: {range_key}")
    resolution = "&resolution=day" if range_key == "1m" else ""
    payload = _get_json(
        f"{PRICE_CHART_URL.format(orderbook_id=orderbook_id)}?timePeriod={time_period}{resolution}"
    )
    rows = payload.get("ohlc")
    if not isinstance(rows, list):
        raise ValueError("Avanza returned no fund price history.")
    points: list[FundHistoryPoint] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            timestamp = float(row["timestamp"])
            close = float(row["close"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(timestamp) or not math.isfinite(close) or close <= 0:
            continue
        points.append(FundHistoryPoint(t=datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc), close=close))
    return points


def fetch_fund_history(*, orderbook_id: str, range_key: str) -> list[FundHistoryPoint]:
    """Fetch public daily NAV history for one Avanza fund orderbook."""
    normalized_id = orderbook_id.strip()
    if not normalized_id:
        raise ValueError("An orderbook id is required to fetch fund history.")
    provider_monitor.record_attempt(PROVIDER_NAME)
    if not rate_limiter.allow(PROVIDER_NAME, AVANZA_FUND_MAX_CALLS, AVANZA_FUND_PERIOD_SECONDS):
        message = "Avanza fund rate limit reached."
        provider_monitor.record_failure(PROVIDER_NAME, message)
        raise RuntimeError(message)
    try:
        points = _fetch_fund_history(normalized_id, range_key)
    except Exception as error:
        provider_monitor.record_failure(PROVIDER_NAME, str(error))
        raise
    provider_monitor.record_success(PROVIDER_NAME)
    return points


def fetch_fund_nav(*, isin: str, name: str) -> FundNav:
    """Fetch one public fund NAV and validate it against the requested ISIN."""
    normalized_isin = isin.strip().upper()
    if not normalized_isin:
        raise ValueError("An ISIN is required to fetch a fund NAV.")

    provider_monitor.record_attempt(PROVIDER_NAME)
    if not rate_limiter.allow(PROVIDER_NAME, AVANZA_FUND_MAX_CALLS, AVANZA_FUND_PERIOD_SECONDS):
        message = "Avanza fund rate limit reached."
        provider_monitor.record_failure(PROVIDER_NAME, message)
        raise RuntimeError(message)

    try:
        payload = _post_json(_search_payload(name))
        rows = payload.get("fundListViews")
        if not isinstance(rows, list):
            raise ValueError("Avanza returned no fund list.")
        match = next(
            (row for row in rows if isinstance(row, dict) and str(row.get("isin") or "").upper() == normalized_isin),
            None,
        )
        if match is None:
            raise LookupError(f"Avanza did not return ISIN {normalized_isin} for {name!r}.")
        nav = float(match.get("nav"))
        if not math.isfinite(nav) or nav <= 0:
            raise ValueError(f"Avanza returned an invalid NAV for {normalized_isin}.")
        orderbook_id = str(match.get("orderbookId") or "").strip() or None
        history: list[FundHistoryPoint] = []
        if orderbook_id:
            try:
                history = _fetch_fund_history(orderbook_id, "1y")
            except Exception:
                # Current NAV is still useful if the optional chart endpoint is unavailable.
                history = []
        result = FundNav(
            isin=normalized_isin,
            name=str(match.get("name") or name).strip() or name,
            nav=nav,
            nav_date=_parse_timestamp(match.get("navDate")),
            currency=str(match.get("currencyCode") or "").strip() or None,
            orderbook_id=orderbook_id,
            history=history,
        )
    except Exception as error:
        provider_monitor.record_failure(PROVIDER_NAME, str(error))
        raise

    provider_monitor.record_success(PROVIDER_NAME)
    return result
