from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypedDict

import yaml
import pandas as pd

from app.core.config import InstrumentConfig, repo_root
from app.models.portfolio import PortfolioAccountValue, PortfolioHolding, PortfolioHoldingLevels, PortfolioOwnerValue, PortfolioTotals
from app.models.summary import SparkPoint
from app.providers import yahoo_finance
from app.providers import avanza_funds
from app.core.settings import AVANZA_FUND_CACHE_SECONDS
from app.services.market_data import calculate_metrics


class TickerMapping(TypedDict):
    ticker: str
    source: str
    label: str | None
    currency: str | None


class PortfolioLevel(TypedDict):
    target_price: float | None
    stop_price: float | None
    currency: str | None
    note: str | None


BUILT_IN_TICKER_MAPPINGS: dict[str, TickerMapping] = {}
PORTFOLIO_OWNERS = (
    {"owner_id": "jp", "owner_label": "JP", "dirname": "JP_avanza"},
    {"owner_id": "pat", "owner_label": "Pat", "dirname": "Pat_avanza"},
)


def portfolio_data_dir() -> Path:
    raw = os.getenv("LOCAL_PORTFOLIO_DATA_DIR")
    if raw:
        return Path(raw).expanduser()
    return repo_root() / "local-data" / "avanza"


def portfolio_base_data_dir() -> Path:
    raw = os.getenv("LOCAL_PORTFOLIO_BASE_DIR")
    if raw:
        return Path(raw).expanduser()
    legacy_dir = os.getenv("LOCAL_PORTFOLIO_DATA_DIR")
    if legacy_dir:
        return Path(legacy_dir).expanduser().parent
    return repo_root() / "local-data"


def portfolio_owner_dirs(base_dir: Path | None = None) -> list[dict[str, Any]]:
    root = base_dir or portfolio_base_data_dir()
    return [
        {
            "owner_id": owner["owner_id"],
            "owner_label": owner["owner_label"],
            "data_dir": root / owner["dirname"],
        }
        for owner in PORTFOLIO_OWNERS
    ]


def latest_portfolio_source_files(base_dir: Path | None = None) -> list[tuple[str, str, Path, Path]]:
    files: list[tuple[str, str, Path, Path]] = []
    for owner in portfolio_owner_dirs(base_dir):
        data_dir = owner["data_dir"]
        source_file = _latest_position_file(data_dir) if data_dir.exists() else None
        if source_file is not None:
            files.append((owner["owner_id"], owner["owner_label"], data_dir, source_file))
    return files


def _latest_named_file(data_dir: Path, patterns: tuple[str, ...]) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(data_dir.glob(pattern))
    unique_candidates = sorted(
        set(candidates),
        key=lambda path: (_snapshot_date(path), path.stat().st_mtime, path.name),
        reverse=True,
    )
    return unique_candidates[0] if unique_candidates else None


def _latest_account_file(data_dir: Path) -> Path | None:
    return _latest_named_file(data_dir, ("*konto*.csv", "*konto*.ods"))


def _latest_transaction_file(data_dir: Path) -> Path | None:
    candidates: list[Path] = []
    for pattern in ("*transaktion*.csv", "*transaktion*.ods", "*transaction*.csv", "*transaction*.ods"):
        candidates.extend(data_dir.glob(pattern))
    unique_candidates = sorted(
        set(candidates),
        key=lambda path: (_latest_date_in_filename(path), path.suffix.lower() == ".ods", path.stat().st_mtime, path.name),
        reverse=True,
    )
    return unique_candidates[0] if unique_candidates else None


def latest_portfolio_refresh_files(base_dir: Path | None = None) -> list[tuple[str, str, Path, str, Path]]:
    transaction_files = latest_portfolio_transaction_files(base_dir)
    if transaction_files:
        return [(owner_id, owner_label, data_dir, "transactions", source_file) for owner_id, owner_label, data_dir, source_file in transaction_files]
    return [(owner_id, owner_label, data_dir, "positions", source_file) for owner_id, owner_label, data_dir, source_file in latest_portfolio_source_files(base_dir)]


def latest_portfolio_transaction_files(base_dir: Path | None = None) -> list[tuple[str, str, Path, Path]]:
    files: list[tuple[str, str, Path, Path]] = []
    for owner in portfolio_owner_dirs(base_dir):
        data_dir = owner["data_dir"]
        if not data_dir.exists():
            continue
        source_file = _latest_transaction_file(data_dir)
        if source_file is not None:
            files.append((owner["owner_id"], owner["owner_label"], data_dir, source_file))
    return files


def _transaction_state_path(base_dir: Path) -> Path:
    return base_dir / ".portfolio-transaction-state.json"


def portfolio_ledger_path(base_dir: Path | None = None) -> Path:
    return (base_dir or portfolio_base_data_dir()) / "portfolio-ledger.json"


def fund_price_cache_path(base_dir: Path | None = None) -> Path:
    return (base_dir or portfolio_base_data_dir()) / "fund-prices.json"


def portfolio_levels_path(base_dir: Path | None = None) -> Path:
    return (base_dir or portfolio_base_data_dir()) / "portfolio-levels.yaml"


def _parse_cache_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _load_fund_price_cache(base_dir: Path) -> dict[str, dict[str, Any]]:
    path = fund_price_cache_path(base_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    prices = payload.get("prices") if isinstance(payload, dict) else None
    if not isinstance(prices, dict):
        return {}
    return {str(isin).lower(): entry for isin, entry in prices.items() if isinstance(entry, dict)}


def _save_fund_price_cache(base_dir: Path, prices: dict[str, dict[str, Any]]) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    path = fund_price_cache_path(base_dir)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps({"version": 1, "prices": prices}, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _cache_entry_to_fund_nav(entry: dict[str, Any]) -> avanza_funds.FundNav | None:
    try:
        nav = float(entry["nav"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(nav) or nav <= 0:
        return None
    isin = str(entry.get("isin") or "").strip().upper()
    name = str(entry.get("name") or "").strip()
    if not isin or not name:
        return None
    return avanza_funds.FundNav(
        isin=isin,
        name=name,
        nav=nav,
        nav_date=_parse_cache_timestamp(entry.get("nav_date")),
        currency=str(entry.get("currency") or "").strip() or None,
        orderbook_id=str(entry.get("orderbook_id") or "").strip() or None,
    )


def _fund_cache_entry(quote: avanza_funds.FundNav, fetched_at: datetime) -> dict[str, Any]:
    return {
        "isin": quote.isin,
        "name": quote.name,
        "nav": quote.nav,
        "nav_date": quote.nav_date.isoformat() if quote.nav_date else None,
        "currency": quote.currency,
        "orderbook_id": quote.orderbook_id,
        "fetched_at": fetched_at.isoformat(),
    }


def _apply_fund_nav(
    holding: PortfolioHolding,
    quote: avanza_funds.FundNav,
    *,
    fetched_at: datetime,
    is_stale: bool,
    stale_reason: str | None,
) -> PortfolioHolding:
    owners = [
        owner.model_copy(
            update={
                "current_value": round(owner.quantity * quote.nav, 2),
                "gain_abs": _round(owner.quantity * quote.nav - owner.acquisition_value)
                if owner.acquisition_value is not None
                else None,
                "gain_pct": _round((owner.quantity * quote.nav - owner.acquisition_value) / owner.acquisition_value * 100.0)
                if owner.acquisition_value not in (None, 0)
                else None,
            }
        )
        for owner in holding.owners
    ]
    current_value = round(sum(owner.current_value for owner in owners), 2) if owners else round(holding.quantity * quote.nav, 2)
    acquisition_value = holding.acquisition_value
    gain_abs = current_value - acquisition_value if acquisition_value is not None else None
    gain_pct = (gain_abs / acquisition_value * 100.0) if gain_abs is not None and acquisition_value not in (None, 0) else None
    return holding.model_copy(
        update={
            "owners": owners,
            "current_value": current_value,
            "gain_abs": _round(gain_abs),
            "gain_pct": _round(gain_pct),
            "valuation_source": "avanza_funds",
            "valuation_fetched_at": fetched_at,
            "valuation_is_stale": is_stale,
            "valuation_stale_reason": stale_reason,
        }
    )


def _enrich_fund_valuations(
    holdings: list[PortfolioHolding],
    *,
    cache_dir: Path,
) -> list[PortfolioHolding]:
    now = datetime.now(timezone.utc)
    cache = _load_fund_price_cache(cache_dir)
    cache_changed = False
    quote_by_isin: dict[str, tuple[avanza_funds.FundNav, datetime, bool, str | None]] = {}
    candidates = {
        holding.isin.lower(): holding
        for holding in holdings
        if holding.isin
        and (holding.instrument_type.upper() == "FUND" or (holding.instrument_type.upper() == "UNKNOWN" and not holding.ticker))
    }

    for isin, holding in candidates.items():
        cached_entry = cache.get(isin)
        cached_quote = _cache_entry_to_fund_nav(cached_entry) if cached_entry else None
        cached_at = _parse_cache_timestamp(cached_entry.get("fetched_at")) if cached_entry else None
        is_fresh = cached_quote is not None and cached_at is not None and now - cached_at <= timedelta(seconds=AVANZA_FUND_CACHE_SECONDS)
        if is_fresh:
            quote_by_isin[isin] = (cached_quote, cached_at, False, None)
            continue
        try:
            quote = avanza_funds.fetch_fund_nav(isin=holding.isin or "", name=holding.name)
        except Exception as error:
            if cached_quote is not None and cached_at is not None:
                quote_by_isin[isin] = (cached_quote, cached_at, True, str(error))
            continue
        cache[isin] = _fund_cache_entry(quote, now)
        cache_changed = True
        quote_by_isin[isin] = (quote, now, False, None)

    if cache_changed:
        _save_fund_price_cache(cache_dir, cache)

    output: list[PortfolioHolding] = []
    for holding in holdings:
        quote_data = quote_by_isin.get((holding.isin or "").lower())
        if quote_data is None:
            output.append(holding)
            continue
        quote, fetched_at, is_stale, stale_reason = quote_data
        output.append(
            _apply_fund_nav(
                holding,
                quote,
                fetched_at=fetched_at,
                is_stale=is_stale,
                stale_reason=stale_reason,
            )
        )
    return output


def _transaction_file_signature(source_file: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    rows = _read_table_rows(source_file)
    for row in rows:
        digest.update(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        digest.update(b"\n")
    return {
        "source_file": source_file.name,
        "mtime_ns": source_file.stat().st_mtime_ns,
        "row_count": len(rows),
        "sha256": digest.hexdigest(),
    }


def check_portfolio_transactions_for_updates(base_dir: Path | None = None) -> dict[str, Any]:
    root = base_dir or portfolio_base_data_dir()
    root.mkdir(parents=True, exist_ok=True)
    state_path = _transaction_state_path(root)
    previous = {}
    if state_path.exists():
        try:
            previous = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}

    owners: list[dict[str, Any]] = []
    has_updates = False
    for owner_id, owner_label, _data_dir, source_file in latest_portfolio_transaction_files(root):
        signature = _transaction_file_signature(source_file)
        previous_owner = previous.get("owners", {}).get(owner_id, {})
        changed = signature.get("sha256") != previous_owner.get("sha256")
        new_rows = max(0, int(signature["row_count"]) - int(previous_owner.get("row_count", 0))) if previous_owner else int(signature["row_count"])
        has_updates = has_updates or changed
        owners.append(
            {
                "owner_id": owner_id,
                "owner_label": owner_label,
                "source_file": signature["source_file"],
                "row_count": signature["row_count"],
                "changed": changed,
                "new_rows": new_rows if changed else 0,
            }
        )

    current_state = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "owners": {
            owner_id: _transaction_file_signature(source_file)
            for owner_id, _owner_label, _data_dir, source_file in latest_portfolio_transaction_files(root)
        },
    }
    state_path.write_text(json.dumps(current_state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {"has_updates": has_updates, "owners": owners, "state_file": str(state_path)}


def _parse_decimal(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace("\ufeff", "").replace(" ", "").replace("\xa0", "")
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", ".")
    try:
        parsed = float(cleaned)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _slug(value: str) -> str:
    normalized = value.strip().lower()
    output = []
    for char in normalized:
        if char.isalnum():
            output.append(char)
        elif output and output[-1] != "-":
            output.append("-")
    return "".join(output).strip("-") or "holding"


def _stable_id(row: dict[str, str]) -> str:
    isin = (row.get("ISIN") or "").strip()
    if isin:
        return isin.lower()
    name = (row.get("Namn") or row.get("Kortnamn") or "holding").strip()
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"{_slug(name)}-{digest}"


def _normalized_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _holding_match_key(holding: PortfolioHolding) -> str:
    if holding.isin:
        return f"isin:{holding.isin.lower()}"
    if holding.ticker:
        return f"ticker:{holding.ticker.lower()}"
    return f"name:{_normalized_name(holding.name)}"


def _holding_id_from_key(key: str, fallback: str) -> str:
    prefix, _, value = key.partition(":")
    if prefix in {"isin", "ticker"} and value:
        return _slug(value)
    return fallback


def _latest_position_file(data_dir: Path) -> Path | None:
    candidates = sorted(
        set(data_dir.glob("*positioner*.csv")) | set(data_dir.glob("*positioner*.ods")),
        key=lambda path: (_snapshot_date(path), path.stat().st_mtime, path.name),
        reverse=True,
    )
    return candidates[0] if candidates else None


def _table_cell_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if pd.isna(value):
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value).strip()


def _clean_table_row(row: dict[Any, Any]) -> dict[str, str]:
    return {
        str(key).strip().replace("\ufeff", ""): _table_cell_to_str(value)
        for key, value in row.items()
        if key is not None and str(key).strip() and not str(key).strip().lower().startswith("unnamed:")
    }


def _read_table_rows(source_file: Path) -> list[dict[str, str]]:
    if source_file.suffix.lower() == ".ods":
        frame = pd.read_excel(source_file, engine="odf", dtype=object, keep_default_na=False)
        return [_clean_table_row(row) for row in frame.to_dict(orient="records")]

    with source_file.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        return [_clean_table_row(row) for row in reader]


def _load_ticker_mapping(data_dir: Path) -> dict[str, TickerMapping]:
    result: dict[str, TickerMapping] = dict(BUILT_IN_TICKER_MAPPINGS)
    mapping_path = data_dir / "ticker-map.yaml"
    if not mapping_path.exists():
        return result
    data = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
    mappings = data.get("mappings", [])
    if not isinstance(mappings, list):
        return result
    for item in mappings:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").strip()
        if not ticker:
            continue
        mapping: TickerMapping = {
            "ticker": ticker,
            "source": str(item.get("source") or "manual").strip() or "manual",
            "label": str(item.get("label") or "").strip() or None,
            "currency": str(item.get("currency") or "").strip().upper() or None,
        }
        for key in ("isin", "short_name", "name"):
            value = str(item.get(key) or "").strip()
            if value:
                result[f"{key}:{value.lower()}"] = mapping
    return result


def _normalize_ticker(value: str | None) -> str:
    return (value or "").strip().lower()


def _load_portfolio_levels(base_dir: Path) -> dict[str, dict[str, PortfolioLevel]]:
    path = portfolio_levels_path(base_dir)
    empty: dict[str, dict[str, PortfolioLevel]] = {"isin": {}, "ticker": {}, "name": {}}
    if not path.exists():
        return empty
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return empty
    rows = data.get("levels", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return empty

    result: dict[str, dict[str, PortfolioLevel]] = {"isin": {}, "ticker": {}, "name": {}}
    for item in rows:
        if not isinstance(item, dict):
            continue
        target_price = _parse_decimal(str(item.get("target_price") or ""))
        stop_price = _parse_decimal(str(item.get("stop_price") or ""))
        if target_price is None and stop_price is None:
            continue
        level: PortfolioLevel = {
            "target_price": target_price,
            "stop_price": stop_price,
            "currency": str(item.get("currency") or "").strip().upper() or None,
            "note": str(item.get("note") or "").strip() or None,
        }
        for source, raw_value in (
            ("isin", item.get("isin")),
            ("ticker", item.get("ticker")),
            ("name", item.get("name") or item.get("short_name")),
        ):
            value = str(raw_value or "").strip()
            if not value:
                continue
            if source == "isin":
                result[source][value.lower()] = level
            elif source == "ticker":
                result[source][_normalize_ticker(value)] = level
            else:
                result[source][_normalized_name(value)] = level
            break
    return result


def _match_portfolio_level(holding: PortfolioHolding, levels: dict[str, dict[str, PortfolioLevel]]) -> tuple[str, PortfolioLevel] | None:
    isin = (holding.isin or "").strip().lower()
    if isin and isin in levels["isin"]:
        return "isin", levels["isin"][isin]
    ticker = _normalize_ticker(holding.ticker)
    if ticker and ticker in levels["ticker"]:
        return "ticker", levels["ticker"][ticker]
    name = _normalized_name(holding.name)
    if name and name in levels["name"]:
        return "name", levels["name"][name]
    return None


def _comparison_price(holding: PortfolioHolding) -> float | None:
    instrument_type = holding.instrument_type.upper()
    if instrument_type == "FUND" and holding.quantity:
        return _round(holding.current_value / holding.quantity, 6)
    if holding.last is not None:
        return holding.last
    if instrument_type == "FUND" and holding.quantity:
        return _round(holding.current_value / holding.quantity, 6)
    return None


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def _estimated_level_basis_price(holding: PortfolioHolding, current_price: float | None) -> float | None:
    basis_price_sek = holding.acquisition_price_sek
    if (basis_price_sek is None or basis_price_sek <= 0) and holding.acquisition_value is not None and holding.quantity:
        basis_price_sek = holding.acquisition_value / holding.quantity
    if basis_price_sek is None or basis_price_sek <= 0:
        return None

    currency = (holding.currency or "SEK").upper()
    if currency == "SEK" or current_price is None or current_price <= 0 or not holding.quantity:
        return _round(basis_price_sek, 6)

    sek_per_unit = holding.current_value / (holding.quantity * current_price) if holding.current_value > 0 else None
    if sek_per_unit is None or sek_per_unit <= 0:
        return None
    return _round(basis_price_sek / sek_per_unit, 6)


def _estimated_portfolio_level(holding: PortfolioHolding, current_price: float | None) -> PortfolioLevel | None:
    if current_price is None or current_price <= 0:
        return None

    basis_price = _estimated_level_basis_price(holding, current_price)
    if basis_price is None or basis_price <= 0:
        return None

    closes = [point.v for point in holding.sparkline if point.v > 0]
    daily_moves = [
        abs(closes[index] / closes[index - 1] - 1.0)
        for index in range(1, len(closes))
        if closes[index - 1] > 0
    ]
    average_daily_move = sum(daily_moves) / len(daily_moves) if daily_moves else 0.0
    stop_pct = _clamp(max(0.08, average_daily_move * 3.0), 0.06, 0.20)
    target_pct = _clamp(max(0.12, stop_pct * 1.6, average_daily_move * 5.0), 0.10, 0.35)

    stop_price = _clamp(basis_price * (1.0 - stop_pct), basis_price * 0.75, basis_price * 0.96)
    target_price = _clamp(basis_price * (1.0 + target_pct), basis_price * 1.05, basis_price * 1.50)
    return {
        "target_price": _round(target_price),
        "stop_price": _round(stop_price),
        "currency": holding.currency,
        "note": "Uppskattad fran inkopskurs: stopp ca 6-20% ned, mal minst 1,6x risken upp.",
    }


def apply_portfolio_levels(holdings: list[PortfolioHolding], base_dir: Path | None = None) -> list[PortfolioHolding]:
    levels = _load_portfolio_levels(base_dir or portfolio_base_data_dir())
    output: list[PortfolioHolding] = []
    for holding in holdings:
        current_price = _comparison_price(holding)
        match = _match_portfolio_level(holding, levels)
        estimate = _estimated_portfolio_level(holding, current_price)
        if match is None and estimate is None:
            output.append(holding)
            continue
        match_source, level = match if match is not None else ("estimated", estimate)
        has_manual_target = match is not None and level["target_price"] is not None
        has_manual_stop = match is not None and level["stop_price"] is not None
        if estimate is not None:
            level = {
                "target_price": level["target_price"] if level["target_price"] is not None else estimate["target_price"],
                "stop_price": level["stop_price"] if level["stop_price"] is not None else estimate["stop_price"],
                "currency": level["currency"] or estimate["currency"],
                "note": level["note"] or estimate["note"],
            }
        target_price = level["target_price"]
        stop_price = level["stop_price"]
        target_distance = target_price - current_price if target_price is not None and current_price is not None else None
        stop_distance = current_price - stop_price if stop_price is not None and current_price is not None else None
        source = "manual" if has_manual_target and has_manual_stop else "manual+estimated" if match is not None else "estimated"
        level_model = PortfolioHoldingLevels(
            target_price=target_price,
            stop_price=stop_price,
            currency=level["currency"] or holding.currency,
            current_price=current_price,
            target_distance=_round(target_distance),
            target_distance_pct=_round(target_distance / current_price * 100.0) if target_distance is not None and current_price else None,
            stop_distance=_round(stop_distance),
            stop_distance_pct=_round(stop_distance / current_price * 100.0) if stop_distance is not None and current_price else None,
            match_source=match_source,
            source=source,
            note=level["note"],
        )
        output.append(holding.model_copy(update={"levels": level_model}))
    return output


def _infer_ticker_mapping(row: dict[str, str], mapping: dict[str, TickerMapping]) -> TickerMapping | None:
    keys = [
        ("isin", row.get("ISIN")),
        ("short_name", row.get("Kortnamn")),
        ("name", row.get("Namn")),
    ]
    for key, value in keys:
        normalized = (value or "").strip().lower()
        if normalized and f"{key}:{normalized}" in mapping:
            return mapping[f"{key}:{normalized}"]

    instrument_type = (row.get("Typ") or "").strip().upper()
    if instrument_type != "STOCK":
        return None

    short_name = (row.get("Kortnamn") or "").strip()
    market = (row.get("Marknad") or "").strip().upper()
    if not short_name:
        return None

    yahoo_symbol = short_name.replace(" ", "-")
    if market == "XSTO":
        return {"ticker": f"{yahoo_symbol}.ST", "source": "direct", "label": None, "currency": "SEK"}
    if market in {"XNYS", "XNAS", "XASE", "ARCX"}:
        return {"ticker": yahoo_symbol, "source": "direct", "label": None, "currency": "USD"}
    return None


def _snapshot_date(source_file: Path) -> str:
    match = re.search(r"\d{4}-\d{2}-\d{2}", source_file.name)
    if match:
        return match.group(0)
    return datetime.now(timezone.utc).date().isoformat()


def _latest_date_in_filename(source_file: Path) -> str:
    """Use a transaction export's end date when its filename contains a range."""
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", source_file.name)
    if dates:
        return max(dates)
    return _snapshot_date(source_file)


def _round(value: float | None, precision: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, precision)


def _transaction_row_hash(row: dict[str, str]) -> str:
    normalized = {key.strip(): _canonical_transaction_value(key, value) for key, value in row.items()}
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical_decimal(value: str) -> str | None:
    cleaned = value.strip().replace("\ufeff", "").replace(" ", "").replace("\xa0", "")
    if not cleaned:
        return ""
    cleaned = cleaned.replace(",", ".")
    try:
        parsed = Decimal(cleaned)
    except InvalidOperation:
        return None
    return format(parsed.normalize(), "f")


def _canonical_transaction_value(key: str, value: str | None) -> str:
    cleaned = (value or "").strip()
    if cleaned.lower() in {"nan", "none", "<na>"}:
        return ""
    normalized_key = key.strip().lower()
    if normalized_key in {"antal", "kurs", "belopp", "courtage", "valutakurs", "resultat"}:
        parsed = _canonical_decimal(cleaned)
        if parsed is not None:
            return parsed
    if normalized_key == "datum":
        return cleaned[:10]
    return " ".join(cleaned.split())


def load_portfolio_holdings(data_dir: Path | None = None) -> list[PortfolioHolding]:
    base_dir = data_dir or portfolio_data_dir()
    position_file = _latest_position_file(base_dir)
    if position_file is None:
        return []

    mapping = _load_ticker_mapping(base_dir)
    holdings: list[PortfolioHolding] = []
    for row in _read_table_rows(position_file):
        name = (row.get("Namn") or row.get("Kortnamn") or "").strip()
        if not name:
            continue
        quantity = _parse_decimal(row.get("Volym")) or 0.0
        current_value = _parse_decimal(row.get("Marknadsvärde")) or 0.0
        acquisition_price = _parse_decimal(row.get("GAV (SEK)"))
        acquisition_value = quantity * acquisition_price if acquisition_price is not None else None
        gain_abs = current_value - acquisition_value if acquisition_value is not None else None
        gain_pct = (gain_abs / acquisition_value * 100.0) if gain_abs is not None and acquisition_value not in (None, 0) else None
        ticker_mapping = _infer_ticker_mapping(row, mapping)
        ticker = ticker_mapping["ticker"] if ticker_mapping else None

        holdings.append(
            PortfolioHolding(
                id=_stable_id(row),
                name=name,
                short_name=(row.get("Kortnamn") or "").strip() or None,
                isin=(row.get("ISIN") or "").strip() or None,
                instrument_type=(row.get("Typ") or "").strip() or "UNKNOWN",
                market=(row.get("Marknad") or "").strip() or None,
                currency=(ticker_mapping["currency"] if ticker_mapping and ticker_mapping["currency"] else (row.get("Valuta") or "").strip() or None),
                quantity=round(quantity, 6),
                current_value=round(current_value, 2),
                acquisition_price_sek=_round(acquisition_price),
                acquisition_value=_round(acquisition_value),
                gain_abs=_round(gain_abs),
                gain_pct=_round(gain_pct),
                ticker=ticker,
                chart_source=ticker_mapping["source"] if ticker_mapping else None,
                chart_label=ticker_mapping["label"] if ticker_mapping else None,
                has_chart=bool(ticker),
                is_stale=not bool(ticker),
            )
        )

    return sorted(holdings, key=lambda item: item.current_value, reverse=True)


def load_portfolio_account_value(data_dir: Path, owner_id: str, owner_label: str) -> PortfolioAccountValue:
    account_file = _latest_account_file(data_dir)
    if account_file is None:
        return PortfolioAccountValue(
            owner_id=owner_id,
            owner_label=owner_label,
            total_value=0.0,
            bank_value=0.0,
            account_count=0,
            source_file=None,
        )

    total_value = 0.0
    bank_value = 0.0
    account_count = 0
    for row in _read_table_rows(account_file):
        value = _parse_decimal(row.get("Totalvärde")) or 0.0
        total_value += value
        account_count += 1
        if (row.get("Kontotyp") or "").strip().lower() == "sparkonto":
            bank_value += value

    return PortfolioAccountValue(
        owner_id=owner_id,
        owner_label=owner_label,
        total_value=round(total_value, 2),
        bank_value=round(bank_value, 2),
        account_count=account_count,
        source_file=account_file.name,
    )


def save_portfolio_snapshot(data_dir: Path, source_file: Path, holdings: list[PortfolioHolding]) -> Path:
    snapshots_dir = data_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshots_path = snapshots_dir / "portfolio-snapshots.csv"
    fieldnames = [
        "snapshot_date",
        "source_file",
        "isin",
        "name",
        "quantity",
        "current_value",
        "derived_price",
        "acquisition_price_sek",
        "acquisition_value",
        "ticker",
        "chart_source",
    ]

    existing_keys: set[tuple[str, str, str]] = set()
    if snapshots_path.exists():
        with snapshots_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            for row in reader:
                existing_keys.add((row.get("snapshot_date", ""), row.get("source_file", ""), row.get("isin", "")))

    snapshot_date = _snapshot_date(source_file)
    rows = []
    for holding in holdings:
        isin = holding.isin or holding.id
        key = (snapshot_date, source_file.name, isin)
        if key in existing_keys:
            continue
        derived_price = holding.current_value / holding.quantity if holding.quantity else None
        rows.append(
            {
                "snapshot_date": snapshot_date,
                "source_file": source_file.name,
                "isin": isin,
                "name": holding.name,
                "quantity": holding.quantity,
                "current_value": holding.current_value,
                "derived_price": _round(derived_price, 6),
                "acquisition_price_sek": holding.acquisition_price_sek,
                "acquisition_value": holding.acquisition_value,
                "ticker": holding.ticker,
                "chart_source": holding.chart_source,
            }
        )

    if rows:
        write_header = not snapshots_path.exists()
        with snapshots_path.open("a", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
            if write_header:
                writer.writeheader()
            writer.writerows(rows)

    return snapshots_path


def _owner_value(owner_id: str, owner_label: str, holding: PortfolioHolding) -> PortfolioOwnerValue:
    return PortfolioOwnerValue(
        owner_id=owner_id,
        owner_label=owner_label,
        current_value=holding.current_value,
        acquisition_value=holding.acquisition_value,
        gain_abs=holding.gain_abs,
        gain_pct=holding.gain_pct,
        quantity=holding.quantity,
    )


def _merge_portfolio_holdings(owner_holdings: list[tuple[str, str, PortfolioHolding]]) -> list[PortfolioHolding]:
    grouped: dict[str, list[tuple[str, str, PortfolioHolding]]] = {}
    first_key_by_id: dict[str, str] = {}
    for owner_id, owner_label, holding in owner_holdings:
        key = _holding_match_key(holding)
        grouped.setdefault(key, []).append((owner_id, owner_label, holding))
        first_key_by_id.setdefault(key, holding.id)

    merged: list[PortfolioHolding] = []
    for key, items in grouped.items():
        template = items[0][2]
        chart_template = next((item for _, _, item in items if item.ticker), template)
        quantity = round(sum(item.quantity for _, _, item in items), 6)
        current_value = round(sum(item.current_value for _, _, item in items), 2)
        acquisition_values = [item.acquisition_value for _, _, item in items if item.acquisition_value is not None]
        acquisition_value = round(sum(acquisition_values), 2) if acquisition_values else None
        gain_abs = round(current_value - acquisition_value, 2) if acquisition_value is not None else None
        gain_pct = _round(gain_abs / acquisition_value * 100.0) if gain_abs is not None and acquisition_value not in (None, 0) else None
        acquisition_price = _round(acquisition_value / quantity) if acquisition_value is not None and quantity else None
        owners = [_owner_value(owner_id, owner_label, holding) for owner_id, owner_label, holding in items]

        merged.append(
            chart_template.model_copy(
                update={
                    "id": _holding_id_from_key(key, first_key_by_id[key]),
                    "name": template.name,
                    "short_name": template.short_name,
                    "isin": template.isin,
                    "instrument_type": template.instrument_type,
                    "market": template.market,
                    "currency": template.currency,
                    "quantity": quantity,
                    "current_value": current_value,
                    "acquisition_price_sek": acquisition_price,
                    "acquisition_value": acquisition_value,
                    "gain_abs": gain_abs,
                    "gain_pct": gain_pct,
                    "owners": owners,
                }
            )
        )

    return sorted(merged, key=lambda item: item.current_value, reverse=True)


def load_combined_portfolio_holdings(base_dir: Path | None = None, *, save_snapshots: bool = False) -> list[PortfolioHolding]:
    owner_holdings: list[tuple[str, str, PortfolioHolding]] = []
    for owner_id, owner_label, data_dir, source_file in latest_portfolio_source_files(base_dir):
        holdings = load_portfolio_holdings(data_dir)
        if save_snapshots:
            save_portfolio_snapshot(data_dir, source_file, holdings)
        owner_holdings.extend((owner_id, owner_label, holding) for holding in holdings)
    return _merge_portfolio_holdings(owner_holdings)


def load_portfolio_accounts(base_dir: Path | None = None) -> list[PortfolioAccountValue]:
    accounts: list[PortfolioAccountValue] = []
    for owner in portfolio_owner_dirs(base_dir):
        data_dir = owner["data_dir"]
        if data_dir.exists():
            accounts.append(load_portfolio_account_value(data_dir, owner["owner_id"], owner["owner_label"]))
    return accounts


def _empty_ledger_owner(owner_id: str, owner_label: str) -> dict[str, Any]:
    return {
        "owner_id": owner_id,
        "owner_label": owner_label,
        "bank_value": 0.0,
        "holdings": {},
        "processed_transactions": {},
        "transaction_checkpoint": {
            "source_file": None,
            "latest_transaction_date": None,
            "updated_at": None,
        },
    }


def _ledger_key_for_holding(holding: PortfolioHolding) -> str:
    if holding.isin:
        return f"isin:{holding.isin.lower()}"
    if holding.ticker:
        return f"ticker:{holding.ticker.lower()}"
    return f"name:{_normalized_name(holding.name)}"


def _holding_to_ledger_item(holding: PortfolioHolding) -> dict[str, Any]:
    current_price = holding.current_value / holding.quantity if holding.quantity else None
    return {
        "id": holding.id,
        "name": holding.name,
        "short_name": holding.short_name,
        "isin": holding.isin,
        "instrument_type": holding.instrument_type,
        "market": holding.market,
        "currency": holding.currency,
        "quantity": holding.quantity,
        "acquisition_value": holding.acquisition_value or 0.0,
        "current_price_sek": _round(current_price, 6),
        "ticker": holding.ticker,
        "chart_source": holding.chart_source,
        "chart_label": holding.chart_label,
    }


def _ledger_item_to_holding(item: dict[str, Any]) -> PortfolioHolding:
    quantity = float(item.get("quantity") or 0.0)
    acquisition_value = float(item.get("acquisition_value") or 0.0)
    acquisition_price = acquisition_value / quantity if quantity else None
    current_price = _parse_decimal(str(item.get("current_price_sek") or ""))
    if current_price is None:
        current_price = acquisition_price
    current_value = quantity * current_price if current_price is not None else 0.0
    gain_abs = current_value - acquisition_value
    gain_pct = (gain_abs / acquisition_value * 100.0) if acquisition_value else None
    ticker = item.get("ticker")
    return PortfolioHolding(
        id=str(item.get("id") or item.get("isin") or _slug(str(item.get("name") or "holding"))),
        name=str(item.get("name") or item.get("short_name") or "Okänt innehav"),
        short_name=item.get("short_name"),
        isin=item.get("isin"),
        instrument_type=str(item.get("instrument_type") or "UNKNOWN"),
        market=item.get("market"),
        currency=item.get("currency"),
        quantity=round(quantity, 6),
        current_value=round(current_value, 2),
        acquisition_price_sek=_round(acquisition_price),
        acquisition_value=round(acquisition_value, 2),
        gain_abs=_round(gain_abs),
        gain_pct=_round(gain_pct),
        ticker=ticker,
        chart_source=item.get("chart_source"),
        chart_label=item.get("chart_label"),
        has_chart=bool(ticker),
        is_stale=not bool(ticker),
    )


def _read_transaction_rows(source_file: Path) -> list[tuple[str, dict[str, str]]]:
    rows: list[tuple[str, dict[str, str]]] = []
    for row in _read_table_rows(source_file):
        normalized_row = _normalize_transaction_row(row)
        rows.append((_transaction_row_hash(normalized_row), normalized_row))
    return rows


def _normalize_transaction_row(row: dict[str, str]) -> dict[str, str]:
    """Repair the shifted amount columns emitted by some LibreOffice ODS exports."""
    normalized = dict(row)
    amount = _parse_decimal(normalized.get("Belopp"))
    shifted_amount = _parse_decimal(normalized.get("Transaktionsvaluta"))
    shifted_currency = (normalized.get("Valutakurs") or "").strip()
    if amount is None or shifted_amount is None or not shifted_currency.isalpha():
        return normalized

    original_commission = normalized.get("Belopp") or ""
    normalized["Belopp"] = normalized.get("Transaktionsvaluta") or ""
    normalized["Transaktionsvaluta"] = shifted_currency
    normalized["Courtage"] = original_commission
    normalized["Valutakurs"] = ""
    return normalized


def _transaction_sort_key(row: dict[str, str], index: int) -> tuple[str, int]:
    return (row.get("Datum") or "", index)


def _infer_transaction_ticker(row: dict[str, str], data_dir: Path) -> TickerMapping | None:
    mapping = _load_ticker_mapping(data_dir)
    synthetic_row = {
        "ISIN": row.get("ISIN", ""),
        "Namn": row.get("Värdepapper/beskrivning", ""),
        "Kortnamn": row.get("Värdepapper/beskrivning", ""),
        "Typ": "",
        "Marknad": "",
    }
    return _infer_ticker_mapping(synthetic_row, mapping)


def _ensure_ledger_holding(owner: dict[str, Any], row: dict[str, str], data_dir: Path) -> tuple[str, dict[str, Any]]:
    isin = (row.get("ISIN") or "").strip() or None
    name = (row.get("Värdepapper/beskrivning") or row.get("ISIN") or "Okänt innehav").strip()
    key = f"isin:{isin.lower()}" if isin else f"name:{_normalized_name(name)}"
    holdings = owner.setdefault("holdings", {})
    matching_name_key = next(
        (
            existing_key
            for existing_key, existing in holdings.items()
            if _normalized_name(str(existing.get("name") or "")) == _normalized_name(name)
        ),
        None,
    )
    if isin and key not in holdings and matching_name_key and matching_name_key != key:
        holding = holdings.pop(matching_name_key)
        ticker_mapping = _infer_transaction_ticker(row, data_dir)
        holding.update(
            {
                "id": isin.lower(),
                "isin": isin,
                "name": name,
                "short_name": name,
                "currency": (
                    ticker_mapping["currency"]
                    if ticker_mapping and ticker_mapping["currency"]
                    else (row.get("Instrumentvaluta") or row.get("Transaktionsvaluta") or holding.get("currency") or "SEK").strip() or "SEK"
                ),
                "ticker": ticker_mapping["ticker"] if ticker_mapping else holding.get("ticker"),
                "chart_source": ticker_mapping["source"] if ticker_mapping else holding.get("chart_source"),
                "chart_label": ticker_mapping["label"] if ticker_mapping else holding.get("chart_label"),
            }
        )
        holdings[key] = holding
    elif not isin and matching_name_key:
        key = matching_name_key
    if key not in holdings:
        ticker_mapping = _infer_transaction_ticker(row, data_dir)
        holdings[key] = {
            "id": isin.lower() if isin else f"{_slug(name)}-{hashlib.sha1(name.encode('utf-8')).hexdigest()[:8]}",
            "name": name,
            "short_name": name,
            "isin": isin,
            "instrument_type": "UNKNOWN",
            "market": None,
            "currency": (
                ticker_mapping["currency"]
                if ticker_mapping and ticker_mapping["currency"]
                else (row.get("Instrumentvaluta") or row.get("Transaktionsvaluta") or "SEK").strip() or "SEK"
            ),
            "quantity": 0.0,
            "acquisition_value": 0.0,
            "current_price_sek": None,
            "ticker": ticker_mapping["ticker"] if ticker_mapping else None,
            "chart_source": ticker_mapping["source"] if ticker_mapping else None,
            "chart_label": ticker_mapping["label"] if ticker_mapping else None,
        }
    return key, holdings[key]


def _apply_transaction_to_ledger_owner(owner: dict[str, Any], row: dict[str, str], data_dir: Path) -> None:
    transaction_type = (row.get("Typ av transaktion") or "").strip()
    account = (row.get("Konto") or "").strip().lower()
    amount = _parse_decimal(row.get("Belopp")) or 0.0

    if account == "bank" and transaction_type in {
        "Autogiroinsättning",
        "Inlåningsränta",
        "Preliminärskatt kapitalränta",
        "Intern överföring",
    }:
        owner["bank_value"] = round(float(owner.get("bank_value") or 0.0) + amount, 2)
        return

    if transaction_type not in {"Köp", "Sälj"}:
        return

    quantity = _parse_decimal(row.get("Antal")) or 0.0
    if transaction_type == "Sälj":
        quantity = abs(quantity)
    if quantity <= 0:
        return

    _key, holding = _ensure_ledger_holding(owner, row, data_dir)
    current_quantity = float(holding.get("quantity") or 0.0)
    current_acquisition = float(holding.get("acquisition_value") or 0.0)

    if transaction_type == "Köp":
        holding["quantity"] = round(current_quantity + quantity, 6)
        holding["acquisition_value"] = round(current_acquisition + abs(amount), 2)
        if _parse_decimal(str(holding.get("current_price_sek") or "")) is None:
            holding["current_price_sek"] = round(abs(amount) / quantity, 6)
        return

    sold_quantity = min(quantity, current_quantity)
    average_cost = current_acquisition / current_quantity if current_quantity else 0.0
    holding["quantity"] = round(current_quantity - sold_quantity, 6)
    holding["acquisition_value"] = round(max(0.0, current_acquisition - average_cost * sold_quantity), 2)


def _baseline_transactions_for_owner(
    owner: dict[str, Any],
    source_file: Path | None,
    baseline_through: str | None,
) -> None:
    if source_file is None:
        return
    processed = owner.setdefault("processed_transactions", {})
    for row_hash, row in _read_transaction_rows(source_file):
        if baseline_through is not None and (row.get("Datum") or "") > baseline_through:
            continue
        processed[row_hash] = {
            "source_file": source_file.name,
            "date": row.get("Datum"),
            "type": row.get("Typ av transaktion"),
            "baseline": True,
        }


def _seed_portfolio_ledger(base_dir: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    ledger = {
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "seed": {"owners": {}},
        "owners": {},
    }
    for owner_meta in portfolio_owner_dirs(base_dir):
        owner_id = owner_meta["owner_id"]
        owner_label = owner_meta["owner_label"]
        data_dir = owner_meta["data_dir"]
        owner = _empty_ledger_owner(owner_id, owner_label)
        if data_dir.exists():
            position_file = _latest_position_file(data_dir)
            account_file = _latest_account_file(data_dir)
            transaction_file = _latest_transaction_file(data_dir)
            for holding in load_portfolio_holdings(data_dir):
                owner["holdings"][_ledger_key_for_holding(holding)] = _holding_to_ledger_item(holding)
            account = load_portfolio_account_value(data_dir, owner_id, owner_label)
            owner["bank_value"] = account.bank_value
            _baseline_transactions_for_owner(
                owner,
                transaction_file,
                _snapshot_date(position_file) if position_file else None,
            )
            ledger["seed"]["owners"][owner_id] = {
                "position_file": position_file.name if position_file else None,
                "account_file": account_file.name if account_file else None,
                "transaction_file": transaction_file.name if transaction_file else None,
                "seeded_at": now,
            }
        ledger["owners"][owner_id] = owner
    return ledger


def _backfill_ledger_current_prices(base_dir: Path, ledger: dict[str, Any]) -> bool:
    """Initialize legacy ledgers once from their original position exports."""
    changed = False
    for owner_meta in portfolio_owner_dirs(base_dir):
        owner = ledger.get("owners", {}).get(owner_meta["owner_id"])
        data_dir = owner_meta["data_dir"]
        if not owner or not data_dir.exists():
            continue
        missing_keys = [
            key
            for key, item in owner.get("holdings", {}).items()
            if _parse_decimal(str(item.get("current_price_sek") or "")) is None
        ]
        if not missing_keys:
            continue
        source_holdings = {
            _ledger_key_for_holding(holding): holding
            for holding in load_portfolio_holdings(data_dir)
        }
        for key in missing_keys:
            source_holding = source_holdings.get(key)
            if source_holding is None or not source_holding.quantity:
                continue
            owner["holdings"][key]["current_price_sek"] = _round(
                source_holding.current_value / source_holding.quantity,
                6,
            )
            changed = True
    return changed


def _backfill_ledger_ticker_mappings(base_dir: Path, ledger: dict[str, Any]) -> bool:
    """Apply local ticker metadata to ledger holdings created from transactions."""
    changed = False
    for owner_meta in portfolio_owner_dirs(base_dir):
        owner = ledger.get("owners", {}).get(owner_meta["owner_id"])
        data_dir = owner_meta["data_dir"]
        if not owner or not data_dir.exists():
            continue
        mapping = _load_ticker_mapping(data_dir)
        for holding in owner.get("holdings", {}).values():
            synthetic_row = {
                "ISIN": str(holding.get("isin") or ""),
                "Namn": str(holding.get("name") or ""),
                "Kortnamn": str(holding.get("short_name") or ""),
                "Typ": str(holding.get("instrument_type") or ""),
                "Marknad": str(holding.get("market") or ""),
            }
            ticker_mapping = _infer_ticker_mapping(synthetic_row, mapping)
            if ticker_mapping is None:
                continue
            updates = {
                "ticker": ticker_mapping["ticker"],
                "chart_source": ticker_mapping["source"],
                "chart_label": ticker_mapping["label"],
            }
            if ticker_mapping["currency"]:
                updates["currency"] = ticker_mapping["currency"]
            for key, value in updates.items():
                if holding.get(key) != value:
                    holding[key] = value
                    changed = True
    return changed


def _unbaseline_transactions_after_position_snapshot(ledger: dict[str, Any]) -> bool:
    """Let legacy ledgers apply transactions that happened after their seed export."""
    changed = False
    seed_owners = ledger.get("seed", {}).get("owners", {})
    for owner_id, owner in ledger.get("owners", {}).items():
        position_file = seed_owners.get(owner_id, {}).get("position_file")
        if not position_file:
            continue
        snapshot_date = _snapshot_date(Path(str(position_file)))
        processed = owner.get("processed_transactions", {})
        for row_hash, transaction in list(processed.items()):
            if transaction.get("baseline") and (transaction.get("date") or "") > snapshot_date:
                del processed[row_hash]
                changed = True
    return changed


def _load_portfolio_ledger(base_dir: Path) -> dict[str, Any]:
    ledger_path = portfolio_ledger_path(base_dir)
    if not ledger_path.exists():
        ledger = _seed_portfolio_ledger(base_dir)
        _save_portfolio_ledger(base_dir, ledger)
        return ledger
    return json.loads(ledger_path.read_text(encoding="utf-8"))


def _save_portfolio_ledger(base_dir: Path, ledger: dict[str, Any]) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
    portfolio_ledger_path(base_dir).write_text(json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def update_portfolio_ledger_from_transactions(base_dir: Path | None = None) -> dict[str, Any]:
    root = base_dir or portfolio_base_data_dir()
    ledger = _load_portfolio_ledger(root)
    ledger_changed = _backfill_ledger_current_prices(root, ledger)
    ledger_changed = _backfill_ledger_ticker_mappings(root, ledger) or ledger_changed
    ledger_changed = _unbaseline_transactions_after_position_snapshot(ledger) or ledger_changed
    applied: list[dict[str, Any]] = []
    for owner_id, owner_label, data_dir, source_file in latest_portfolio_transaction_files(root):
        owner = ledger.setdefault("owners", {}).setdefault(owner_id, _empty_ledger_owner(owner_id, owner_label))
        owner["owner_label"] = owner_label
        processed = owner.setdefault("processed_transactions", {})
        position_file = ledger.get("seed", {}).get("owners", {}).get(owner_id, {}).get("position_file")
        baseline_through = _snapshot_date(Path(str(position_file))) if position_file else None
        rows = _read_transaction_rows(source_file)
        latest_transaction_date = max((row.get("Datum") or "" for _row_hash, row in rows), default="") or None
        checkpoint = owner.setdefault("transaction_checkpoint", {})
        previous_checkpoint_date = checkpoint.get("latest_transaction_date")
        checkpoint_changed = (
            checkpoint.get("source_file") != source_file.name
            or checkpoint.get("latest_transaction_date") != latest_transaction_date
        )
        if checkpoint_changed:
            checkpoint.update(
                {
                    "source_file": source_file.name,
                    "latest_transaction_date": latest_transaction_date,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            ledger_changed = True
        new_rows = [(row_hash, row, index) for index, (row_hash, row) in enumerate(rows) if row_hash not in processed]
        for row_hash, row, _index in sorted(new_rows, key=lambda item: _transaction_sort_key(item[1], item[2])):
            if previous_checkpoint_date and (row.get("Datum") or "") <= previous_checkpoint_date:
                processed[row_hash] = {
                    "source_file": source_file.name,
                    "date": row.get("Datum"),
                    "type": row.get("Typ av transaktion"),
                    "baseline": True,
                    "baseline_reason": "before_transaction_checkpoint",
                }
                ledger_changed = True
                continue
            if baseline_through is not None and (row.get("Datum") or "") <= baseline_through:
                processed[row_hash] = {
                    "source_file": source_file.name,
                    "date": row.get("Datum"),
                    "type": row.get("Typ av transaktion"),
                    "baseline": True,
                }
                continue
            _apply_transaction_to_ledger_owner(owner, row, data_dir)
            processed[row_hash] = {
                "source_file": source_file.name,
                "date": row.get("Datum"),
                "type": row.get("Typ av transaktion"),
                "baseline": False,
            }
            applied.append({"owner_id": owner_id, "date": row.get("Datum"), "type": row.get("Typ av transaktion")})
    if applied or ledger_changed:
        _save_portfolio_ledger(root, ledger)
    return {"applied_count": len(applied), "applied": applied, "ledger_path": str(portfolio_ledger_path(root))}


def load_portfolio_holdings_from_ledger(base_dir: Path | None = None) -> list[PortfolioHolding]:
    root = base_dir or portfolio_base_data_dir()
    update_portfolio_ledger_from_transactions(root)
    ledger = _load_portfolio_ledger(root)
    owner_holdings: list[tuple[str, str, PortfolioHolding]] = []
    for owner_id, owner in ledger.get("owners", {}).items():
        owner_label = owner.get("owner_label") or owner_id
        for item in owner.get("holdings", {}).values():
            if abs(float(item.get("quantity") or 0.0)) <= 0.000001:
                continue
            owner_holdings.append((owner_id, owner_label, _ledger_item_to_holding(item)))
    return _merge_portfolio_holdings(owner_holdings)


def load_portfolio_accounts_from_ledger(base_dir: Path | None = None) -> list[PortfolioAccountValue]:
    root = base_dir or portfolio_base_data_dir()
    update_portfolio_ledger_from_transactions(root)
    ledger = _load_portfolio_ledger(root)
    accounts: list[PortfolioAccountValue] = []
    for owner_meta in portfolio_owner_dirs(root):
        owner_id = owner_meta["owner_id"]
        owner = ledger.get("owners", {}).get(owner_id, _empty_ledger_owner(owner_id, owner_meta["owner_label"]))
        accounts.append(
            PortfolioAccountValue(
                owner_id=owner_id,
                owner_label=owner.get("owner_label") or owner_meta["owner_label"],
                total_value=round(float(owner.get("bank_value") or 0.0), 2),
                bank_value=round(float(owner.get("bank_value") or 0.0), 2),
                account_count=1 if owner.get("bank_value") is not None else 0,
                source_file="portfolio-ledger.json",
            )
        )
    return accounts


def build_portfolio_totals(holdings: list[PortfolioHolding]) -> PortfolioTotals:
    current_value = sum(item.current_value for item in holdings)
    acquisition_value = sum(item.acquisition_value or 0.0 for item in holdings)
    gain_abs = current_value - acquisition_value
    gain_pct = (gain_abs / acquisition_value * 100.0) if acquisition_value else None
    return PortfolioTotals(
        current_value=round(current_value, 2),
        acquisition_value=round(acquisition_value, 2),
        gain_abs=round(gain_abs, 2),
        gain_pct=_round(gain_pct),
        holding_count=len(holdings),
        chart_count=sum(1 for item in holdings if item.has_chart),
    )


def enrich_holdings_with_market_data(
    holdings: list[PortfolioHolding],
    *,
    fund_cache_dir: Path | None = None,
) -> list[PortfolioHolding]:
    holdings = _enrich_fund_valuations(
        holdings,
        cache_dir=fund_cache_dir or portfolio_base_data_dir(),
    )
    ticker_by_id = {item.id: item.ticker for item in holdings if item.ticker}
    if not ticker_by_id:
        return holdings

    foreign_currencies = {
        item.currency.upper()
        for item in holdings
        if item.ticker
        and item.chart_source == "direct"
        and item.currency
        and item.currency.upper() != "SEK"
        and not item.ticker.endswith(".ST")
    }
    exchange_ticker_by_currency = {currency: f"{currency}SEK=X" for currency in foreign_currencies}
    snapshots, errors = yahoo_finance.fetch_quotes_with_history(
        tickers=[*ticker_by_id.values(), *exchange_ticker_by_currency.values()],
        period="1y",
    )
    sek_per_currency = {
        currency: snapshot.last
        for currency, ticker in exchange_ticker_by_currency.items()
        if (snapshot := snapshots.get(ticker)) is not None and snapshot.last is not None
    }
    output: list[PortfolioHolding] = []
    for holding in holdings:
        if not holding.ticker:
            output.append(holding)
            continue
        snapshot = snapshots.get(holding.ticker)
        if snapshot is None or snapshot.last is None:
            output.append(holding.model_copy(update={"is_stale": True, "has_chart": False}))
            continue
        metrics = calculate_metrics(snapshot.last, snapshot.prev_close, snapshot.history)
        sparkline = [SparkPoint(t=point.t, v=round(point.close, 2)) for point in snapshot.history[-30:]]
        value_update: dict[str, Any] = {}
        currency = (holding.currency or "").upper()
        sek_multiplier = 1.0 if currency == "SEK" or holding.ticker.endswith(".ST") else sek_per_currency.get(currency)
        if holding.chart_source == "direct" and sek_multiplier is not None:
            owners = []
            for owner in holding.owners:
                owner_current_value = round(owner.quantity * snapshot.last * sek_multiplier, 2)
                owner_gain_abs = owner_current_value - owner.acquisition_value if owner.acquisition_value is not None else None
                owner_gain_pct = (owner_gain_abs / owner.acquisition_value * 100.0) if owner_gain_abs is not None and owner.acquisition_value not in (None, 0) else None
                owners.append(
                    owner.model_copy(
                        update={
                            "current_value": owner_current_value,
                            "gain_abs": _round(owner_gain_abs),
                            "gain_pct": _round(owner_gain_pct),
                        }
                    )
                )
            current_value = round(sum(owner.current_value for owner in owners), 2)
            acquisition_value = holding.acquisition_value
            gain_abs = current_value - acquisition_value if acquisition_value is not None else None
            gain_pct = (gain_abs / acquisition_value * 100.0) if gain_abs is not None and acquisition_value not in (None, 0) else None
            value_update = {
                "owners": owners,
                "current_value": current_value,
                "gain_abs": _round(gain_abs),
                "gain_pct": _round(gain_pct),
            }
        output.append(
            holding.model_copy(
                update={
                    **value_update,
                    "has_chart": bool(sparkline),
                    "last": _round(snapshot.last),
                    "day_abs": _round(metrics["day_abs"]),
                    "day_pct": _round(metrics["day_pct"]),
                    "w1_pct": _round(metrics["w1_pct"]),
                    "ytd_pct": _round(metrics["ytd_pct"]),
                    "y1_pct": _round(metrics["y1_pct"]),
                    "timestamp_local": snapshot.timestamp,
                    "is_stale": holding.ticker in errors or not bool(sparkline),
                    "sparkline": sparkline,
                }
            )
        )
    return output


def fetch_portfolio_series(holding: PortfolioHolding, range_key: str) -> list[SparkPoint]:
    if not holding.ticker:
        return []
    points = yahoo_finance.fetch_history(ticker=holding.ticker, range_key=range_key)
    return [SparkPoint(t=point.t, v=round(point.close, 2)) for point in points]


def portfolio_meta(
    *,
    cached: bool,
    fetched_at: datetime,
    data_dir: Path,
    source_file: Path | None = None,
    source_files: list[tuple[str, Path]] | None = None,
    refresh_files: list[tuple[str, str, Path]] | None = None,
) -> dict[str, Any]:
    return {
        "source": "local_avanza_export",
        "cached": cached,
        "fetched_at": fetched_at,
        "data_dir": str(data_dir),
        "source_file": source_file.name if source_file else None,
        "source_files": [{"owner_id": owner_id, "source_file": path.name} for owner_id, path in (source_files or [])],
        "refresh_files": [{"owner_id": owner_id, "kind": kind, "source_file": path.name} for owner_id, kind, path in (refresh_files or [])],
    }
