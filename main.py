"""Moneliora educational sandbox. No live orders or real account balances."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hmac
import os
from pathlib import Path
import sqlite3
import threading
import time

from fastapi import FastAPI, Header, HTTPException, Request
from platform_features import router as platform_router
from market_data import router as market_router
from paypal_billing import router as paypal_router
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, field_validator

ROOT = Path(__file__).resolve().parent
DB = Path(os.getenv("MONELIORA_DB", str(ROOT / "data" / "moneliora.db")))
ADMIN_TOKEN = os.getenv("MONELIORA_ADMIN_TOKEN", "")
ALLOWED_ORIGIN = os.getenv("MONELIORA_ORIGIN", "http://127.0.0.1:8000").rstrip("/")
PUBLIC_PREVIEW = os.getenv("MONELIORA_PUBLIC_PREVIEW", "false").strip().lower() == "true"
app = FastAPI(title="Moneliora", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.include_router(platform_router)
app.include_router(market_router)
app.include_router(paypal_router)
rate_lock = threading.Lock()
requests_by_client: dict[str, list[float]] = {}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; "
       "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
       "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")

def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("""CREATE TABLE IF NOT EXISTS consultations(
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL,
        topic TEXT NOT NULL, preferred_date TEXT NOT NULL,
        message TEXT NOT NULL, consent_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'requested')""")
    return db

class Consultation(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    topic: str = Field(min_length=3, max_length=80)
    preferred_date: date
    message: str = Field(default="", max_length=1200)
    privacy_accepted: bool

    model_config = {"extra": "forbid"}

    @field_validator("name", "topic", "message")
    @classmethod
    def clean_text(cls, v: str):
        v = v.strip()
        if any(ord(c) < 32 and c not in "\n\t" for c in v) or "<" in v or ">" in v:
            raise ValueError("Markup and control characters are not accepted")
        return v

    @field_validator("preferred_date")
    @classmethod
    def reasonable_date(cls, v: date):
        if not date.today() <= v <= date.today() + timedelta(days=180):
            raise ValueError("Date must be within the next 180 days")
        return v

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
}

@app.middleware("http")
async def security_headers(request: Request, call_next):
    # Fail closed for all stateful and provider APIs when a public demo is deployed.
    # Use /api/health for unauthenticated uptime checks only.
    if PUBLIC_PREVIEW and request.url.path.startswith("/api/") and request.url.path != "/api/health":
        response = JSONResponse(
            {"detail": "Customer accounts, billing and market feeds are disabled in this public demo."},
            status_code=403,
        )
        response.headers.update(SECURITY_HEADERS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
    # Also apply headers on rejected requests, not only successful responses.
    rejection = None
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if request.url.path in ("/api/billing/webhook", "/api/paypal/webhook"):
            response = await call_next(request)
            response.headers.update(SECURITY_HEADERS)
            return response
        origin = request.headers.get("origin")
        if origin is not None and origin.rstrip("/") != ALLOWED_ORIGIN:
            rejection = JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        # A bodyless DELETE does not need a content type.
        elif request.method in ("POST", "PUT", "PATCH"):
            if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
                rejection = JSONResponse({"detail": "JSON required"}, status_code=415)
        if rejection is None:
            length = request.headers.get("content-length")
            if length:
                try:
                    too_large = int(length) > 4096
                except ValueError:
                    too_large = True
                if too_large:
                    rejection = JSONResponse({"detail": "Request too large"}, status_code=413)
    response = rejection if rejection is not None else await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.get("/")
def home():
    if PUBLIC_PREVIEW:
        # Keep simulated investing tools interactive, but remove UI for private
        # customer details and billing. No customer APIs are available in preview.
        page = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        for script in ("account.js", "paypal.js", "market.js"):
            page = page.replace(f'<script src="/static/{script}" defer></script>', "")
        page = page.replace(
            "<body>",
            '<body class="public-preview">'
            '<div class="preview-banner" role="status">'
            "PUBLIC EDUCATIONAL PREVIEW — simulated money and fictional stock prices only. "
            "Accounts, contact forms, payments and live data are disabled.</div>",
            1,
        )
        return HTMLResponse(page)
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/api/health")
def health():
    return {"ok": True, "mode": "public-preview" if PUBLIC_PREVIEW else "education-only", "live_trading": False, "payments_enabled": False if PUBLIC_PREVIEW else None}

@app.post("/api/consultations", status_code=201)
def create_consultation(payload: Consultation, request: Request):
    if not payload.privacy_accepted:
        raise HTTPException(400, "Privacy consent is required")
    # Use a trusted reverse proxy for public deployments; do not trust X-Forwarded-For.
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with rate_lock:
        hits = [t for t in requests_by_client.get(client, []) if now - t < 3600]
        if len(hits) >= 5:
            raise HTTPException(429, "Rate limit exceeded")
        hits.append(now)
        requests_by_client[client] = hits
    timestamp = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        db.execute("DELETE FROM consultations WHERE consent_at < ?",
                   ((datetime.now(timezone.utc)-timedelta(days=90)).isoformat(),))
        cursor = db.execute(
            "INSERT INTO consultations(name,email,topic,preferred_date,message,consent_at) VALUES(?,?,?,?,?,?)",
            (payload.name, str(payload.email), payload.topic,
             str(payload.preferred_date), payload.message, timestamp))
        db.commit()
    return {"id": cursor.lastrowid, "status": "requested",
            "note": "Request received; this is not a confirmed appointment."}

def require_admin(token: str | None):
    if not ADMIN_TOKEN or len(ADMIN_TOKEN) < 32:
        raise HTTPException(503, "Admin API disabled")
    if not token or not hmac.compare_digest(token, ADMIN_TOKEN):
        raise HTTPException(401, "Not authorized")

@app.get("/api/admin/consultations")
def admin_list(x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    with connect() as db:
        data = db.execute(
            "SELECT id,name,email,topic,preferred_date,message,consent_at,status "
            "FROM consultations ORDER BY id DESC LIMIT 100").fetchall()
    return {"requests": [dict(row) for row in data]}

@app.delete("/api/admin/consultations/{item_id}")
def admin_delete(item_id: int, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    with connect() as db:
        result = db.execute("DELETE FROM consultations WHERE id=?", (item_id,))
        db.commit()
    if not result.rowcount:
        raise HTTPException(404, "Not found")
    return {"deleted": True}
