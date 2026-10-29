from dataclasses import replace
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_public_demo_is_nontransactional(monkeypatch):
    monkeypatch.setitem(app.state._state, "settings", replace(app.state.settings, public_preview=True))
    r = client.get("/studio")
    assert r.status_code == 200
    assert "PUBLIC EDUCATIONAL PREVIEW" in r.text
    assert 'src="/static/account.js"' not in r.text
    assert 'src="/static/paypal.js"' not in r.text
    assert 'src="/static/market.js"' not in r.text
    h = client.get("/api/health")
    assert h.json()["mode"] == "public-preview"
    assert h.json()["live_trading"] is False
    assert h.json()["payments_enabled"] is False
    for path in ("/api/auth/me", "/api/paypal/status", "/api/billing/status",
                 "/api/market/status"):
        assert client.get(path).status_code == 403
    assert client.get("/api/quotes/status").status_code == 200
    assert client.get("/api/quotes/snapshot").status_code == 503
    assert client.post("/api/auth/register", json={
        "email": "demo@example.org", "password": "temporary-test-password-12345"
    }).status_code == 403
    assert client.post("/api/paypal/checkout", json={"tier":"premium"}).status_code == 403
