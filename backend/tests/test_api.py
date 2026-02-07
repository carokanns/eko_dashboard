from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import default_config_path, load_instruments
from app.models.summary import SparkPoint, SummaryItem


def _sample_item(item_id: str, name: str, stale: bool = False) -> SummaryItem:
    now = datetime.now(timezone.utc)
    return SummaryItem(
        id=item_id,
        name=name,
        unit="USD",
        price_type="Spot",
        last=100.0,
        day_abs=1.0,
        day_pct=1.01,
        w1_pct=2.2,
        ytd_pct=3.3,
        y1_pct=4.4,
        timestamp_local=now,
        is_stale=stale,
        sparkline=[SparkPoint(t=now - timedelta(days=1), v=99.0), SparkPoint(t=now, v=100.0)],
    )


def test_health_payload(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data_source"] == "yahoo_finance"
    assert payload["provider"]["name"] == "yfinance"
    assert payload["cache"]["ttl_seconds"] == 60
    assert payload["last_update"] is None


def test_health_last_update_after_successful_fetch(client: TestClient, monkeypatch):
    def fake_fetch_summary(instruments):
        items = [_sample_item(i.id, i.name_sv) for i in instruments]
        return items, {}

    monkeypatch.setattr("app.routes.commodities.fetch_summary_for_instruments", fake_fetch_summary)
    response = client.get("/api/commodities/summary")
    assert response.status_code == 200

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["last_update"] is not None


def test_load_instruments_default_path():
    config_path = default_config_path()
    assert config_path.exists()
    instruments = load_instruments()
    assert instruments
    assert all(hasattr(item, "module") for item in instruments)


def test_commodities_summary_response_shape_and_cache(client: TestClient, monkeypatch):
    calls = {"count": 0}

    def fake_fetch_summary(instruments):
        calls["count"] += 1
        items = [_sample_item(i.id, i.name_sv) for i in instruments]
        return items, {}

    monkeypatch.setattr("app.routes.commodities.fetch_summary_for_instruments", fake_fetch_summary)

    first = client.get("/api/commodities/summary")
    assert first.status_code == 200
    payload = first.json()
    assert payload["meta"]["source"] == "yahoo_finance"
    assert payload["meta"]["cached"] is False
    assert isinstance(payload["meta"]["fetched_at"], str)
    assert payload["items"]

    second = client.get("/api/commodities/summary")
    assert second.status_code == 200
    payload2 = second.json()
    assert payload2["meta"]["cached"] is True
    assert calls["count"] == 1


def test_mag7_summary_partial_data_marks_stale(client: TestClient, monkeypatch):
    def fake_fetch_summary(instruments):
        output = []
        for index, item in enumerate(instruments):
            output.append(_sample_item(item.id, item.name_sv, stale=index == 0))
        return output, {"AAPL": "upstream issue"}

    monkeypatch.setattr("app.routes.mag7.fetch_summary_for_instruments", fake_fetch_summary)
    response = client.get("/api/mag7/summary")
    assert response.status_code == 200
    items = response.json()["items"]
    assert any(row["is_stale"] for row in items)
    assert any(not row["is_stale"] for row in items)


def test_commodities_series_validates_range_and_uses_cache(client: TestClient, monkeypatch):
    now = datetime.now(timezone.utc)
    calls = {"count": 0}

    def fake_series(_instrument, _range):
        calls["count"] += 1
        return [SparkPoint(t=now - timedelta(days=1), v=42.0), SparkPoint(t=now, v=43.0)]

    monkeypatch.setattr("app.routes.commodities.fetch_series_for_instrument", fake_series)

    response = client.get("/api/commodities/series", params={"id": "brent", "range": "1m"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["range"] == "1m"
    assert len(payload["points"]) == 2
    assert payload["meta"]["cached"] is False

    cached = client.get("/api/commodities/series", params={"id": "brent", "range": "1m"})
    assert cached.status_code == 200
    assert cached.json()["meta"]["cached"] is True
    assert calls["count"] == 1

    invalid = client.get("/api/commodities/series", params={"id": "brent", "range": "10y"})
    assert invalid.status_code == 422


def test_commodities_series_unknown_id_returns_404(client: TestClient):
    response = client.get("/api/commodities/series", params={"id": "unknown-id", "range": "1m"})
    assert response.status_code == 404


def test_health_last_update_unchanged_when_all_items_stale(client: TestClient, monkeypatch):
    def fake_fetch_summary(instruments):
        items = []
        for item in instruments:
            items.append(
                SummaryItem(
                    id=item.id,
                    name=item.name_sv,
                    unit=item.unit_label,
                    price_type=item.price_type,
                    last=None,
                    day_abs=None,
                    day_pct=None,
                    w1_pct=None,
                    ytd_pct=None,
                    y1_pct=None,
                    timestamp_local=None,
                    is_stale=True,
                    sparkline=[],
                )
            )
        return items, {item.ticker: "upstream unavailable" for item in instruments}

    monkeypatch.setattr("app.routes.commodities.fetch_summary_for_instruments", fake_fetch_summary)
    response = client.get("/api/commodities/summary")
    assert response.status_code == 200

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["last_update"] is None
