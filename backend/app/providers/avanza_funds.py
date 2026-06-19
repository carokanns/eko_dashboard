from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from urllib.request import Request, urlopen

from app.core.provider_monitor import provider_monitor
from app.core.rate_limit import rate_limiter
from app.core.settings import AVANZA_FUND_MAX_CALLS, AVANZA_FUND_PERIOD_SECONDS


FUND_LIST_URL = "https://www.avanza.se/_api/fund-guide/list?shouldCheckFundExcludedFromPromotion=true"
PROVIDER_NAME = "avanza_funds"


@dataclass(frozen=True)
class FundNav:
    isin: str
    name: str
    nav: float
    nav_date: datetime | None
    currency: str | None
    orderbook_id: str | None


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
        result = FundNav(
            isin=normalized_isin,
            name=str(match.get("name") or name).strip() or name,
            nav=nav,
            nav_date=_parse_timestamp(match.get("navDate")),
            currency=str(match.get("currencyCode") or "").strip() or None,
            orderbook_id=str(match.get("orderbookId") or "").strip() or None,
        )
    except Exception as error:
        provider_monitor.record_failure(PROVIDER_NAME, str(error))
        raise

    provider_monitor.record_success(PROVIDER_NAME)
    return result
