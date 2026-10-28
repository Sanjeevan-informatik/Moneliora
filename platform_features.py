"""Optional account, booking and payment foundation. Never executes investment orders."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen
import hmac
import json
import os
import secrets
import sqlite3
import time

import pyotp
from argon2 import PasswordHasher, exceptions as argon_exc
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

router = APIRouter()
DB = Path(os.getenv("MONELIORA_DB", str(Path(__file__).resolve().parent / "data" / "moneliora.db")))
COOKIE_SECURE = os.getenv("MONELIORA_SECURE_COOKIES", "false").lower() == "true"
MARKET_API_KEY = os.getenv("MONELIORA_TWELVE_DATA_KEY", "")
STRIPE_SECRET = os.getenv("MONELIORA_STRIPE_SECRET_KEY", "")
STRIPE_PRICE = os.getenv("MONELIORA_STRIPE_PRICE_ID", "")
STRIPE_WEBHOOK = os.getenv("MONELIORA_STRIPE_WEBHOOK_SECRET", "")
PUBLIC_URL = os.getenv("MONELIORA_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
PASSWORD = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
AUTH_LOCK = Lock()
AUTH_ATTEMPTS: dict[str, list[float]] = {}
SESSION_SECONDS = 12 * 3600
SYMBOLS = frozenset(["NVDA", "MSFT", "AAPL", "TSLA", "XIA", "BYD", "IFX", "VW", "AIR"])
US_SYMBOLS = frozenset(["NVDA", "MSFT", "AAPL", "TSLA"])
MARKET_CACHE: dict[str, tuple[float, dict]] = {}
MARKET_LOCK = Lock()

def db_conn():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
           id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE,
           password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user',
           mfa_secret TEXT, mfa_pending TEXT, created_at TEXT NOT NULL,
           failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT,
           plan TEXT NOT NULL DEFAULT 'free'
        );
        CREATE TABLE IF NOT EXISTS sessions(
           token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
           csrf TEXT NOT NULL, expires_at TEXT NOT NULL,
           FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS account_states(
           user_id INTEGER PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL,
           FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS booking_requests(
           id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
           topic TEXT NOT NULL, preferred_date TEXT NOT NULL, preferred_time TEXT NOT NULL,
           question TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
           created_at TEXT NOT NULL,
           FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS stripe_subscriptions(
           stripe_subscription_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
           stripe_customer_id TEXT, status TEXT NOT NULL,
           FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS paypal_subscriptions(
          user_id INTEGER PRIMARY KEY, subscription_id TEXT UNIQUE, intent_id TEXT NOT NULL,
          tier TEXT NOT NULL, plan_id TEXT NOT NULL, status TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS paypal_events(event_id TEXT PRIMARY KEY, processed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS stripe_events(
           event_id TEXT PRIMARY KEY, processed_at TEXT NOT NULL
        );
    """)
    return db

def recompute_membership(db, user_id: int) -> None:
    paypal = db.execute("SELECT tier FROM paypal_subscriptions WHERE user_id=? AND status='ACTIVE'", (user_id,)).fetchone()
    stripe = db.execute("SELECT 1 FROM stripe_subscriptions WHERE user_id=? AND status IN ('active','trialing') LIMIT 1",(user_id,)).fetchone()
    db.execute("UPDATE users SET plan=? WHERE id=?", (paypal["tier"] if paypal else ("premium" if stripe else "free"),user_id))

def utc_now():
    return datetime.now(timezone.utc)

def now_iso():
    return utc_now().isoformat()

def login_limiter(key: str):
    current = time.monotonic()
    with AUTH_LOCK:
        # prune keys to avoid indefinite storage growth
        if len(AUTH_ATTEMPTS) > 10000:
            for k in list(AUTH_ATTEMPTS):
                AUTH_ATTEMPTS[k] = [t for t in AUTH_ATTEMPTS[k] if current-t < 900]
                if not AUTH_ATTEMPTS[k]:
                    del AUTH_ATTEMPTS[k]
        hits = [t for t in AUTH_ATTEMPTS.get(key, []) if current-t < 900]
        if len(hits) >= 8:
            raise HTTPException(429, "Too many attempts. Try again later.")
        hits.append(current)
        AUTH_ATTEMPTS[key] = hits

def session_auth(moneliora_session: Annotated[str | None, Cookie()] = None):
    if not moneliora_session:
        raise HTTPException(401, "Please sign in.")
    hashed = sha256(moneliora_session.encode()).hexdigest()
    with db_conn() as db:
        row = db.execute("""
            SELECT u.id, u.email, u.role, u.mfa_secret, u.plan, s.csrf, s.expires_at
            FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?
        """, (hashed,)).fetchone()
    if not row or row["expires_at"] <= now_iso():
        raise HTTPException(401, "Session expired. Please sign in again.")
    return dict(row)

def csrf_guard(
    request: Request,
    user: Annotated[dict, Depends(session_auth)],
    x_csrf_token: Annotated[str | None, Header()] = None,
):
    if not x_csrf_token or not hmac.compare_digest(x_csrf_token, user["csrf"]):
        raise HTTPException(403, "Security token missing or invalid.")
    return user

def admin_user(user: Annotated[dict, Depends(session_auth)]):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access required.")
    return user

def admin_write(request: Request, user: Annotated[dict, Depends(csrf_guard)]):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access required.")
    return user

class AuthInput(BaseModel):
    model_config = {"extra": "forbid"}
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    otp: str | None = Field(default=None, pattern=r"^\d{6}$")

class MFAConfirm(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")

class MFADisable(BaseModel):
    password: str
    code: str = Field(pattern=r"^\d{6}$")

def issue_session(db, user_id: int, response: Response):
    raw = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    until = (utc_now()+timedelta(seconds=SESSION_SECONDS)).isoformat()
    db.execute("DELETE FROM sessions WHERE user_id=? OR expires_at<?", (user_id, now_iso()))
    db.execute("INSERT INTO sessions(token_hash,user_id,csrf,expires_at) VALUES(?,?,?,?)",
               (sha256(raw.encode()).hexdigest(), user_id, csrf, until))
    response.set_cookie("moneliora_session", raw, max_age=SESSION_SECONDS, httponly=True,
                        secure=COOKIE_SECURE, samesite="strict", path="/")
    return csrf

@router.post("/api/auth/register", status_code=201)
def register(payload: AuthInput, response: Response, request: Request):
    login_limiter("register:"+str(request.client.host if request.client else "unknown"))
    email = str(payload.email).lower()
    hashed = PASSWORD.hash(payload.password)
    try:
        with db_conn() as db:
            cursor = db.execute("INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)",
                                (email, hashed, now_iso()))
            csrf = issue_session(db, cursor.lastrowid, response)
            db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account with this email already exists.")
    return {"email":email, "role":"user", "csrf":csrf, "mfa_enabled":False, "plan":"free"}

@router.post("/api/auth/login")
def login(payload: AuthInput, response: Response, request: Request):
    login_limiter("login:"+str(request.client.host if request.client else "unknown")+":"+str(payload.email).lower())
    with db_conn() as db:
        row = db.execute("SELECT * FROM users WHERE email=?", (str(payload.email).lower(),)).fetchone()
        if row and row["locked_until"] and row["locked_until"] > now_iso():
            raise HTTPException(429, "Account temporarily locked. Try again later.")
        ok = False
        if row:
            try:
                ok = PASSWORD.verify(row["password_hash"], payload.password)
            except (argon_exc.VerifyMismatchError, argon_exc.VerificationError, argon_exc.InvalidHashError):
                ok = False
        if not ok or (row and row["mfa_secret"] and
                       not (payload.otp and pyotp.TOTP(row["mfa_secret"]).verify(payload.otp, valid_window=1))):
            if row:
                attempts = row["failed_attempts"]+1
                lock_until = (utc_now()+timedelta(minutes=15)).isoformat() if attempts>=8 else None
                db.execute("UPDATE users SET failed_attempts=?,locked_until=? WHERE id=?",
                           (attempts if attempts<8 else 0, lock_until, row["id"]))
                db.commit()
            raise HTTPException(401, "Incorrect credentials or authentication code.")
        db.execute("UPDATE users SET failed_attempts=0,locked_until=NULL WHERE id=?", (row["id"],))
        csrf = issue_session(db, row["id"], response)
        db.commit()
        return {"email":row["email"],"role":row["role"],"csrf":csrf,
                "mfa_enabled":bool(row["mfa_secret"]),"plan":row["plan"]}

@router.get("/api/auth/me")
def me(user: Annotated[dict, Depends(session_auth)]):
    return {"email":user["email"],"role":user["role"],"csrf":user["csrf"],
            "mfa_enabled":bool(user["mfa_secret"]),"plan":user["plan"]}

@router.post("/api/auth/logout")
def logout(response: Response, user: Annotated[dict, Depends(csrf_guard)],
           moneliora_session: Annotated[str | None, Cookie()] = None):
    with db_conn() as db:
        db.execute("DELETE FROM sessions WHERE token_hash=?", (sha256((moneliora_session or "").encode()).hexdigest(),))
        db.commit()
    response.delete_cookie("moneliora_session", path="/", httponly=True,
                           secure=COOKIE_SECURE, samesite="strict")
    return {"signed_out":True}

@router.post("/api/auth/mfa/setup")
def mfa_setup(user: Annotated[dict, Depends(csrf_guard)]):
    if user["mfa_secret"]:
        raise HTTPException(409, "Two-factor authentication already enabled.")
    secret = pyotp.random_base32()
    with db_conn() as db:
        db.execute("UPDATE users SET mfa_pending=? WHERE id=?", (secret, user["id"]))
        db.commit()
    url = pyotp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="Moneliora")
    return {"secret":secret,"otpauth_uri":url,"note":"Keep this secret private; confirm the code to enable MFA."}

@router.post("/api/auth/mfa/confirm")
def mfa_confirm(payload: MFAConfirm, user: Annotated[dict, Depends(csrf_guard)]):
    with db_conn() as db:
        row = db.execute("SELECT mfa_pending FROM users WHERE id=?", (user["id"],)).fetchone()
        if not row or not row["mfa_pending"] or not pyotp.TOTP(row["mfa_pending"]).verify(payload.code,valid_window=1):
            raise HTTPException(400, "Invalid or expired authentication code.")
        db.execute("UPDATE users SET mfa_secret=mfa_pending,mfa_pending=NULL WHERE id=?", (user["id"],))
        db.commit()
    return {"mfa_enabled":True}

@router.post("/api/auth/mfa/disable")
def mfa_disable(payload: MFADisable, user: Annotated[dict, Depends(csrf_guard)]):
    with db_conn() as db:
        row = db.execute("SELECT password_hash,mfa_secret FROM users WHERE id=?", (user["id"],)).fetchone()
        try:
            correct = PASSWORD.verify(row["password_hash"],payload.password)
        except (argon_exc.VerifyMismatchError, argon_exc.VerificationError, argon_exc.InvalidHashError):
            correct = False
        if not correct or not row["mfa_secret"] or not pyotp.TOTP(row["mfa_secret"]).verify(payload.code,valid_window=1):
            raise HTTPException(401, "Password or authentication code incorrect.")
        db.execute("UPDATE users SET mfa_secret=NULL,mfa_pending=NULL WHERE id=?", (user["id"],))
        db.commit()
    return {"mfa_enabled":False}

class TradeState(BaseModel):
    symbol: str
    qty: int = Field(ge=1,le=100000)
    amount: float = Field(ge=0,le=5000000)
    side: Literal["buy","sell"]
    date: str = Field(max_length=100)

class AccountState(BaseModel):
    model_config = {"extra": "forbid"}
    cash: float = Field(ge=0,le=5000)
    positions: dict[str,int] = Field(default_factory=dict, max_length=9)
    watched: list[str] = Field(default_factory=list,max_length=9)
    trades: list[TradeState] = Field(default_factory=list,max_length=30)

    @model_validator(mode="after")
    def valid_symbols(self):
        if any(s not in SYMBOLS or not isinstance(v,int) or v<0 or v>100000
               for s,v in self.positions.items()):
            raise ValueError("Invalid example symbol or share quantity.")
        if any(s not in SYMBOLS for s in self.watched) or len(set(self.watched))!=len(self.watched):
            raise ValueError("Watchlist symbols must be unique and supported.")
        if any(t.symbol not in SYMBOLS for t in self.trades):
            raise ValueError("Invalid trade symbol.")
        return self

@router.get("/api/account/state")
def get_state(user: Annotated[dict, Depends(session_auth)]):
    with db_conn() as db:
        row=db.execute("SELECT data,updated_at FROM account_states WHERE user_id=?", (user["id"],)).fetchone()
    return {"state":json.loads(row["data"]) if row else None,"updated_at":row["updated_at"] if row else None}

@router.put("/api/account/state")
def put_state(payload: AccountState,user: Annotated[dict, Depends(csrf_guard)]):
    with db_conn() as db:
        db.execute("""INSERT INTO account_states(user_id,data,updated_at) VALUES(?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at""",
            (user["id"],payload.model_dump_json(),now_iso()))
        db.commit()
    return {"saved":True}

class BookingInput(BaseModel):
    model_config={"extra":"forbid"}
    topic: str = Field(min_length=3,max_length=80)
    preferred_date: date
    preferred_time: str = Field(pattern=r"^(0[8-9]|1[0-9]|20):[0-5][0-9]$")
    question: str = Field(default="",max_length=500)

    @field_validator("topic","question")
    @classmethod
    def plain_text(cls,v):
        if any(ord(c)<32 and c not in "\n\t" for c in v) or "<" in v or ">" in v:
            raise ValueError("Markup is not allowed")
        return v.strip()

    @field_validator("preferred_date")
    @classmethod
    def valid_date(cls,v):
        if v<date.today() or v>date.today()+timedelta(days=90):
            raise ValueError("Date must be within the next 90 days.")
        return v

@router.post("/api/bookings",status_code=201)
def request_booking(payload: BookingInput,user: Annotated[dict,Depends(csrf_guard)]):
    with db_conn() as db:
        count=db.execute("SELECT COUNT(*) FROM booking_requests WHERE user_id=? AND status='pending'",(user["id"],)).fetchone()[0]
        if count>=3:
            raise HTTPException(429,"Only 3 pending requests are allowed.")
        cur=db.execute("""INSERT INTO booking_requests(user_id,topic,preferred_date,preferred_time,question,created_at)
            VALUES(?,?,?,?,?,?)""",(user["id"],payload.topic,str(payload.preferred_date),
            payload.preferred_time,payload.question,now_iso()))
        db.commit()
    return {"id":cur.lastrowid,"status":"pending","note":"A request, not a confirmed appointment. Times in Europe/Berlin."}

@router.get("/api/bookings")
def list_bookings(user: Annotated[dict,Depends(session_auth)]):
    with db_conn() as db:
        rows=db.execute("""SELECT id,topic,preferred_date,preferred_time,question,status,created_at
                         FROM booking_requests WHERE user_id=? ORDER BY id DESC LIMIT 30""",(user["id"],)).fetchall()
    return {"timezone":"Europe/Berlin","bookings":[dict(r) for r in rows]}

@router.delete("/api/bookings/{booking_id}")
def cancel_booking(booking_id:int,user: Annotated[dict,Depends(csrf_guard)]):
    with db_conn() as db:
        cur=db.execute("UPDATE booking_requests SET status='cancelled' WHERE id=? AND user_id=? AND status='pending'",
                       (booking_id,user["id"]))
        db.commit()
    if not cur.rowcount:
        raise HTTPException(404,"Pending booking request not found.")
    return {"status":"cancelled"}

@router.get("/api/admin/bookings")
def admin_bookings(user: Annotated[dict,Depends(admin_user)]):
    with db_conn() as db:
        rows=db.execute("""SELECT b.id,u.email,b.topic,b.preferred_date,b.preferred_time,
                         b.question,b.status FROM booking_requests b JOIN users u ON b.user_id=u.id
                         ORDER BY b.id DESC LIMIT 100""").fetchall()
    return {"timezone":"Europe/Berlin","bookings":[dict(r) for r in rows]}

class BookingStatus(BaseModel):
    status: Literal["pending","confirmed","cancelled"]

@router.put("/api/admin/bookings/{booking_id}")
def admin_booking_status(booking_id:int,payload:BookingStatus,user:Annotated[dict,Depends(admin_write)]):
    with db_conn() as db:
        cur=db.execute("UPDATE booking_requests SET status=? WHERE id=?",(payload.status,booking_id))
        db.commit()
    if not cur.rowcount:
        raise HTTPException(404,"Booking request not found.")
    return {"status":payload.status}

@router.get("/api/market/status")
def market_status():
    return {"configured":bool(MARKET_API_KEY),"provider":"Twelve Data",
            "symbols":sorted(US_SYMBOLS),"currency":"USD",
            "note":"Daily historical data only when licensed API key is configured. Demo prices are separate."}

@router.get("/api/market/history/{symbol}")
def market_history(symbol:str,days:int=Query(default=30,ge=5,le=90)):
    symbol=symbol.upper()
    if symbol not in US_SYMBOLS:
        raise HTTPException(400,"Historical data is currently supported for selected US stocks.")
    if not MARKET_API_KEY:
        raise HTTPException(503,"Market provider not configured. No live data available.")
    cache_key=symbol+":"+str(days)
    with MARKET_LOCK:
        cached=MARKET_CACHE.get(cache_key)
        if cached and time.monotonic()-cached[0]<900:
            return cached[1]
    params=urlencode({"symbol":symbol,"interval":"1day","outputsize":days,"apikey":MARKET_API_KEY})
    req=URLRequest("https://api.twelvedata.com/time_series?"+params,headers={"User-Agent":"Moneliora-educational/1"})
    try:
        with urlopen(req,timeout=6) as stream:
            raw=stream.read(150001)
            if len(raw)>150000:
                raise ValueError("Market data response too large.")
        data=json.loads(raw)
        if not isinstance(data.get("values"),list):
            raise ValueError("Provider unavailable.")
        points=[{"date":str(item["datetime"]),"close":float(item["close"])}
                for item in data["values"][:days]]
        if not points or any(not (0<point["close"]<1e9) for point in points):
            raise ValueError("Invalid provider data.")
    except (ValueError,KeyError,TypeError,OSError) as e:
        raise HTTPException(502,"Market provider temporarily unavailable.") from e
    result={"symbol":symbol,"provider":"Twelve Data","currency":data.get("meta",{}).get("currency","USD"),
            "interval":"1day","fetched_at":now_iso(),"prices":list(reversed(points)),
            "note":"Historical closes, may be delayed; not connected to the virtual portfolio."}
    with MARKET_LOCK:
        if len(MARKET_CACHE)>100:MARKET_CACHE.clear()
        MARKET_CACHE[cache_key]=(time.monotonic(),result)
    return result

@router.get("/api/billing/status")
def billing_status(user:Annotated[dict,Depends(session_auth)]):
    return {"plan":user["plan"],"checkout_configured":bool(STRIPE_SECRET and STRIPE_PRICE and STRIPE_WEBHOOK)}

@router.post("/api/billing/checkout")
def billing_checkout(user:Annotated[dict,Depends(csrf_guard)]):
    if not (STRIPE_SECRET and STRIPE_PRICE and STRIPE_WEBHOOK):
        raise HTTPException(503,"Subscriptions are not available yet.")
    with db_conn() as db:
        other = db.execute("SELECT 1 FROM paypal_subscriptions WHERE user_id=? AND status NOT IN ('CANCELLED','EXPIRED')",(user["id"],)).fetchone()
        if other:
            raise HTTPException(409,"Manage your existing PayPal subscription before using Stripe.")
    if not PUBLIC_URL.startswith("https://"):
        raise HTTPException(503,"HTTPS public URL required for billing.")
    try:
        import stripe
        stripe.api_key=STRIPE_SECRET
        checkout=stripe.checkout.Session.create(
            mode="subscription",line_items=[{"price":STRIPE_PRICE,"quantity":1}],
            client_reference_id=str(user["id"]),
            customer_email=user["email"],
            success_url=PUBLIC_URL+"/?checkout=success",
            cancel_url=PUBLIC_URL+"/?checkout=cancelled",
        )
    except Exception as e:
        raise HTTPException(502,"Payment provider temporarily unavailable.") from e
    return {"checkout_url":checkout.url}

@router.post("/api/billing/webhook")
async def billing_webhook(request:Request,stripe_signature:Annotated[str | None,Header()]=None):
    if not STRIPE_WEBHOOK:
        raise HTTPException(503,"Webhooks not configured.")
    if not stripe_signature:
        raise HTTPException(400,"Missing signature.")
    import stripe
    payload=await request.body()
    if len(payload)>65536:
        raise HTTPException(413,"Payload too large.")
    try:
        event=stripe.Webhook.construct_event(payload,stripe_signature,STRIPE_WEBHOOK)
    except (ValueError,stripe.error.SignatureVerificationError) as e:
        raise HTTPException(400,"Invalid webhook signature.") from e
    event_type=event["type"]
    obj=event["data"]["object"]
    with db_conn() as db:
        if db.execute("SELECT 1 FROM stripe_events WHERE event_id=?",(event["id"],)).fetchone():
            return {"received":True}
        if event_type=="checkout.session.completed" and obj.get("mode")=="subscription" and obj.get("payment_status")=="paid":
            ref=obj.get("client_reference_id")
            subscription=obj.get("subscription")
            if ref and str(ref).isdigit() and subscription:
                db.execute("""INSERT INTO stripe_subscriptions(stripe_subscription_id,user_id,stripe_customer_id,status)
                    VALUES(?,?,?,?) ON CONFLICT(stripe_subscription_id)
                    DO UPDATE SET status=excluded.status""",(subscription,int(ref),obj.get("customer"),"active"))
                db.execute("UPDATE users SET plan='premium' WHERE id=?",(int(ref),))
        elif event_type in ("customer.subscription.deleted","customer.subscription.updated"):
            subid=obj.get("id");status=obj.get("status","unknown")
            db.execute("UPDATE stripe_subscriptions SET status=? WHERE stripe_subscription_id=?",(status,subid))
            row=db.execute("SELECT user_id FROM stripe_subscriptions WHERE stripe_subscription_id=?",(subid,)).fetchone()
            if row:
                db.execute("UPDATE users SET plan=? WHERE id=?",
                           ("premium" if status in ("active","trialing") else "free",row["user_id"]))
        # Reconcile entitlements across both providers; a Stripe cancellation
        # must never override an active PayPal membership.
        affected = None
        if event_type == "checkout.session.completed" and obj.get("payment_status") == "paid":
            customer_ref = obj.get("client_reference_id")
            if customer_ref and str(customer_ref).isdigit():
                affected = int(customer_ref)
        elif event_type in ("customer.subscription.deleted","customer.subscription.updated") and row:
            affected = row["user_id"]
        if affected is not None:
            recompute_membership(db, affected)
        db.execute("INSERT INTO stripe_events(event_id,processed_at) VALUES(?,?)",(event["id"],now_iso()))
        db.commit()
    return {"received":True}
