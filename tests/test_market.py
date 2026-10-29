"""Market integration tests use synthetic provider data; no API credentials or live requests."""
import os
os.environ.setdefault("MONELIORA_ADMIN_TOKEN", "a" * 64)
from fastapi.testclient import TestClient
import moneliora.integrations.market_data as m
from main import app
from unittest.mock import patch
client=TestClient(app)

def test_status_without_credentials():
    with patch.object(m,"API_KEY",""):
        r=client.get("/api/quotes/status")
        assert r.status_code==200 and r.json()["configured"] is False
        assert client.get("/api/quotes/latest/AAPL").status_code==503
        assert client.get("/api/quotes/chart/AAPL").status_code==503

def test_symbol_and_range_restrictions():
    assert client.get("/api/quotes/latest/UNKNOWN").status_code==404
    assert client.get("/api/quotes/chart/UNKNOWN").status_code==404
    assert client.get("/api/quotes/chart/AAPL?range=100Y").status_code==422

def test_quote_and_chart_with_mock_provider():
    def fake(path,params):
        if path=="/quote":
            return {"symbol":"AAPL","currency":"USD","close":"210.20","previous_close":"205.10",
                    "exchange":"NASDAQ","timestamp":1793131200,"is_market_open":False}
        return {"meta":{"symbol":"AAPL","currency":"USD","exchange":"NASDAQ","exchange_timezone":"America/New_York"},
                "values":[{"datetime":"2026-10-26","close":"208.00"},{"datetime":"2026-10-27","close":"210.20"}]}
    m.CACHE.clear()
    with patch.object(m,"API_KEY","synthetic-test-key"),patch.object(m,"_provider_call",side_effect=fake) as provider:
        q=client.get("/api/quotes/latest/AAPL")
        assert q.status_code==200,q.text
        assert q.json()["price"]==210.2
        assert q.json()["currency"]=="USD"
        assert q.json()["percent_change"]>0
        a=client.get("/api/quotes/chart/AAPL?range=1M")
        assert a.status_code==200,a.text
        assert len(a.json()["points"])==2
        assert a.json()["points"][0]["time"]=="2026-10-26"
        client.get("/api/quotes/latest/AAPL")
        client.get("/api/quotes/chart/AAPL?range=1M")
        assert provider.call_count==2
    m.CACHE.clear()

def test_malformed_provider_data_is_rejected():
    m.CACHE.clear()
    with patch.object(m,"API_KEY","synthetic-test-key"),patch.object(m,"_provider_call",return_value={"symbol":"AAPL","currency":"USD","close":"nan"}):
        assert client.get("/api/quotes/latest/AAPL").status_code==502
    with patch.object(m,"API_KEY","synthetic-test-key"),patch.object(m,"_provider_call",return_value={"meta":{"symbol":"AAPL","currency":"USD"},"values":[{"datetime":"2026-10-27","close":"-100"}]}):
        assert client.get("/api/quotes/chart/AAPL?range=1M").status_code==502
