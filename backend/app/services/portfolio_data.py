from __future__ import annotations

import csv
import hashlib
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

import yaml

from app.core.config import InstrumentConfig, repo_root
from app.models.portfolio import PortfolioHolding, PortfolioOwnerValue, PortfolioTotals
from app.models.summary import SparkPoint
from app.providers import yahoo_finance
from app.services.market_data import calculate_metrics


class TickerMapping(TypedDict):
    ticker: str
    source: str
    label: str | None


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
        data_dir.glob("*positioner*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


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
        }
        for key in ("isin", "short_name", "name"):
            value = str(item.get(key) or "").strip()
            if value:
                result[f"{key}:{value.lower()}"] = mapping
    return result


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
        return {"ticker": f"{yahoo_symbol}.ST", "source": "direct", "label": None}
    if market in {"XNYS", "XNAS", "XASE", "ARCX"}:
        return {"ticker": yahoo_symbol, "source": "direct", "label": None}
    return None


def _snapshot_date(source_file: Path) -> str:
    match = re.search(r"\d{4}-\d{2}-\d{2}", source_file.name)
    if match:
        return match.group(0)
    return datetime.now(timezone.utc).date().isoformat()


def _round(value: float | None, precision: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, precision)


def load_portfolio_holdings(data_dir: Path | None = None) -> list[PortfolioHolding]:
    base_dir = data_dir or portfolio_data_dir()
    position_file = _latest_position_file(base_dir)
    if position_file is None:
        return []

    mapping = _load_ticker_mapping(base_dir)
    holdings: list[PortfolioHolding] = []
    with position_file.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
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
                    currency=(row.get("Valuta") or "").strip() or None,
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


def enrich_holdings_with_market_data(holdings: list[PortfolioHolding]) -> list[PortfolioHolding]:
    ticker_by_id = {item.id: item.ticker for item in holdings if item.ticker}
    if not ticker_by_id:
        return holdings

    snapshots, errors = yahoo_finance.fetch_quotes_with_history(tickers=ticker_by_id.values(), period="1y")
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
        output.append(
            holding.model_copy(
                update={
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
) -> dict[str, Any]:
    return {
        "source": "local_avanza_export",
        "cached": cached,
        "fetched_at": fetched_at,
        "data_dir": str(data_dir),
        "source_file": source_file.name if source_file else None,
        "source_files": [{"owner_id": owner_id, "source_file": path.name} for owner_id, path in (source_files or [])],
    }
