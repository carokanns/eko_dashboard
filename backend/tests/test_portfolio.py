from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.models.summary import SparkPoint
from app.services.portfolio_data import build_portfolio_totals, load_combined_portfolio_holdings, load_portfolio_holdings, save_portfolio_snapshot


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


def test_portfolio_summary_with_flag_and_local_file(client: TestClient, monkeypatch, tmp_path):
    _write_positions(tmp_path, "JP_avanza")
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
    assert payload["totals"]["current_value"] == 1750.5
    assert len(payload["holdings"]) == 2
    assert payload["holdings"][0]["has_chart"] is True
    assert payload["holdings"][1]["has_chart"] is False
    assert payload["holdings"][0]["owners"][0]["owner_id"] == "jp"


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
