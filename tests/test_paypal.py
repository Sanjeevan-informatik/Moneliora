"""PayPal tests use mock provider responses: never charge a real account."""
import os
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from main import app
import paypal_billing as paypal
from platform_features import db_conn

client=TestClient(app)

@pytest.fixture
def logged_in():
    import uuid
    r=client.post("/api/auth/register",json={"email":f"paypal-{uuid.uuid4().hex[:12]}@example.org","password":"A-strong-test-password-12345"})
    assert r.status_code==201,r.text
    yield {"csrf":r.json()["csrf"],"headers":{"x-csrf-token":r.json()["csrf"]}}
    client.post("/api/auth/logout",json={},headers={"x-csrf-token":r.json()["csrf"]})


def test_unconfigured_and_authentication(logged_in):
    with patch.object(paypal,"CLIENT_ID",""),patch.object(paypal,"CLIENT_SECRET",""):
        status=client.get("/api/paypal/status")
        assert status.status_code==200 and status.json()["configured"] is False
        assert client.post("/api/paypal/checkout",json={"tier":"premium"},headers=logged_in["headers"]).status_code==503
    assert client.post("/api/paypal/checkout",json={"tier":"invalid"},headers=logged_in["headers"]).status_code==422
    assert client.post("/api/paypal/checkout",json={"tier":"premium"}).status_code==403


def test_paypal_checkout_reconcile_cancel(logged_in):
    with patch.object(paypal,"CLIENT_ID","dummy"),patch.object(paypal,"CLIENT_SECRET","dummy"),\
         patch.object(paypal,"WEBHOOK_ID","test-webhook"),\
         patch.dict(paypal.PLANS,{"premium":"P-TESTPLAN123456789","pro":"P-TESTPLAN987654321"}),\
         patch.object(paypal,"_api") as remote:
        def respond(method,path,**kwargs):
            if method=="POST" and path=="/v1/billing/subscriptions":
                assert kwargs["payload"]["plan_id"]=="P-TESTPLAN123456789"
                return {"id":"I-TESTSUBSCRIPTION123","links":[{"rel":"approve","href":"https://www.sandbox.paypal.com/webapps/billing/subscriptions?ba_token=fake"}]}
            if method=="GET":
                with db_conn() as db:
                    rec=db.execute("SELECT intent_id FROM paypal_subscriptions WHERE subscription_id='I-TESTSUBSCRIPTION123'").fetchone()
                return {"id":"I-TESTSUBSCRIPTION123","plan_id":"P-TESTPLAN123456789",
                        "custom_id":rec["intent_id"],"status":"ACTIVE"}
            if method=="POST" and path.endswith("/cancel"):
                return {}
            raise AssertionError((method,path))
        remote.side_effect=respond
        r=client.post("/api/paypal/checkout",json={"tier":"premium"},headers=logged_in["headers"])
        assert r.status_code==200,r.text
        assert r.json()["approval_url"].startswith("https://www.sandbox.paypal.com/")
        assert client.post("/api/paypal/checkout",json={"tier":"premium"},headers=logged_in["headers"]).status_code==409
        # No premium entitlements before verifying the subscription with PayPal.
        assert client.get("/api/auth/me").json()["plan"]=="free"
        r=client.post("/api/paypal/sync",json={},headers=logged_in["headers"])
        assert r.status_code==200,r.text
        assert r.json()["status"]=="ACTIVE"
        assert client.get("/api/auth/me").json()["plan"]=="premium"
        r=client.post("/api/paypal/cancel",json={},headers=logged_in["headers"])
        assert r.status_code==200,r.text
        assert client.get("/api/auth/me").json()["plan"]=="free"


def test_webhook_rejection_and_approval_host(logged_in):
    assert client.post("/api/paypal/webhook",json={"event_type":"BILLING.SUBSCRIPTION.ACTIVATED"}).status_code==503
    with patch.object(paypal,"CLIENT_ID","dummy"),patch.object(paypal,"CLIENT_SECRET","dummy"),\
         patch.object(paypal,"WEBHOOK_ID","test-webhook"),patch.dict(paypal.PLANS,{"premium":"P-TESTPLAN123456789"}):
        assert client.post("/api/paypal/webhook",json={"id":"EV-123"}).status_code==400
        with pytest.raises(Exception):
            paypal._check_approval("https://attacker.example/approval")

def test_stripe_subscription_does_not_lose_paypal_entitlements(logged_in):
    user=client.get("/api/auth/me")
    assert user.status_code==200
    with db_conn() as db:
        uid=db.execute("SELECT id FROM users WHERE email=?",(user.json()["email"],)).fetchone()["id"]
        db.execute("INSERT INTO stripe_subscriptions(stripe_subscription_id,user_id,status) VALUES(?,?,?)",("sub_fake_"+str(uid),uid,"active"))
        db.commit()
    with patch.object(paypal,"CLIENT_ID","dummy"),patch.object(paypal,"CLIENT_SECRET","dummy"),\
         patch.object(paypal,"WEBHOOK_ID","test-webhook"),patch.dict(paypal.PLANS,{"premium":"P-TESTPLAN123456789"}):
        assert client.post("/api/paypal/checkout",json={"tier":"premium"},headers=logged_in["headers"]).status_code==409
