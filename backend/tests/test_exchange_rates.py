from __future__ import annotations

from app.services import exchange_rates


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return self._payload


def test_refresh_startup_exchange_rates_reads_frankfurter(monkeypatch):
    def fake_urlopen(_url, timeout):
        assert timeout == 10
        return _FakeResponse(b'{"amount":1.0,"base":"SEK","date":"2026-07-02","rates":{"THB":3.4282}}')

    monkeypatch.setattr(exchange_rates, "urlopen", fake_urlopen)

    exchange_rates.refresh_startup_exchange_rates()

    rate = exchange_rates.sek_to_thb_rate()
    assert rate.base == "SEK"
    assert rate.quote == "THB"
    assert rate.rate == 3.4282
    assert rate.source == "frankfurter"
    assert rate.ticker == "SEKTHB"
    assert rate.is_fallback is False
    assert rate.fetched_at.isoformat() == "2026-07-02T00:00:00+00:00"


def test_refresh_startup_exchange_rates_falls_back_on_invalid_response(monkeypatch):
    monkeypatch.setattr(exchange_rates, "urlopen", lambda *_args, **_kwargs: _FakeResponse(b'{"rates":{}}'))

    exchange_rates.refresh_startup_exchange_rates()

    rate = exchange_rates.sek_to_thb_rate()
    assert rate.rate == exchange_rates.SEK_TO_THB_FALLBACK_RATE
    assert rate.source == "fallback"
    assert rate.ticker == "SEKTHB"
    assert rate.is_fallback is True
    assert rate.stale_reason is not None
