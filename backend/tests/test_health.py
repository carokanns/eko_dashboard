from fastapi.testclient import TestClient

from app.core.config import default_config_path, load_instruments


def test_health_payload(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data_source"] == "yahoo_finance"
    assert payload["last_update"] is None


def test_load_instruments_default_path():
    config_path = default_config_path()
    assert config_path.exists()
    instruments = load_instruments()
    assert instruments
    assert all(hasattr(item, "module") for item in instruments)


def test_commodities_summary_filters_module(client: TestClient):
    instruments = [i for i in load_instruments() if i.module == "commodities"]
    response = client.get("/api/commodities/summary")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == len(instruments)
    assert {item["id"] for item in items} == {item.id for item in instruments}
