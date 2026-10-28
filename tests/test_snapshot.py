"""Snapshot regression checks; no real provider calls."""
from unittest.mock import patch
from fastapi.testclient import TestClient
import market_data
import market_snapshot
from main import app

client = TestClient(app)

def test_unconfigured_snapshot_returns_service_unavailable():
    with patch.object(market_data, 'API_KEY', ''):
        assert client.get('/api/quotes/snapshot').status_code == 503

def test_snapshot_converts_all_supported_quotes():
    market_data.CACHE.clear()
    quote = dict(currency='USD', price=100, percent_change=1, as_of='2026-10-28',
                 exchange='TEST', market_open=False, fetched_at='2026-10-28')
    with patch.object(market_data, 'API_KEY', 'test-only'), \
         patch.object(market_snapshot, 'fx_quote', return_value={'rate': 0.9}), \
         patch.object(market_snapshot, 'latest', return_value=quote):
        response = client.get('/api/quotes/snapshot')
        assert response.status_code == 200
        assert len(response.json()['quotes']) == 4
        assert all(q['eur'] == 90 for q in response.json()['quotes'])
    market_data.CACHE.clear()
