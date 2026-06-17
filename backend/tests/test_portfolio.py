from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi.testclient import TestClient

from app.models.summary import SparkPoint
from app.services.portfolio_data import (
    build_portfolio_totals,
    check_portfolio_transactions_for_updates,
    latest_portfolio_refresh_files,
    load_combined_portfolio_holdings,
    load_portfolio_accounts_from_ledger,
    load_portfolio_accounts,
    load_portfolio_holdings_from_ledger,
    load_portfolio_holdings,
    save_portfolio_snapshot,
    update_portfolio_ledger_from_transactions,
)


def _write_positions(tmp_path, dirname="avanza"):
    data_dir = tmp_path / dirname
    data_dir.mkdir()
    (data_dir / "2026-06-11_positioner.csv").write_text(
        "\ufeffNamn;Kortnamn;Volym;Marknadsvärde;GAV (SEK);GAV;Valuta;Land;ISIN;Marknad;Typ\n"
        "Exempelbolag B;EX B;10;1500,50;100,00;100,00;SEK;SE;SE0000000001;XSTO;STOCK\n"
        "Exempelfond;Exempelfond;2,5;250,00;80,00;80,00;SEK;SE;SE0000000002;FUND;FUND\n",
        encoding="utf-8",
    )
    return data_dir


def _write_single_position(
    base_dir,
    dirname,
    *,
    name="Exempelbolag B",
    short_name="EX B",
    isin="SE0000000001",
    quantity="10",
    current_value="1500,50",
    acquisition_price="100,00",
    market="XSTO",
    instrument_type="STOCK",
):
    data_dir = base_dir / dirname
    data_dir.mkdir()
    (data_dir / "2026-06-11_positioner.csv").write_text(
        "\ufeffNamn;Kortnamn;Volym;Marknadsvärde;GAV (SEK);GAV;Valuta;Land;ISIN;Marknad;Typ\n"
        f"{name};{short_name};{quantity};{current_value};{acquisition_price};{acquisition_price};SEK;SE;{isin};{market};{instrument_type}\n",
        encoding="utf-8",
    )
    return data_dir


def _write_account_summary(data_dir, *, bank_value="1234,00", isk_value="10000,00"):
    (data_dir / "2026-06-11_konto.csv").write_text(
        "\ufeffKontonummer;Kontotyp;Totalvärde;Lånebelopp\n"
        f"1111-1111111;Investeringssparkonto;{isk_value}\n"
        f"2222-2222222;Sparkonto;{bank_value}\n",
        encoding="utf-8",
    )


def _write_transactions(data_dir, *, rows: list[str] | None = None):
    transaction_rows = rows or [
        "2026-06-02;Bas ISK;Autogiroinsättning;Autogiroinsättning;;;1000;SEK;;;;;",
    ]
    (data_dir / "transaktioner_2026-01-01_2026-06-17.csv").write_text(
        "\ufeffDatum;Konto;Typ av transaktion;Värdepapper/beskrivning;Antal;Kurs;Belopp;Transaktionsvaluta;Courtage;Valutakurs;Instrumentvaluta;ISIN;Resultat\n"
        + "\n".join(transaction_rows)
        + "\n",
        encoding="utf-8",
    )


def _write_ods(path, rows: list[dict[str, str]]) -> None:
    pd.DataFrame(rows).to_excel(path, index=False, engine="odf")


def test_portfolio_endpoint_is_disabled_without_flag(client: TestClient, monkeypatch):
    monkeypatch.delenv("ENABLE_LOCAL_PORTFOLIO", raising=False)

    status = client.get("/api/portfolio/status")
    assert status.status_code == 200
    assert status.json()["configured"] is False

    response = client.get("/api/portfolio/summary")
    assert response.status_code == 404


def test_parser_reads_positions_and_totals(tmp_path):
    data_dir = _write_positions(tmp_path)

    holdings = load_portfolio_holdings(data_dir)
    assert [item.name for item in holdings] == ["Exempelbolag B", "Exempelfond"]
    assert holdings[0].quantity == 10
    assert holdings[0].current_value == 1500.5
    assert holdings[0].acquisition_value == 1000
    assert holdings[0].gain_abs == 500.5
    assert holdings[0].ticker == "EX-B.ST"
    assert holdings[1].ticker is None
    assert holdings[1].has_chart is False

    totals = build_portfolio_totals(holdings)
    assert totals.current_value == 1750.5
    assert totals.acquisition_value == 1200
    assert totals.holding_count == 2
    assert totals.chart_count == 1


def test_parser_reads_ods_positions_accounts_and_transactions(tmp_path):
    data_dir = tmp_path / "JP_avanza"
    data_dir.mkdir()
    _write_ods(
        data_dir / "2026-06-11_positioner.ods",
        [
            {
                "Namn": "Exempelbolag B",
                "Kortnamn": "EX B",
                "Volym": "10",
                "Marknadsvärde": "1500,50",
                "GAV (SEK)": "100,00",
                "GAV": "100,00",
                "Valuta": "SEK",
                "Land": "SE",
                "ISIN": "SE0000000001",
                "Marknad": "XSTO",
                "Typ": "STOCK",
            }
        ],
    )
    _write_ods(
        data_dir / "2026-06-11_konto.ods",
        [
            {"Kontonummer": "1111-1111111", "Kontotyp": "Investeringssparkonto", "Totalvärde": "10000,00"},
            {"Kontonummer": "2222-2222222", "Kontotyp": "Sparkonto", "Totalvärde": "1234,50"},
        ],
    )
    _write_ods(
        data_dir / "transaktioner_2026-01-01_2026-06-17.ods",
        [
            {
                "Datum": "2026-06-02",
                "Konto": "Bank",
                "Typ av transaktion": "Autogiroinsättning",
                "Värdepapper/beskrivning": "Autogiroinsättning",
                "Antal": "",
                "Kurs": "",
                "Belopp": "1000",
                "Transaktionsvaluta": "SEK",
                "Courtage": "",
                "Valutakurs": "",
                "Instrumentvaluta": "",
                "ISIN": "",
                "Resultat": "",
            }
        ],
    )

    holdings = load_portfolio_holdings(data_dir)
    accounts = load_portfolio_accounts(tmp_path)
    refresh_files = latest_portfolio_refresh_files(tmp_path)
    transaction_check = check_portfolio_transactions_for_updates(tmp_path)

    assert holdings[0].name == "Exempelbolag B"
    assert holdings[0].current_value == 1500.5
    assert accounts[0].bank_value == 1234.5
    assert refresh_files[0][4].suffix == ".ods"
    assert transaction_check["owners"][0]["row_count"] == 1


def test_local_fund_proxy_mapping_and_snapshots(tmp_path):
    data_dir = tmp_path / "avanza"
    data_dir.mkdir()
    (data_dir / "ticker-map.yaml").write_text(
        "mappings:\n"
        "  - isin: SE0000000100\n"
        "    ticker: ^OMX\n"
        "    source: proxy\n"
        "    label: 'Proxy: example index'\n",
        encoding="utf-8",
    )
    source_file = data_dir / "2026-06-11_positioner.csv"
    source_file.write_text(
        "\ufeffNamn;Kortnamn;Volym;Marknadsvärde;GAV (SEK);GAV;Valuta;Land;ISIN;Marknad;Typ\n"
        "Exempel Indexfond;Exempel Indexfond;20;1000,00;40,00;40,00;SEK;SE;SE0000000100;FUND;FUND\n"
        "Exempel Småfond;Exempel Småfond;1;100,00;90,00;90,00;SEK;SE;SE0000000200;FUND;FUND\n",
        encoding="utf-8",
    )

    holdings = load_portfolio_holdings(data_dir)
    mapped_fund = next(item for item in holdings if item.name == "Exempel Indexfond")
    unmapped_fund = next(item for item in holdings if item.name == "Exempel Småfond")
    assert mapped_fund.ticker == "^OMX"
    assert mapped_fund.chart_source == "proxy"
    assert "example index" in (mapped_fund.chart_label or "")
    assert unmapped_fund.ticker is None

    snapshots_path = save_portfolio_snapshot(data_dir, source_file, holdings)
    save_portfolio_snapshot(data_dir, source_file, holdings)
    snapshot_rows = snapshots_path.read_text(encoding="utf-8-sig").splitlines()
    assert len(snapshot_rows) == 3
    assert "2026-06-11;2026-06-11_positioner.csv;SE0000000100;Exempel Indexfond;20" in snapshot_rows[1]


def test_portfolio_status_is_enabled_with_only_pat_data(client: TestClient, monkeypatch, tmp_path):
    _write_single_position(tmp_path, "Pat_avanza")
    monkeypatch.setenv("ENABLE_LOCAL_PORTFOLIO", "1")
    monkeypatch.setenv("LOCAL_PORTFOLIO_BASE_DIR", str(tmp_path))
    monkeypatch.delenv("LOCAL_PORTFOLIO_DATA_DIR", raising=False)

    status = client.get("/api/portfolio/status")

    assert status.status_code == 200
    assert status.json()["enabled"] is True
    assert status.json()["has_data"] is True


def test_combined_portfolio_merges_same_isin_with_jp_first(tmp_path):
    _write_single_position(tmp_path, "JP_avanza", quantity="10", current_value="1500,00", acquisition_price="100,00")
    _write_single_position(tmp_path, "Pat_avanza", quantity="5", current_value="900,00", acquisition_price="120,00")

    holdings = load_combined_portfolio_holdings(tmp_path)

    assert len(holdings) == 1
    holding = holdings[0]
    assert holding.id == "se0000000001"
    assert holding.quantity == 15
    assert holding.current_value == 2400
    assert holding.acquisition_value == 1600
    assert holding.gain_abs == 800
    assert holding.gain_pct == 50
    assert [owner.owner_id for owner in holding.owners] == ["jp", "pat"]
    assert holding.owners[0].current_value == 1500
    assert holding.owners[1].current_value == 900


def test_combined_portfolio_keeps_different_holdings_separate(tmp_path):
    _write_single_position(tmp_path, "JP_avanza", isin="SE0000000001", current_value="1500,00")
    _write_single_position(
        tmp_path,
        "Pat_avanza",
        name="Annatbolag",
        short_name="ANN",
        isin="SE0000000002",
        current_value="900,00",
    )

    holdings = load_combined_portfolio_holdings(tmp_path)

    assert [holding.name for holding in holdings] == ["Exempelbolag B", "Annatbolag"]
    assert all(len(holding.owners) == 1 for holding in holdings)


def test_combined_portfolio_writes_snapshots_per_owner(tmp_path):
    jp_dir = _write_single_position(tmp_path, "JP_avanza", current_value="1500,00")
    pat_dir = _write_single_position(tmp_path, "Pat_avanza", current_value="900,00")

    load_combined_portfolio_holdings(tmp_path, save_snapshots=True)
    load_combined_portfolio_holdings(tmp_path, save_snapshots=True)

    jp_rows = (jp_dir / "snapshots" / "portfolio-snapshots.csv").read_text(encoding="utf-8-sig").splitlines()
    pat_rows = (pat_dir / "snapshots" / "portfolio-snapshots.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(jp_rows) == 2
    assert len(pat_rows) == 2
    assert ";1500.0;" in jp_rows[1]
    assert ";900.0;" in pat_rows[1]


def test_portfolio_accounts_read_bank_account_per_owner(tmp_path):
    jp_dir = _write_single_position(tmp_path, "JP_avanza")
    pat_dir = _write_single_position(tmp_path, "Pat_avanza")
    _write_account_summary(jp_dir, bank_value="1234,50", isk_value="10000,00")
    _write_account_summary(pat_dir, bank_value="2500,00", isk_value="20000,00")

    accounts = load_portfolio_accounts(tmp_path)

    assert [account.owner_id for account in accounts] == ["jp", "pat"]
    assert accounts[0].bank_value == 1234.5
    assert accounts[0].total_value == 11234.5
    assert accounts[1].bank_value == 2500
    assert accounts[1].total_value == 22500


def test_transaction_files_are_refresh_signal_when_present(tmp_path):
    jp_dir = _write_single_position(tmp_path, "JP_avanza")
    pat_dir = _write_single_position(tmp_path, "Pat_avanza")
    _write_account_summary(jp_dir)
    _write_account_summary(pat_dir)
    _write_transactions(pat_dir)

    refresh_files = latest_portfolio_refresh_files(tmp_path)

    assert [(owner_id, kind, source_file.name) for owner_id, _owner_label, _data_dir, kind, source_file in refresh_files] == [
        ("pat", "transactions", "transaktioner_2026-01-01_2026-06-17.csv")
    ]


def test_transaction_refresh_prefers_ods_when_csv_copy_exists(tmp_path):
    data_dir = _write_single_position(tmp_path, "JP_avanza")
    _write_transactions(data_dir)
    _write_ods(
        data_dir / "transaktioner_2026-01-01_2026-06-17.ods",
        [
            {
                "Datum": "2026-06-02",
                "Konto": "Bank",
                "Typ av transaktion": "Autogiroinsättning",
                "Värdepapper/beskrivning": "Autogiroinsättning",
                "Antal": "",
                "Kurs": "",
                "Belopp": "1000",
                "Transaktionsvaluta": "SEK",
                "Courtage": "",
                "Valutakurs": "",
                "Instrumentvaluta": "",
                "ISIN": "",
                "Resultat": "",
            }
        ],
    )

    refresh_files = latest_portfolio_refresh_files(tmp_path)

    assert refresh_files[0][4].name == "transaktioner_2026-01-01_2026-06-17.ods"


def test_startup_transaction_check_tracks_new_rows(tmp_path):
    pat_dir = _write_single_position(tmp_path, "Pat_avanza")
    _write_transactions(pat_dir)

    first = check_portfolio_transactions_for_updates(tmp_path)
    second = check_portfolio_transactions_for_updates(tmp_path)
    _write_transactions(
        pat_dir,
        rows=[
            "2026-06-02;Bas ISK;Autogiroinsättning;Autogiroinsättning;;;1000;SEK;;;;;",
            "2026-06-03;Bas ISK;Köp;Exempel;1;100;-100;SEK;;;;SE0000000001;",
        ],
    )
    third = check_portfolio_transactions_for_updates(tmp_path)

    assert first["has_updates"] is True
    assert first["owners"][0]["new_rows"] == 1
    assert second["has_updates"] is False
    assert second["owners"][0]["new_rows"] == 0
    assert third["has_updates"] is True
    assert third["owners"][0]["new_rows"] == 1


def test_ledger_seed_baselines_existing_transactions(tmp_path):
    data_dir = _write_single_position(tmp_path, "JP_avanza", quantity="10", current_value="1500,00", acquisition_price="100,00")
    _write_account_summary(data_dir, bank_value="1234,00", isk_value="10000,00")
    _write_transactions(
        data_dir,
        rows=[
            "2026-06-02;Bank;Autogiroinsättning;Autogiroinsättning;;;1000;SEK;;;;;",
        ],
    )

    first_update = update_portfolio_ledger_from_transactions(tmp_path)
    holdings = load_portfolio_holdings_from_ledger(tmp_path)
    accounts = load_portfolio_accounts_from_ledger(tmp_path)

    assert first_update["applied_count"] == 0
    assert holdings[0].quantity == 10
    assert holdings[0].acquisition_value == 1000
    assert accounts[0].bank_value == 1234


def test_ledger_applies_new_buy_transaction_after_seed(tmp_path):
    data_dir = _write_single_position(tmp_path, "JP_avanza", quantity="10", current_value="1500,00", acquisition_price="100,00")
    _write_account_summary(data_dir, bank_value="1234,00", isk_value="10000,00")
    _write_transactions(
        data_dir,
        rows=[
            "2026-06-02;Bas ISK;Autogiroinsättning;Autogiroinsättning;;;1000;SEK;;;;;",
        ],
    )
    update_portfolio_ledger_from_transactions(tmp_path)
    _write_transactions(
        data_dir,
        rows=[
            "2026-06-02;Bas ISK;Autogiroinsättning;Autogiroinsättning;;;1000;SEK;;;;;",
            "2026-06-03;Bas ISK;Köp;Exempelbolag B;2;100;-200;SEK;;;SEK;SE0000000001;",
        ],
    )

    update = update_portfolio_ledger_from_transactions(tmp_path)
    holdings = load_portfolio_holdings_from_ledger(tmp_path)

    assert update["applied_count"] == 1
    assert holdings[0].quantity == 12
    assert holdings[0].acquisition_value == 1200


def test_ledger_applies_new_bank_transaction_after_seed(tmp_path):
    data_dir = _write_single_position(tmp_path, "JP_avanza")
    _write_account_summary(data_dir, bank_value="1000,00", isk_value="10000,00")
    _write_transactions(data_dir, rows=[])
    update_portfolio_ledger_from_transactions(tmp_path)
    _write_transactions(
        data_dir,
        rows=[
            "2026-06-03;Bank;Inlåningsränta;Inlåningsränta;;;25;SEK;;;;;",
        ],
    )

    update = update_portfolio_ledger_from_transactions(tmp_path)
    accounts = load_portfolio_accounts_from_ledger(tmp_path)

    assert update["applied_count"] == 1
    assert accounts[0].bank_value == 1025


def test_portfolio_summary_with_flag_and_local_file(client: TestClient, monkeypatch, tmp_path):
    data_dir = _write_positions(tmp_path, "JP_avanza")
    _write_account_summary(data_dir, bank_value="1234,50", isk_value="1750,50")
    _write_transactions(data_dir)
    now = datetime.now(timezone.utc)

    def fake_enrich(holdings):
        return [
            item.model_copy(
                update={
                    "has_chart": bool(item.ticker),
                    "is_stale": not bool(item.ticker),
                    "last": 123.0 if item.ticker else None,
                    "day_abs": 1.0 if item.ticker else None,
                    "day_pct": 0.82 if item.ticker else None,
                    "sparkline": [SparkPoint(t=now - timedelta(days=1), v=122.0), SparkPoint(t=now, v=123.0)] if item.ticker else [],
                }
            )
            for item in holdings
        ]

    monkeypatch.setenv("ENABLE_LOCAL_PORTFOLIO", "1")
    monkeypatch.setenv("LOCAL_PORTFOLIO_BASE_DIR", str(tmp_path))
    monkeypatch.delenv("LOCAL_PORTFOLIO_DATA_DIR", raising=False)
    monkeypatch.setattr("app.routes.portfolio.enrich_holdings_with_market_data", fake_enrich)

    status = client.get("/api/portfolio/status")
    assert status.status_code == 200
    assert status.json()["enabled"] is True

    response = client.get("/api/portfolio/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["meta"]["source"] == "local_avanza_export"
    assert payload["totals"]["current_value"] == 1200
    assert len(payload["holdings"]) == 2
    assert payload["holdings"][0]["has_chart"] is True
    assert payload["holdings"][1]["has_chart"] is False
    assert payload["holdings"][0]["owners"][0]["owner_id"] == "jp"
    assert payload["accounts"][0]["owner_id"] == "jp"
    assert payload["accounts"][0]["bank_value"] == 1234.5
    assert any(item["kind"] == "transactions" for item in payload["meta"]["refresh_files"])


def test_portfolio_series_for_unmapped_holding_returns_empty(client: TestClient, monkeypatch, tmp_path):
    _write_positions(tmp_path, "JP_avanza")
    monkeypatch.setenv("ENABLE_LOCAL_PORTFOLIO", "1")
    monkeypatch.setenv("LOCAL_PORTFOLIO_BASE_DIR", str(tmp_path))
    monkeypatch.delenv("LOCAL_PORTFOLIO_DATA_DIR", raising=False)

    fund_id = "se0000000002"
    response = client.get("/api/portfolio/series", params={"id": fund_id, "range": "1m"})
    assert response.status_code == 200
    assert response.json()["points"] == []
    assert response.json()["meta"]["stale_reason"] == "no_ticker_mapping"
