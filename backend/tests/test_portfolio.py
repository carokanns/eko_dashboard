from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.models.summary import SparkPoint
from app.services.portfolio_data import build_portfolio_totals, load_portfolio_holdings, save_portfolio_snapshot


def _write_positions(tmp_path):
    data_dir = tmp_path / "avanza"
    data_dir.mkdir()
    (data_dir / "2026-06-11_positioner.csv").write_text(
        "\ufeffNamn;Kortnamn;Volym;Marknadsvärde;GAV (SEK);GAV;Valuta;Land;ISIN;Marknad;Typ\n"
        "Exempelbolag B;EX B;10;1500,50;100,00;100,00;SEK;SE;SE0000000001;XSTO;STOCK\n"
        "Exempelfond;Exempelfond;2,5;250,00;80,00;80,00;SEK;SE;SE0000000002;FUND;FUND\n",
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


def test_portfolio_summary_with_flag_and_local_file(client: TestClient, monkeypatch, tmp_path):
    data_dir = _write_positions(tmp_path)
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
    monkeypatch.setenv("LOCAL_PORTFOLIO_DATA_DIR", str(data_dir))
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


def test_portfolio_series_for_unmapped_holding_returns_empty(client: TestClient, monkeypatch, tmp_path):
    data_dir = _write_positions(tmp_path)
    monkeypatch.setenv("ENABLE_LOCAL_PORTFOLIO", "1")
    monkeypatch.setenv("LOCAL_PORTFOLIO_DATA_DIR", str(data_dir))

    fund_id = "se0000000002"
    response = client.get("/api/portfolio/series", params={"id": fund_id, "range": "1m"})
    assert response.status_code == 200
    assert response.json()["points"] == []
    assert response.json()["meta"]["stale_reason"] == "no_ticker_mapping"
