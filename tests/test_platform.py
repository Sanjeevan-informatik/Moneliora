import os
import tempfile
from pathlib import Path
from datetime import date, timedelta
os.environ["MONELIORA_DB"]=str(Path(tempfile.mkdtemp())/"accounts.db")
os.environ["MONELIORA_ADMIN_TOKEN"]="z"*64
from fastapi.testclient import TestClient
from main import app
from platform_features import db_conn
client=TestClient(app)

def test_register_auth_csrf_portfolio_bookings_and_logout():
    email="student@example.org"
    r=client.post("/api/auth/register",json={"email":email,"password":"ThisIsAnExamplePassphrase-20"})
    assert r.status_code==201,r.text
    csrf=r.json()["csrf"]
    assert client.get("/api/auth/me").json()["email"]==email
    state={"cash":4500,"positions":{"NVDA":4},"watched":["NVDA"],"trades":[]}
    assert client.put("/api/account/state",json=state).status_code==403
    assert client.put("/api/account/state",json=state,headers={"x-csrf-token":csrf}).status_code==200
    assert client.get("/api/account/state").json()["state"]["positions"]["NVDA"]==4
    assert client.put("/api/account/state",json={**state,"positions":{"FAKE":4}},headers={"x-csrf-token":csrf}).status_code==422
    payload={"topic":"Paper trading introduction","preferred_date":str(date.today()+timedelta(days=5)),
             "preferred_time":"14:30","question":"How can I learn?"}
    r=client.post("/api/bookings",json=payload,headers={"x-csrf-token":csrf})
    assert r.status_code==201,r.text
    booking_id=r.json()["id"]
    assert len(client.get("/api/bookings").json()["bookings"])==1
    assert client.get("/api/admin/bookings").status_code==403
    assert client.delete(f"/api/bookings/{booking_id}",headers={"x-csrf-token":csrf}).status_code==200
    assert client.post("/api/auth/logout",json={},headers={"x-csrf-token":csrf}).status_code==200
    assert client.get("/api/auth/me").status_code==401
    assert client.post("/api/auth/login",json={"email":email,"password":"wrong-password-1234"}).status_code==401
    assert client.post("/api/auth/login",json={"email":email,"password":"ThisIsAnExamplePassphrase-20"}).status_code==200

def test_mfa_setup_and_require_code():
    import pyotp
    r=client.post("/api/auth/register",json={"email":"mfa@example.org","password":"AnotherPassword-1234567"})
    assert r.status_code==201
    csrf=r.json()["csrf"]
    r=client.post("/api/auth/mfa/setup",json={},headers={"x-csrf-token":csrf})
    assert r.status_code==200
    secret=r.json()["secret"]
    code=pyotp.TOTP(secret).now()
    r=client.post("/api/auth/mfa/confirm",json={"code":code},headers={"x-csrf-token":csrf})
    assert r.status_code==200
    client.post("/api/auth/logout",json={},headers={"x-csrf-token":csrf})
    assert client.post("/api/auth/login",json={"email":"mfa@example.org","password":"AnotherPassword-1234567"}).status_code==401
    assert client.post("/api/auth/login",json={"email":"mfa@example.org","password":"AnotherPassword-1234567","otp":code}).status_code==200

def test_optional_integrations_disabled():
    r=client.get("/api/market/status")
    assert r.status_code==200
    assert r.json()["configured"] is False
    assert client.get("/api/market/history/NVDA").status_code==503
    assert client.get("/api/market/history/OTHER").status_code==400
    assert client.get("/api/market/history/NVDA?days=999").status_code==422
