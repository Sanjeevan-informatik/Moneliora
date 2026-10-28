import os
from datetime import date, timedelta
from pathlib import Path
import tempfile

os.environ["MONELIORA_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["MONELIORA_ADMIN_TOKEN"] = "a" * 64

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_and_headers():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["live_trading"] is False
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"

def test_validation_origin_and_admin():
    payload = {"name":"Valid Person","email":"test@example.org","topic":"Platform education",
               "preferred_date":str(date.today()+timedelta(days=5)),
               "message":"How do fees work?","privacy_accepted":True}
    assert client.post("/api/consultations", json=payload,
        headers={"Origin":"https://attacker.example"}).status_code == 403
    assert client.post("/api/consultations", data="bad",
        headers={"content-type":"text/plain"}).status_code == 415
    assert client.post("/api/consultations", json={**payload,"name":"<script>alert(1)</script>"}).status_code == 422
    assert client.post("/api/consultations", json={**payload,"privacy_accepted":False}).status_code == 400
    r = client.post("/api/consultations", json=payload)
    assert r.status_code == 201
    assert client.get("/api/admin/consultations").status_code == 401
    listing = client.get("/api/admin/consultations",headers={"x-admin-token":"a"*64})
    assert listing.status_code == 200
    assert listing.json()["requests"]
    item_id = r.json()["id"]
    assert client.delete(f"/api/admin/consultations/{item_id}",headers={"x-admin-token":"a"*64}).status_code == 200

def test_home():
    assert client.get("/").status_code == 200


def test_rejected_responses_have_security_headers():
    payload = {"name":"Test User","email":"test@example.org","topic":"Learning",
       "preferred_date":str(date.today()+timedelta(days=1)),
       "message":"","privacy_accepted":True}
    r=client.post("/api/consultations",json=payload,headers={"origin":"https://evil.example"})
    assert r.status_code==403
    assert r.headers["x-frame-options"]=="DENY"
    assert client.post("/api/consultations",json={**payload,"admin":True}).status_code==422
    assert client.post("/api/consultations",json=payload,headers={"content-length":"50000"}).status_code==413
