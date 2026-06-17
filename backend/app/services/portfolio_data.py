from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypedDict

import yaml
import pandas as pd

from app.core.config import InstrumentConfig, repo_root
from app.models.portfolio import PortfolioAccountValue, PortfolioHolding, PortfolioOwnerValue, PortfolioTotals
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
        key=lambda path: (_snapshot_date(path), path.suffix.lower() == ".ods", path.stat().st_mtime, path.name),
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
    }


def _ledger_key_for_holding(holding: PortfolioHolding) -> str:
    if holding.isin:
        return f"isin:{holding.isin.lower()}"
    if holding.ticker:
        return f"ticker:{holding.ticker.lower()}"
    return f"name:{_normalized_name(holding.name)}"


def _holding_to_ledger_item(holding: PortfolioHolding) -> dict[str, Any]:
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
        "ticker": holding.ticker,
        "chart_source": holding.chart_source,
        "chart_label": holding.chart_label,
    }


def _ledger_item_to_holding(item: dict[str, Any]) -> PortfolioHolding:
    quantity = float(item.get("quantity") or 0.0)
    acquisition_value = float(item.get("acquisition_value") or 0.0)
    acquisition_price = acquisition_value / quantity if quantity else None
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
        current_value=round(acquisition_value, 2),
        acquisition_price_sek=_round(acquisition_price),
        acquisition_value=round(acquisition_value, 2),
        gain_abs=0.0,
        gain_pct=0.0 if acquisition_value else None,
        ticker=ticker,
        chart_source=item.get("chart_source"),
        chart_label=item.get("chart_label"),
        has_chart=bool(ticker),
        is_stale=not bool(ticker),
    )


def _read_transaction_rows(source_file: Path) -> list[tuple[str, dict[str, str]]]:
    rows: list[tuple[str, dict[str, str]]] = []
    for row in _read_table_rows(source_file):
        rows.append((_transaction_row_hash(row), row))
    return rows


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
    if key not in holdings:
        ticker_mapping = _infer_transaction_ticker(row, data_dir)
        holdings[key] = {
            "id": isin.lower() if isin else f"{_slug(name)}-{hashlib.sha1(name.encode('utf-8')).hexdigest()[:8]}",
            "name": name,
            "short_name": name,
            "isin": isin,
            "instrument_type": "UNKNOWN",
            "market": None,
            "currency": (row.get("Instrumentvaluta") or row.get("Transaktionsvaluta") or "SEK").strip() or "SEK",
            "quantity": 0.0,
            "acquisition_value": 0.0,
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
    if quantity <= 0:
        return

    _key, holding = _ensure_ledger_holding(owner, row, data_dir)
    current_quantity = float(holding.get("quantity") or 0.0)
    current_acquisition = float(holding.get("acquisition_value") or 0.0)

    if transaction_type == "Köp":
        holding["quantity"] = round(current_quantity + quantity, 6)
        holding["acquisition_value"] = round(current_acquisition + abs(amount), 2)
        return

    sold_quantity = min(quantity, current_quantity)
    average_cost = current_acquisition / current_quantity if current_quantity else 0.0
    holding["quantity"] = round(current_quantity - sold_quantity, 6)
    holding["acquisition_value"] = round(max(0.0, current_acquisition - average_cost * sold_quantity), 2)


def _baseline_transactions_for_owner(owner: dict[str, Any], source_file: Path | None) -> None:
    if source_file is None:
        return
    processed = owner.setdefault("processed_transactions", {})
    for row_hash, row in _read_transaction_rows(source_file):
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
            _baseline_transactions_for_owner(owner, transaction_file)
            ledger["seed"]["owners"][owner_id] = {
                "position_file": position_file.name if position_file else None,
                "account_file": account_file.name if account_file else None,
                "transaction_file": transaction_file.name if transaction_file else None,
                "seeded_at": now,
            }
        ledger["owners"][owner_id] = owner
    return ledger


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
    applied: list[dict[str, Any]] = []
    for owner_id, owner_label, data_dir, source_file in latest_portfolio_transaction_files(root):
        owner = ledger.setdefault("owners", {}).setdefault(owner_id, _empty_ledger_owner(owner_id, owner_label))
        owner["owner_label"] = owner_label
        processed = owner.setdefault("processed_transactions", {})
        rows = _read_transaction_rows(source_file)
        new_rows = [(row_hash, row, index) for index, (row_hash, row) in enumerate(rows) if row_hash not in processed]
        for row_hash, row, _index in sorted(new_rows, key=lambda item: _transaction_sort_key(item[1], item[2])):
            _apply_transaction_to_ledger_owner(owner, row, data_dir)
            processed[row_hash] = {
                "source_file": source_file.name,
                "date": row.get("Datum"),
                "type": row.get("Typ av transaktion"),
                "baseline": False,
            }
            applied.append({"owner_id": owner_id, "date": row.get("Datum"), "type": row.get("Typ av transaktion")})
    if applied:
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
        value_update: dict[str, Any] = {}
        can_value_in_sek = holding.chart_source == "direct" and (holding.currency == "SEK" or holding.ticker.endswith(".ST"))
        if can_value_in_sek:
            owners = []
            for owner in holding.owners:
                owner_current_value = round(owner.quantity * snapshot.last, 2)
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
