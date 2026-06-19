from __future__ import annotations

from app.providers import avanza_funds


def test_fetch_fund_nav_reads_public_fund_response(monkeypatch):
    monkeypatch.setattr(
        avanza_funds,
        "_post_json",
        lambda _payload: {
            "fundListViews": [
                {
                    "isin": "NO0010827280",
                    "name": "DNB Global Indeks S",
                    "nav": 171.77157,
                    "navDate": "2026-06-17T00:00:00",
                    "currencyCode": "SEK",
                    "orderbookId": "1509082",
                }
            ]
        },
    )

    quote = avanza_funds.fetch_fund_nav(isin="no0010827280", name="DNB Global Indeks S")

    assert quote.isin == "NO0010827280"
    assert quote.name == "DNB Global Indeks S"
    assert quote.nav == 171.77157
    assert quote.nav_date is not None
    assert quote.currency == "SEK"


def test_fetch_fund_nav_rejects_mismatched_isin(monkeypatch):
    monkeypatch.setattr(
        avanza_funds,
        "_post_json",
        lambda _payload: {"fundListViews": [{"isin": "SE0000000001", "name": "Another fund", "nav": 100}]},
    )

    try:
        avanza_funds.fetch_fund_nav(isin="NO0010827280", name="DNB Global Indeks S")
    except LookupError as error:
        assert "NO0010827280" in str(error)
    else:  # pragma: no cover - makes a failed validation unambiguous.
        raise AssertionError("Expected the provider to reject a mismatched ISIN.")
