"""Synthetic quotes only: no Twelve Data credentials or live API requests in CI."""
from unittest.mock import patch
from fastapi.testclient import TestClient
import market_data as provider
import market_snapshot as snapshot
from main import app
client=TestClient(app)

def test_missing_key_fails_closed():
    with patch.object(provider, "API_KEY", ""):
        assert client.get("/api/quotes/snapshot").status_code==503

def test_snapshot_with_mock_quote_and_fx():
    snapshot._cached.__globals__["CACHE"].clear()
    def fake(path, params):
        if path=="/exchange_rate":
            return {"symbol":"USD/EUR", "rate":"0.85","timestamp":1793131200}
        raise AssertionError("Unexpected provider call")
    def quote(ticker):
        return {"currency":"USD", "price":200.0, "percent_change":1.0,
                "as_of":"2026-10-28T12:00:00+00:00","exchange":"NASDAQ",
                "market_open":True,"fetched_at":"2026-10-28T12:01:00+00:00"}
    with patch.object(provider,"API_KEY","synthetic"),patch.object(snapshot,"_provider_call",side_effect=fake),patch.object(snapshot,"latest",side_effect=quote):
        r=client.get("/api/quotes/snapshot")
        assert r.status_code==200,r.text
        result=r.json()
        assert result["currency"]=="EUR"
        assert result["fx"]["rate"]==0.85
        assert len(result["quotes"])==4
        assert all(q["eur"]==170.0 for q in result["quotes"])
        assert result["disclaimer"].lower().find("delayed")>=0
    snapshot._cached.__globals__["CACHE"].clear()

def test_bad_fx_rate_not_substituted():
    snapshot._cached.__globals__["CACHE"].clear()
    with patch.object(provider,"API_KEY","synthetic"),patch.object(snapshot,"_provider_call",return_value={"symbol":"USD/EUR","rate":"nan"}):
        assert client.get("/api/quotes/snapshot").status_code==502
    snapshot._cached.__globals__["CACHE"].clear()

def test_public_preview_read_only(monkeypatch):
    import main
    monkeypatch.setattr(main,"PUBLIC_PREVIEW",True)
    assert client.get("/api/quotes/status").status_code==200
    with patch.object(provider,"API_KEY",""):
        assert client.get("/api/quotes/snapshot").status_code==503
    assert client.get("/api/quotes/latest/AAPL").status_code==403
    assert client.post("/api/paypal/checkout",json={"tier":"premium"}).status_code==403
