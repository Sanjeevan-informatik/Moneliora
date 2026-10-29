"""PayPal Subscriptions API integration. Sandbox-only by default.

Payment state is verified with PayPal on the server. Never trust browser return URLs
or unsigned webhook payloads. Requires merchant-approved plans and HTTPS webhooks.
"""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Annotated, Literal
from urllib.parse import urlparse
import os
import re
import secrets

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from moneliora.accounts import csrf_guard, session_auth, db_conn, now_iso, PUBLIC_URL, recompute_membership

router = APIRouter(prefix="/api/paypal", tags=["PayPal subscriptions"])
MODE = os.getenv("MONELIORA_PAYPAL_MODE", "sandbox").lower()
CLIENT_ID = os.getenv("MONELIORA_PAYPAL_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("MONELIORA_PAYPAL_CLIENT_SECRET", "")
WEBHOOK_ID = os.getenv("MONELIORA_PAYPAL_WEBHOOK_ID", "")
PLANS = {
    "premium": os.getenv("MONELIORA_PAYPAL_PREMIUM_PLAN_ID", "").strip(),
    "pro": os.getenv("MONELIORA_PAYPAL_PRO_PLAN_ID", "").strip(),
}
HOST = "https://api-m.paypal.com" if MODE == "live" else "https://api-m.sandbox.paypal.com"
SUB_ID = re.compile(r"^I-[A-Z0-9]{5,30}$")
EVENT_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
STATUSES = frozenset(["CREATING", "APPROVAL_PENDING", "APPROVED", "ACTIVE", "SUSPENDED", "CANCELLED", "EXPIRED"])
EVENT_TYPES = frozenset([
    "BILLING.SUBSCRIPTION.CREATED", "BILLING.SUBSCRIPTION.ACTIVATED",
    "BILLING.SUBSCRIPTION.UPDATED", "BILLING.SUBSCRIPTION.SUSPENDED",
    "BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED",
    "BILLING.SUBSCRIPTION.PAYMENT.FAILED",
])
# Serializes provider calls for the same process only. Shared DB transaction protects creation;
# public deployment needs a dedicated distributed worker and multi-instance reconciliation.
LOCK = Lock()


def configured() -> bool:
    return (MODE in ("sandbox", "live") and bool(CLIENT_ID and CLIENT_SECRET and WEBHOOK_ID)
            and bool(PLANS["premium"] or PLANS["pro"]))


def require_provider() -> None:
    if not configured():
        raise HTTPException(503, "PayPal subscriptions are not configured.")
    if MODE == "live" and not PUBLIC_URL.startswith("https://"):
        raise HTTPException(503, "Public HTTPS URL is required for live PayPal billing.")
    if not PUBLIC_URL.startswith(("https://", "http://127.0.0.1:", "http://localhost:")):
        raise HTTPException(503, "Invalid public return URL.")


def _token() -> str:
    try:
        with httpx.Client(timeout=8) as client:
            response = client.post(HOST + "/v1/oauth2/token", auth=(CLIENT_ID, CLIENT_SECRET),
                                   data={"grant_type": "client_credentials"},
                                   headers={"Accept": "application/json"})
            response.raise_for_status()
            token = response.json().get("access_token")
            if not isinstance(token, str) or not token:
                raise ValueError("Missing access token")
            return token
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise HTTPException(502, "PayPal authentication unavailable.") from None


def _api(method: str, path: str, *, payload: dict | None = None, request_id: str | None = None) -> dict:
    """Only calls server-constructed paths on an environment-selected PayPal host."""
    require_provider()
    if not path.startswith("/v1/") or path.startswith("//") or "?" in path or ".." in path:
        raise ValueError("Unsafe PayPal API path")
    headers = {"Authorization": "Bearer " + _token(), "Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if request_id is not None:
        headers["PayPal-Request-Id"] = request_id
    try:
        with httpx.Client(timeout=9) as client:
            response = client.request(method, HOST + path, headers=headers, json=payload)
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return {}
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Invalid PayPal response")
            return data
    except (httpx.HTTPError, ValueError, TypeError):
        # Do not leak sensitive merchant credentials or provider response bodies.
        raise HTTPException(502, "PayPal service unavailable. Check again later.") from None


def _check_approval(url: str) -> str:
    parsed = urlparse(url)
    allowed = "www.paypal.com" if MODE == "live" else "www.sandbox.paypal.com"
    if parsed.scheme != "https" or parsed.hostname != allowed or parsed.port is not None:
        raise HTTPException(502, "Invalid PayPal approval link.")
    if parsed.username or parsed.password:
        raise HTTPException(502, "Invalid PayPal approval link.")
    return url


def _subscription_remote(subscription_id: str, plan_id: str, intent_id: str) -> str:
    if not SUB_ID.fullmatch(subscription_id):
        raise HTTPException(502, "Invalid PayPal subscription identifier.")
    data = _api("GET", "/v1/billing/subscriptions/" + subscription_id)
    if data.get("id") != subscription_id or data.get("plan_id") != plan_id or data.get("custom_id") != intent_id:
        raise HTTPException(409, "Subscription does not match its original account and plan.")
    status = data.get("status")
    if status not in STATUSES - {"CREATING"}:
        raise HTTPException(502, "Unexpected PayPal subscription status.")
    return status


def _reconcile(db, row: dict) -> dict:
    status = _subscription_remote(row["subscription_id"], row["plan_id"], row["intent_id"])
    db.execute("UPDATE paypal_subscriptions SET status=?, updated_at=? WHERE user_id=? AND subscription_id=?",
               (status, now_iso(), row["user_id"], row["subscription_id"]))
    recompute_membership(db, row["user_id"])
    return {"tier": row["tier"], "status": status, "provider": "paypal",
            "subscription_id": row["subscription_id"]}


def _row(db, user_id: int) -> dict | None:
    rec = db.execute("SELECT * FROM paypal_subscriptions WHERE user_id=?", (user_id,)).fetchone()
    return dict(rec) if rec else None


def _prevent_duplicate(db, user_id: int) -> None:
    # Reject a second provider while existing rights or unresolved approval exist.
    row = _row(db, user_id)
    if row and row["status"] not in ("CANCELLED", "EXPIRED"):
        raise HTTPException(409, "A PayPal subscription is already active or awaiting approval.")
    stripe = db.execute(
        "SELECT 1 FROM stripe_subscriptions WHERE user_id=? AND status IN "
        "('active','trialing','past_due','incomplete') LIMIT 1", (user_id,)
    ).fetchone()
    if stripe:
        raise HTTPException(409, "An existing Stripe subscription needs to be managed first.")


class CheckoutInput(BaseModel):
    model_config = {"extra": "forbid"}
    tier: Literal["premium", "pro"]


@router.get("/status")
def status(user: Annotated[dict, Depends(session_auth)]):
    with db_conn() as db:
        row = _row(db, user["id"])
        current = db.execute("SELECT plan FROM users WHERE id=?", (user["id"],)).fetchone()
    return {
        "configured": configured(), "environment": MODE,
        "available_tiers": [name for name, code in PLANS.items() if code],
        "paypal": ({"tier": row["tier"], "status": row["status"],
                    "subscription_id": row["subscription_id"]} if row else None),
        "account_plan": current["plan"] if current else "free",
        "note": "PayPal shows the actual subscription price before approval. No subscription is activated from a browser redirect.",
    }


@router.post("/checkout")
def checkout(data: CheckoutInput, user: Annotated[dict, Depends(csrf_guard)]):
    require_provider()
    plan_id = PLANS[data.tier]
    if not plan_id or not re.fullmatch(r"P-[A-Z0-9-]{8,40}", plan_id):
        raise HTTPException(503, "This PayPal plan is not configured.")
    with LOCK:
        with db_conn() as db:
            # SQLite IMMEDIATE write lock prevents two identical checkouts racing.
            db.execute("BEGIN IMMEDIATE")
            _prevent_duplicate(db, user["id"])
            intent = secrets.token_urlsafe(24)
            db.execute("""INSERT INTO paypal_subscriptions
                (user_id,subscription_id,intent_id,tier,plan_id,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET subscription_id=NULL,intent_id=excluded.intent_id,
                tier=excluded.tier,plan_id=excluded.plan_id,status=excluded.status,updated_at=excluded.updated_at
                """,(user["id"],None,intent,data.tier,plan_id,"CREATING",now_iso(),now_iso()))
            db.commit()
        try:
            sub = _api("POST", "/v1/billing/subscriptions", request_id=intent, payload={
                "plan_id": plan_id, "custom_id": intent,
                "application_context": {
                    "brand_name": "Moneliora", "user_action": "SUBSCRIBE_NOW",
                    "shipping_preference": "NO_SHIPPING",
                    "return_url": PUBLIC_URL + "/?paypal=success#account",
                    "cancel_url": PUBLIC_URL + "/?paypal=cancelled#account",
                }
            })
            sub_id = sub.get("id", "")
            if not isinstance(sub_id, str) or not SUB_ID.fullmatch(sub_id):
                raise HTTPException(502, "PayPal did not return a valid subscription.")
            links = sub.get("links", [])
            approval = next((item.get("href") for item in links
                             if isinstance(item, dict) and item.get("rel") == "approve"), None)
            if not isinstance(approval, str):
                raise HTTPException(502, "PayPal did not return an approval link.")
            approval = _check_approval(approval)
            with db_conn() as db:
                cur = db.execute("""UPDATE paypal_subscriptions SET subscription_id=?,status=?,updated_at=?
                    WHERE user_id=? AND intent_id=? AND status='CREATING'""",
                    (sub_id,"APPROVAL_PENDING",now_iso(),user["id"],intent))
                if cur.rowcount != 1:
                    raise HTTPException(409, "Subscription request state changed.")
                db.commit()
            return {"approval_url": approval, "status":"APPROVAL_PENDING", "tier":data.tier}
        except Exception:
            # Ambiguous provider failures keep CREATING reserved, preventing accidental double charges.
            # A merchant administrator must reconcile the PayPal subscription before retrying.
            raise


@router.post("/sync")
def sync(user: Annotated[dict, Depends(csrf_guard)]):
    with db_conn() as db:
        rec = _row(db,user["id"])
        if not rec or not rec["subscription_id"]:
            raise HTTPException(404, "No PayPal subscription ready to verify.")
        result = _reconcile(db,rec)
        db.commit()
    return result


@router.post("/cancel")
def cancel(user: Annotated[dict, Depends(csrf_guard)]):
    with LOCK:
        with db_conn() as db:
            rec = _row(db,user["id"])
            if not rec or not rec["subscription_id"] or rec["status"] in ("CANCELLED","EXPIRED"):
                raise HTTPException(404,"No current PayPal subscription to cancel.")
            # Confirm it belongs to this user and expected plan at PayPal.
            remote = _subscription_remote(rec["subscription_id"],rec["plan_id"],rec["intent_id"])
            if remote in ("CANCELLED","EXPIRED"):
                result = _reconcile(db,rec)
                db.commit()
                return {"status":result["status"],"message":"Already ended at PayPal."}
            _api("POST","/v1/billing/subscriptions/"+rec["subscription_id"]+"/cancel",
                 payload={"reason":"Customer requested cancellation in Moneliora."})
            # Cancellation ends access immediately. No recurring charge will be initiated by this app.
            db.execute("UPDATE paypal_subscriptions SET status='CANCELLED',updated_at=? WHERE user_id=?",
                       (now_iso(),user["id"]))
            recompute_membership(db,user["id"])
            db.commit()
    return {"status":"CANCELLED","message":"Subscription cancellation requested at PayPal."}


def _verified_event(raw: bytes, request_headers) -> dict:
    try:
        event = __import__("json").loads(raw)
    except (ValueError, UnicodeError):
        raise HTTPException(400,"Invalid webhook JSON.") from None
    if not isinstance(event,dict) or not EVENT_ID.fullmatch(str(event.get("id",""))):
        raise HTTPException(400,"Invalid webhook event.")
    fields = ["paypal-transmission-id","paypal-transmission-time","paypal-cert-url",
              "paypal-auth-algo","paypal-transmission-sig"]
    headers = [request_headers.get(key) for key in fields]
    if not all(isinstance(value,str) and value for value in headers):
        raise HTTPException(400,"Missing PayPal webhook signature headers.")
    payload = dict(zip(["transmission_id","transmission_time","cert_url","auth_algo","transmission_sig"],headers))
    if payload["auth_algo"] != "SHA256withRSA":
        raise HTTPException(400,"Unsupported PayPal signature algorithm.")
    # Verify event against PayPal's first-party verification endpoint before any state change.
    result = _api("POST","/v1/notifications/verify-webhook-signature",payload={
        **payload,"webhook_id":WEBHOOK_ID,"webhook_event":event,
    })
    if result.get("verification_status") != "SUCCESS":
        raise HTTPException(400,"PayPal webhook signature verification failed.")
    return event


@router.post("/webhook")
async def webhook(request:Request):
    # Webhook is intentionally unauthenticated (no browser cookie/CSRF), but
    # the request is verified against PayPal and every subscription reconciled.
    if not configured():
        raise HTTPException(503,"PayPal webhooks disabled.")
    raw=await request.body()
    if len(raw)>65536:
        raise HTTPException(413,"Webhook payload too large.")
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(_webhook_sync,raw,request.headers)


def _webhook_sync(raw: bytes, headers) -> dict:
    event=_verified_event(raw,headers)
    event_id=event["id"]
    with db_conn() as db:
        if db.execute("SELECT 1 FROM paypal_events WHERE event_id=?",(event_id,)).fetchone():
            return {"received":True,"duplicate":True}
        kind=event.get("event_type")
        if kind in EVENT_TYPES:
            resource=event.get("resource",{})
            subid=resource.get("id") if isinstance(resource,dict) else None
            if isinstance(subid,str) and SUB_ID.fullmatch(subid):
                row=db.execute("SELECT * FROM paypal_subscriptions WHERE subscription_id=?",(subid,)).fetchone()
                if row:
                    _reconcile(db,dict(row))
        db.execute("INSERT INTO paypal_events(event_id,processed_at) VALUES(?,?)",(event_id,now_iso()))
        db.commit()
    return {"received":True}
